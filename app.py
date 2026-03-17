import os
import base64
import re
import html as html_lib
from email.utils import parsedate_to_datetime
from typing import List

from flask import Flask, jsonify, render_template, request

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services.gmail_service import (
    get_all_labels,
    get_label_map,
    apply_label,
    remove_label,
    archive_message,
    delete_message,
)
from services.openai_service import get_mail_recommendation

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

app = Flask(__name__)

# Globals kept simple for single-user local app
SERVICE = None
AVAILABLE_LABELS: List[str] = []
LABEL_MAP = {}
MESSAGE_IDS: List[str] = []
ANALYSIS_CACHE = {}


def init_service():
    global SERVICE, AVAILABLE_LABELS, LABEL_MAP
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            # Opens a browser for OAuth once
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    SERVICE = build("gmail", "v1", credentials=creds)
    AVAILABLE_LABELS = get_all_labels(SERVICE)
    LABEL_MAP = get_label_map(SERVICE)


def extract_message_text(payload):
    texts = []
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if data and (mime.startswith("text/plain") or mime.startswith("text/html")):
        try:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            if mime.startswith("text/html"):
                decoded = re.sub(r"<[^>]+>", " ", decoded)
            texts.append(decoded)
        except Exception:
            pass
    for part in payload.get("parts", []):
        texts.append(extract_message_text(part))
    return "\n".join(t for t in texts if t)


def extract_message_html(payload):
    """Extract the first available HTML body from a Gmail message payload.
    Falls back to None if no HTML part is found.
    """
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    # Direct HTML part
    if data and mime.startswith("text/html"):
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        except Exception:
            return None

    # Multipart: search parts, prefer HTML
    parts = payload.get("parts", [])
    for part in parts:
        found = extract_message_html(part)
        if found:
            return found

    return None


def load_inbox_ids(max_fetch: int = 200, mailbox: str = "inbox"):
    """Load up to max_fetch message IDs from specified mailbox into MESSAGE_IDS.

    Args:
        max_fetch: Maximum number of messages to fetch
        mailbox: Either 'inbox' for inbox only, or 'all' for all mail
    """
    global MESSAGE_IDS, SERVICE
    if SERVICE is None:
        init_service()
    assert SERVICE is not None

    MESSAGE_IDS = []
    next_page_token = None
    fetched = 0
    try:
        while True:
            params = {"userId": "me", "maxResults": 100}
            # Only filter by inbox if mailbox is 'inbox'
            if mailbox == "inbox":
                params["q"] = "in:inbox"
            if next_page_token:
                params["pageToken"] = next_page_token
            results = SERVICE.users().messages().list(**params).execute()
            msgs = results.get("messages", [])
            for m in msgs:
                if fetched >= max_fetch:
                    break
                MESSAGE_IDS.append(m["id"])
                fetched += 1
            if fetched >= max_fetch:
                break
            next_page_token = results.get("nextPageToken")
            if not next_page_token:
                break
    except HttpError as e:
        print(f"Error listing messages: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/labels", methods=["GET"])
def api_labels():
    return jsonify({"labels": AVAILABLE_LABELS})


@app.route("/api/messages/count", methods=["GET"])
def api_messages_count():
    mailbox = request.args.get("mailbox", "inbox")
    load_inbox_ids(max_fetch=500, mailbox=mailbox)
    return jsonify({"count": len(MESSAGE_IDS)})


@app.route("/api/messages/item", methods=["GET"])
def api_message_item():
    global SERVICE
    if SERVICE is None:
        init_service()
    assert SERVICE is not None

    try:
        index = int(request.args.get("index", "0"))
    except ValueError:
        index = 0

    mailbox = request.args.get("mailbox", "inbox")
    # Reload messages if mailbox parameter is present to ensure we have the right set
    if mailbox:
        load_inbox_ids(max_fetch=500, mailbox=mailbox)
    if index < 0 or index >= len(MESSAGE_IDS):
        return jsonify({"error": "Index out of range"}), 404

    msg_id = MESSAGE_IDS[index]
    try:
        msg = SERVICE.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Onbekend")
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(geen onderwerp)")
        date_str = next((h["value"] for h in headers if h["name"] == "Date"), "Onbekend")

        # Parse date
        try:
            date_obj = parsedate_to_datetime(date_str)
            date_formatted = date_obj.strftime("%d-%m-%Y")
        except Exception:
            date_formatted = "Onbekend"

        # Clean sender display
        if "<" in sender:
            sender = sender.split("<")[0].strip()

        payload = msg.get("payload", {})
        full_text = extract_message_text(payload) or ""
        body_html = extract_message_html(payload)
        if not body_html:
            # Fallback: escape plain text and convert line breaks
            escaped = html_lib.escape(full_text)
            escaped_with_breaks = escaped.replace("\n", "<br>")
            body_html = f"<div>{escaped_with_breaks}</div>"
        current_label_ids = msg.get("labelIds", [])
        current_labels = [LABEL_MAP.get(lid, lid) for lid in current_label_ids]

        return jsonify({
            "id": msg_id,
            "subject": subject,
            "sender": sender,
            "date": date_formatted,
            "body": full_text,
            "bodyHtml": body_html,
            "labels": current_labels,
            "index": index,
            "total": len(MESSAGE_IDS),
        })
    except HttpError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages/<message_id>/labels", methods=["POST"])
def api_set_labels(message_id):
    global SERVICE
    if SERVICE is None:
        init_service()
    assert SERVICE is not None
    data = request.get_json(silent=True) or {}
    desired_labels = data.get("labels", [])
    if not isinstance(desired_labels, list):
        return jsonify({"error": "labels must be list"}), 400

    # Get current labels for message
    try:
        msg = SERVICE.users().messages().get(userId="me", id=message_id, format="minimal").execute()
        current_label_ids = msg.get("labelIds", [])
        current_labels = set(LABEL_MAP.get(lid, lid) for lid in current_label_ids)
    except HttpError as e:
        return jsonify({"error": str(e)}), 500

    desired_set = set(desired_labels)

    # Consider all labels; protect a few special ones from removal/add for safety
    # Avoid changing core mailbox controls via the modal
    unmodifiable = {"INBOX", "TRASH", "SPAM"}

    current_set = set(current_labels)
    to_add = {l for l in (desired_set - current_set) if l not in unmodifiable}
    to_remove = {l for l in (current_set - desired_set) if l not in unmodifiable}

    added = []
    removed = []
    for l in to_add:
        if apply_label(SERVICE, message_id, l):
            added.append(l)
    for l in to_remove:
        if remove_label(SERVICE, message_id, l):
            removed.append(l)

    return jsonify({"added": added, "removed": removed})


@app.route("/api/messages/<message_id>/archive", methods=["POST"])
def api_archive(message_id):
    global SERVICE
    if SERVICE is None:
        init_service()
    assert SERVICE is not None
    ok = archive_message(SERVICE, message_id)
    return jsonify({"archived": ok})


@app.route("/api/messages/<message_id>/delete", methods=["POST"])
def api_delete(message_id):
    global SERVICE
    if SERVICE is None:
        init_service()
    assert SERVICE is not None
    ok = delete_message(SERVICE, message_id)
    return jsonify({"deleted": ok})


@app.route("/api/messages/<message_id>/analysis", methods=["GET"])
def api_get_analysis(message_id):
    text = ANALYSIS_CACHE.get(message_id)
    if text is None:
        return jsonify({"error": "Not analyzed"}), 404
    return jsonify({"text": text})


@app.route("/api/messages/<message_id>/analyze", methods=["POST"])
def api_analyze(message_id):
    global SERVICE
    if SERVICE is None:
        init_service()
    assert SERVICE is not None
    # If cached, return cached without re-generating
    if message_id in ANALYSIS_CACHE:
        return jsonify({"text": ANALYSIS_CACHE[message_id], "cached": True})
    try:
        msg = SERVICE.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Onbekend")
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(geen onderwerp)")
        body_text = extract_message_text(msg.get("payload", {})) or ""
        current_label_ids = msg.get("labelIds", [])
        current_labels = [LABEL_MAP.get(lid, lid) for lid in current_label_ids]

        # Call AI service
        recommendation_text = get_mail_recommendation(
            sender,
            subject,
            body_text,
            AVAILABLE_LABELS,
            current_labels,
        )
        ANALYSIS_CACHE[message_id] = recommendation_text or "Geen aanbeveling ontvangen"
        return jsonify({"text": ANALYSIS_CACHE[message_id], "cached": False})
    except HttpError as e:
        return jsonify({"error": str(e)}), 500


def startup():
    init_service()
    load_inbox_ids()


if __name__ == "__main__":
    startup()
    app.run(host="127.0.0.1", port=5000, debug=True)

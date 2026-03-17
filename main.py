import os.path
import base64
import json
import re
from email.utils import parsedate_to_datetime

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
  unarchive_message,
  delete_message,
  untrash_message,
)
from services.openai_service import get_mail_recommendation

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main():
  """Process Gmail inbox with AI recommendations."""
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
      creds = flow.run_local_server(port=0)
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("gmail", "v1", credentials=creds)

    # Get all available labels
    available_labels = get_all_labels(service)
    # Build full label map for displaying existing labels on messages
    label_map = get_label_map(service)
    print(f"Beschikbare labels: {', '.join(available_labels)}\n")
    print("=" * 100)

    # Iterate all messages from INBOX using pagination
    next_page_token = None
    total_processed = 0

    while True:
      params = {"userId": "me", "q": "in:inbox", "maxResults": 10}
      if next_page_token:
        params["pageToken"] = next_page_token

      results = service.users().messages().list(**params).execute()
      messages = results.get("messages", [])

      if not messages:
        if total_processed == 0:
          print("Geen e-mails gevonden in inbox.")
        break

      for idx, message in enumerate(messages, 1):
        last_action = None  # track last action for undo: ('labels_add', [names]) | ('archive', None) | ('trash', None)
        msg_id = message["id"]
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = msg["payload"]["headers"]

        # Extract email information
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Onbekend")
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(geen onderwerp)")
        date_str = next((h["value"] for h in headers if h["name"] == "Date"), "Onbekend")

        # Parse date
        try:
          date_obj = parsedate_to_datetime(date_str)
          date_formatted = date_obj.strftime("%d-%m-%Y")
        except:
          date_formatted = "Onbekend"

        # Clean up sender
        if "<" in sender:
          sender = sender.split("<")[0].strip()

        # Extract full text content (plain + html fallback)
        def extract_message_text(payload):
          texts = []
          mime = payload.get("mimeType", "")
          body = payload.get("body", {})
          data = body.get("data")
          if data and (mime.startswith("text/plain") or mime.startswith("text/html")):
            try:
              decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
              if mime.startswith("text/html"):
                # Naive HTML to text: strip tags
                decoded = re.sub(r"<[^>]+>", " ", decoded)
              texts.append(decoded)
            except Exception:
              pass
          for part in payload.get("parts", []):
            texts.append(extract_message_text(part))
          # Join nested results
          return "\n".join(t for t in texts if t)

        full_text = extract_message_text(msg.get("payload", {})) or ""
        # Compute preview from full text first non-empty line
        preview = next((line.strip() for line in full_text.splitlines() if line.strip()), "")
        if not preview:
          preview = "(geen preview)"

        # Current labels on the message
        current_label_ids = msg.get("labelIds", [])
        current_labels = [label_map.get(lid, lid) for lid in current_label_ids]

        # Display email
        print(f"\n[{idx}] Datum: {date_formatted}")
        print(f"Van: {sender}")
        print(f"Onderwerp: {subject}")
        print(f"Preview: {preview}")
        print(f"Labels: {', '.join(current_labels) if current_labels else '(geen)'}")

        # Interactive action loop: allow multiple actions and optional AI analysis
        try:
          while True:
            print("\nWat wil je doen?")
            print("1. Analyseer met AI")
            print("2. Label(s) toevoegen")
            print("3. Archiveren")
            print("4. Verwijderen (naar prullenbak)")
            print("5. Undo laatste actie")
            print("6. Volgende mail")

            action = input("\nKeuze (1/2/3/4/5/6): ").strip()

            if action == '1':
              # Analyseer met AI met volledige inhoud en huidige labels
              print("\n🤖 Analyseren met AI...")
              # Fallback in case full_text is empty
              body_for_ai = full_text if full_text.strip() else preview
              recommendation_text = get_mail_recommendation(
                sender,
                subject,
                body_for_ai,
                available_labels,
                current_labels,
              )
              print(f"\n✅ AI Aanbeveling:")
              print(recommendation_text)
            elif action == '2':
              # Label(s) toevoegen
              if not available_labels:
                print("(Geen gebruikerslabels beschikbaar)")
                continue

              print("\nBeschikbare labels:")
              for i, label in enumerate(available_labels, 1):
                print(f"  {i}. {label}")

              label_input = input("\nKies label(s) (bijv. 1,3,5 of 1-3): ").strip()

              # Parse label selection
              selected_labels = []
              if label_input:
                try:
                  for part in label_input.split(','):
                    part = part.strip()
                    if '-' in part:
                      # Range like 1-3
                      start, end = part.split('-')
                      for i in range(int(start), int(end) + 1):
                        if 1 <= i <= len(available_labels):
                          selected_labels.append(available_labels[i-1])
                    else:
                      # Single number
                      i = int(part)
                      if 1 <= i <= len(available_labels):
                        selected_labels.append(available_labels[i-1])
                except ValueError:
                  print("Ongeldige invoer. Gebruik nummers zoals 1,3,5 of 1-3.")
                  continue

              # Deduplicate while preserving order
              seen = set()
              selected_labels = [x for x in selected_labels if not (x in seen or seen.add(x))]

              if not selected_labels:
                print("(Geen geldige labels gekozen)")
                continue

              for label in selected_labels:
                apply_label(service, msg_id, label)
                print(f"✓ Label toegevoegd: {label}")
              if selected_labels:
                last_action = ('labels_add', selected_labels)

            elif action == '3':
              # Archiveren
              archive_message(service, msg_id)
              print("✓ Gearchiveerd")
              last_action = ('archive', None)
            elif action == '4':
              # Verwijderen en naar volgende mail
              delete_message(service, msg_id)
              print("✓ Naar prullenbak verplaatst")
              last_action = ('trash', None)
            elif action == '5':
              # Undo laatste actie
              if not last_action:
                print("(Geen actie om ongedaan te maken)")
                continue
              action_type, data = last_action
              if action_type == 'labels_add':
                for label in data or []:
                  remove_label(service, msg_id, label)
                  print(f"↩︎ Label verwijderd: {label}")
                last_action = None
              elif action_type == 'archive':
                unarchive_message(service, msg_id)
                print("↩︎ Hersteld naar INBOX")
                last_action = None
              elif action_type == 'trash':
                untrash_message(service, msg_id)
                print("↩︎ Hersteld uit prullenbak")
                last_action = None
              else:
                print("(Onbekende actie kan niet ongedaan gemaakt worden)")
            elif action == '6':
              # Volgende mail
              print("→ Volgende mail")
              break
            else:
              print("Ongeldige keuze. Probeer opnieuw.")

        except Exception as e:
          print(f"⚠️  Fout bij AI-analyse: {e}")


        print("\n" + "=" * 100)
        total_processed += 1

      # end for message loop

      next_page_token = results.get("nextPageToken")
      if not next_page_token:
        break

  except HttpError as error:
    print(f"An error occurred: {error}")
if __name__ == "__main__":
  main()

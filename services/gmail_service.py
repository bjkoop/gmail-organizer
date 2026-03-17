from googleapiclient.errors import HttpError


def get_all_labels(service):
    """
    Get all available Gmail labels for the user.

    Args:
        service: Gmail API service object

    Returns:
        List of label names (including system labels like STARRED/IMPORTANT/CATEGORY_*)
    """
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        label_names = [label.get("name", "") for label in labels if label.get("name")]
        return sorted(label_names)
    except HttpError as error:
        print(f"Error getting labels: {error}")
        return []

def get_label_map(service):
    """Return a mapping of labelId -> labelName for all labels."""
    labels_result = service.users().labels().list(userId="me").execute()
    labels = labels_result.get("labels", [])
    return {l["id"]: l["name"] for l in labels}


def _get_label_id_by_name(service, label_name):
    """Internal helper: resolve a label name to its Gmail label ID."""
    try:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label.get("name") == label_name:
                return label.get("id")
    except HttpError:
        pass
    return None


def apply_label(service, message_id, label_name):
    """
    Apply a label to a message.

    Args:
        service: Gmail API service object
        message_id: The ID of the message
        label_name: The name of the label to apply
    """
    try:
        label_id = _get_label_id_by_name(service, label_name)
        if label_id:
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]},
            ).execute()
            return True
    except HttpError as error:
        print(f"Error applying label: {error}")

    return False


def remove_label(service, message_id, label_name):
    """
    Remove a label from a message.
    """
    try:
        label_id = _get_label_id_by_name(service, label_name)
        if label_id:
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": [label_id]},
            ).execute()
            return True
    except HttpError as error:
        print(f"Error removing label: {error}")
    return False


def archive_message(service, message_id):
    """
    Archive a message by removing it from INBOX.

    Args:
        service: Gmail API service object
        message_id: The ID of the message
    """
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX"]},
        ).execute()
        return True
    except HttpError as error:
        print(f"Error archiving message: {error}")

    return False


def unarchive_message(service, message_id):
    """
    Unarchive a message by adding it back to INBOX.
    """
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": ["INBOX"]},
        ).execute()
        return True
    except HttpError as error:
        print(f"Error unarchiving message: {error}")
    return False


def delete_message(service, message_id):
    """
    Move a message to Trash (Gmail-like delete).

    Args:
        service: Gmail API service object
        message_id: The ID of the message
    """
    try:
        # Gmail-like delete: move to Trash instead of permanent delete
        service.users().messages().trash(userId="me", id=message_id).execute()
        return True
    except HttpError as error:
        print(f"Error moving message to Trash: {error}")
        # Helpfully hint when scopes are insufficient
        status = None
        try:
            status = getattr(error, 'status_code', None)
            if status is None and hasattr(error, 'resp') and hasattr(error.resp, 'status'):
                status = error.resp.status
        except Exception:
            status = None
        if status == 403:
            print("Tip: Onvoldoende permissies. Verwijder 'token.json' en voer de app opnieuw uit om met scope 'gmail.modify' in te loggen.")

    return False


def untrash_message(service, message_id):
    """
    Restore a message from Trash.
    """
    try:
        service.users().messages().untrash(userId="me", id=message_id).execute()
        return True
    except HttpError as error:
        print(f"Error restoring message from Trash: {error}")
    return False

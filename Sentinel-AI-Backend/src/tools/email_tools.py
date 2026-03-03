# src/tools/email_tools.py
"""
Email Agent tools — Gmail API integration.

Requires Gmail OAuth credentials. On first use, a browser window will open
for authentication. The token is saved to gmail_token.json and reused thereafter.

Setup:
  1. credentials.json must exist in Sentinel-AI-Frontend/ (same file used by GMeet)
  2. Run any email tool once to trigger the OAuth flow
  3. Grant Gmail permissions in the browser
"""

import os
import base64
import email as email_lib
from pathlib import Path
from datetime import datetime
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langchain_core.tools import tool

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Path to credentials.json (reuse the GMeet credentials)
_BACKEND_DIR = Path(__file__).parent.parent.parent
_FRONTEND_DIR = _BACKEND_DIR.parent / "Sentinel-AI-Frontend"
_TOKEN_PATH = _BACKEND_DIR / "gmail_token.json"


def _get_gmail_service():
    """Authenticate and return the Gmail API service object."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    # Try token manager first (MongoDB-backed)
    try:
        from src.utils.token_manager import get_token_manager

        creds = get_token_manager().get_gmail_credentials()
        if creds and creds.valid:
            return build("gmail", "v1", credentials=creds)
    except Exception:
        pass

    # Fallback: file-based token
    creds = None
    if _TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), GMAIL_SCOPES)
        except Exception:
            creds = None

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _TOKEN_PATH.write_text(creds.to_json())
        except Exception:
            creds = None

    # Full OAuth flow if no valid creds
    if not creds or not creds.valid:
        creds_paths = [
            _FRONTEND_DIR / "credentials.json",
            _BACKEND_DIR / "credentials.json",
        ]
        creds_file = next((p for p in creds_paths if p.exists()), None)
        if not creds_file:
            raise FileNotFoundError(
                "credentials.json not found. Place your Google OAuth credentials in "
                "Sentinel-AI-Frontend/credentials.json"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        _TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    """Decode the email body from Gmail API payload."""
    body = ""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    elif mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            # Strip HTML tags for readable plain text
            import re

            body = re.sub(r"<[^>]+>", " ", html)
            body = re.sub(r"\s+", " ", body).strip()

    elif "parts" in payload:
        for part in payload["parts"]:
            part_body = _decode_body(part)
            if part_body:
                body = part_body
                break  # Prefer first readable part

    return body


def _header(headers: list, name: str) -> str:
    """Extract a header value by name from a list of header dicts."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


@tool
def list_emails(max_results: int = 10, label: str = "INBOX") -> str:
    """
    Lists recent emails from your Gmail inbox.

    Args:
        max_results: Number of emails to return (1-50, default 10)
        label: Gmail label to list from (default: INBOX). Other options: SENT, DRAFT, SPAM, STARRED
    """
    try:
        max_results = max(1, min(50, max_results))
        service = _get_gmail_service()

        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label.upper()], maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return f"📭 No emails found in {label}."

        output = f"📬 **{label} — {len(messages)} emails**\n\n"
        for msg_ref in messages:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )

            headers = msg.get("payload", {}).get("headers", [])
            sender = _header(headers, "From")
            subject = _header(headers, "Subject") or "(no subject)"
            date = _header(headers, "Date")

            # Format date
            try:
                dt = email_lib.utils.parsedate_to_datetime(date)
                date_str = dt.strftime("%b %d, %H:%M")
            except Exception:
                date_str = date[:16] if date else "?"

            snippet = msg.get("snippet", "")[:80]
            output += f"🆔 `{msg_ref['id']}`\n"
            output += f"📧 **{subject}**\n"
            output += f"   From: {sender} | {date_str}\n"
            output += f"   {snippet}...\n\n"

        return output.strip()
    except Exception as e:
        return f"❌ Error listing emails: {e}"


@tool
def search_emails(query: str, max_results: int = 10) -> str:
    """
    Searches your Gmail using Gmail's search syntax.

    Args:
        query: Search query (e.g. "from:boss@work.com", "subject:meeting", "is:unread", "after:2024/01/01")
        max_results: Number of results to return (1-50, default 10)
    """
    try:
        max_results = max(1, min(50, max_results))
        service = _get_gmail_service()

        results = (
            service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return f"🔍 No emails found matching: **{query}**"

        output = f"🔍 **Search results for '{query}'** ({len(messages)} found)\n\n"
        for msg_ref in messages:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )

            headers = msg.get("payload", {}).get("headers", [])
            sender = _header(headers, "From")
            subject = _header(headers, "Subject") or "(no subject)"
            date = _header(headers, "Date")

            try:
                dt = email_lib.utils.parsedate_to_datetime(date)
                date_str = dt.strftime("%b %d, %H:%M")
            except Exception:
                date_str = date[:16] if date else "?"

            snippet = msg.get("snippet", "")[:80]
            output += f"🆔 `{msg_ref['id']}`\n"
            output += f"📧 **{subject}**\n"
            output += f"   From: {sender} | {date_str}\n"
            output += f"   {snippet}...\n\n"

        return output.strip()
    except Exception as e:
        return f"❌ Error searching emails: {e}"


@tool
def read_email(email_id: str) -> str:
    """
    Reads the full content of a specific email.

    Args:
        email_id: The email ID (shown in list_emails or search_emails results)
    """
    try:
        service = _get_gmail_service()
        msg = service.users().messages().get(userId="me", id=email_id, format="full").execute()

        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        sender = _header(headers, "From")
        to = _header(headers, "To")
        subject = _header(headers, "Subject") or "(no subject)"
        date = _header(headers, "Date")

        try:
            dt = email_lib.utils.parsedate_to_datetime(date)
            date_str = dt.strftime("%B %d, %Y %I:%M %p")
        except Exception:
            date_str = date

        body = _decode_body(payload)
        body_preview = body[:2000] + ("..." if len(body) > 2000 else "")

        result = f"📧 **{subject}**\n\n"
        result += f"📤 From: {sender}\n"
        result += f"📥 To: {to}\n"
        result += f"📅 Date: {date_str}\n"
        result += f"🆔 ID: `{email_id}`\n\n"
        result += f"---\n{body_preview}"
        return result
    except Exception as e:
        return f"❌ Error reading email {email_id}: {e}"


@tool
def send_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """
    Sends a new email from your Gmail account.

    Args:
        to: Recipient email address (or comma-separated multiple addresses)
        subject: Email subject line
        body: Email body text (plain text)
        cc: Optional CC recipient(s), comma-separated
    """
    try:
        service = _get_gmail_service()

        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(userId="me", body={"raw": raw}).execute()

        return (
            f"✅ **Email sent!**\n\n"
            f"📤 To: {to}\n"
            f"📋 Subject: {subject}\n"
            f"🆔 Message ID: `{result.get('id', 'unknown')}`"
        )
    except Exception as e:
        return f"❌ Error sending email: {e}"


@tool
def reply_to_email(email_id: str, body: str) -> str:
    """
    Replies to an existing email thread.

    Args:
        email_id: The ID of the email to reply to
        body: Your reply text (plain text)
    """
    try:
        service = _get_gmail_service()

        # Get original email for threading headers
        orig = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=email_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Message-ID", "References"],
            )
            .execute()
        )

        headers = orig.get("payload", {}).get("headers", [])
        orig_from = _header(headers, "From")
        orig_subject = _header(headers, "Subject") or ""
        orig_msg_id = _header(headers, "Message-ID")
        orig_refs = _header(headers, "References")
        thread_id = orig.get("threadId", "")

        reply_subject = orig_subject if orig_subject.startswith("Re:") else f"Re: {orig_subject}"

        msg = MIMEMultipart()
        msg["To"] = orig_from
        msg["Subject"] = reply_subject
        msg["In-Reply-To"] = orig_msg_id
        msg["References"] = f"{orig_refs} {orig_msg_id}".strip() if orig_refs else orig_msg_id
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": thread_id})
            .execute()
        )

        return (
            f"✅ **Reply sent!**\n\n"
            f"📤 To: {orig_from}\n"
            f"📋 Subject: {reply_subject}\n"
            f"🆔 Message ID: `{result.get('id', 'unknown')}`"
        )
    except Exception as e:
        return f"❌ Error replying to email {email_id}: {e}"


@tool
def draft_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """
    Saves an email as a draft in Gmail (does NOT send it).

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body text (plain text)
        cc: Optional CC recipient(s), comma-separated
    """
    try:
        service = _get_gmail_service()

        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = (
            service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        )

        draft_id = result.get("id", "unknown")
        return (
            f"📝 **Draft saved!**\n\n"
            f"📤 To: {to}\n"
            f"📋 Subject: {subject}\n"
            f"🆔 Draft ID: `{draft_id}`\n\n"
            f"The draft is saved in your Gmail Drafts folder. You can edit and send it from Gmail."
        )
    except Exception as e:
        return f"❌ Error creating draft: {e}"


@tool
def trash_email(email_id: str) -> str:
    """
    Moves an email to the Gmail trash (can be recovered within 30 days).

    Args:
        email_id: The ID of the email to trash
    """
    try:
        service = _get_gmail_service()

        # Get subject before trashing for confirmation
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=email_id, format="metadata", metadataHeaders=["Subject"])
            .execute()
        )

        headers = msg.get("payload", {}).get("headers", [])
        subject = _header(headers, "Subject") or "(no subject)"

        service.users().messages().trash(userId="me", id=email_id).execute()
        return f"🗑️ Moved to trash: **{subject}** (ID: `{email_id}`)\nYou can recover it from Gmail Trash within 30 days."
    except Exception as e:
        return f"❌ Error trashing email {email_id}: {e}"


@tool
def get_email_summary() -> str:
    """
    Gets a quick summary of your inbox: unread count, recent senders, and starred emails.
    """
    try:
        service = _get_gmail_service()

        # Get unread count
        unread = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=1)
            .execute()
        )
        unread_estimate = unread.get("resultSizeEstimate", 0)

        # Get 5 most recent unread emails
        recent_unread = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=5)
            .execute()
        )

        output = f"📬 **Gmail Summary**\n\n"
        output += f"📭 Unread messages: **~{unread_estimate}**\n\n"

        messages = recent_unread.get("messages", [])
        if messages:
            output += "**Recent unread:**\n"
            for msg_ref in messages:
                msg = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_ref["id"],
                        format="metadata",
                        metadataHeaders=["From", "Subject"],
                    )
                    .execute()
                )
                headers = msg.get("payload", {}).get("headers", [])
                sender = _header(headers, "From").split("<")[0].strip()
                subject = _header(headers, "Subject") or "(no subject)"
                output += f"  • **{subject[:50]}** — from {sender}\n"

        return output.strip()
    except Exception as e:
        return f"❌ Error getting email summary: {e}"


email_tools = [
    list_emails,
    search_emails,
    read_email,
    send_email,
    reply_to_email,
    draft_email,
    trash_email,
    get_email_summary,
]

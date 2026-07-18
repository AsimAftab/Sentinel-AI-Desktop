"""Email tools — Gmail API integration.

Ported from the legacy email_tools.py. Auth goes through
sentinel_core.google_auth (shared token with the meeting tools). Reading tools
return raw content; summarization is left to the LLM. Errors are returned as
short strings, never tracebacks.
"""

from __future__ import annotations

import base64
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _service():
    """Build a Gmail API client (lazy — never at import time)."""
    from googleapiclient.discovery import build

    from sentinel_core.google_auth import get_credentials

    return build("gmail", "v1", credentials=get_credentials(SCOPES))


def _err(action: str, exc: Exception) -> str:
    from googleapiclient.errors import HttpError

    logger.error("Email tool failed (%s): %s", action, exc, exc_info=True)
    if isinstance(exc, ValueError):  # setup instructions from google_auth
        return str(exc)
    if isinstance(exc, HttpError):
        return f"Gmail API error while trying to {action} (HTTP {exc.status_code})."
    return f"Could not {action}: {type(exc).__name__}: {exc}"


def _header(headers: list[dict], name: str) -> str:
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _short_date(raw: str) -> str:
    try:
        return parsedate_to_datetime(raw).astimezone().strftime("%b %d, %H:%M")
    except Exception:
        return raw[:16] if raw else "?"


def _decode_body(payload: dict) -> str:
    """Extract readable plain text from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data", "")
    if mime_type == "text/plain" and data:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime_type == "text/html" and data:
        html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    for part in payload.get("parts", []):
        if body := _decode_body(part):
            return body
    return ""


def _list_messages(query: str | None, label: str | None, max_results: int) -> str:
    service = _service()
    kwargs: dict = {"userId": "me", "maxResults": max(1, min(50, max_results))}
    if query:
        kwargs["q"] = query
    if label:
        kwargs["labelIds"] = [label.upper()]
    refs = service.users().messages().list(**kwargs).execute().get("messages", [])
    if not refs:
        return "No emails found."
    lines = [f"{len(refs)} email(s):", ""]
    for ref in refs:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = msg.get("payload", {}).get("headers", [])
        subject = _header(headers, "Subject") or "(no subject)"
        lines.append(f"- {subject}")
        lines.append(
            f"  from: {_header(headers, 'From')} | {_short_date(_header(headers, 'Date'))}"
        )
        lines.append(f"  id: {ref['id']}")
        if snippet := msg.get("snippet", "")[:100]:
            lines.append(f"  {snippet}")
    return "\n".join(lines)


def _validate_recipients(addresses: str, field: str) -> str | None:
    emails = [a.strip() for a in addresses.split(",") if a.strip()]
    if not emails:
        return f"'{field}' must contain at least one email address."
    bad = [a for a in emails if "@" not in a]
    if bad:
        return f"Invalid {field} address(es): {', '.join(bad)}"
    return None


def _build_message(to: str, subject: str, body: str, cc: str = "") -> str:
    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body, "plain"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


@tool
def list_emails(max_results: int = 10, label: str = "INBOX") -> str:
    """List recent emails from Gmail with sender, subject, date, snippet, and id.

    Args:
        max_results: Number of emails to return (1-50).
        label: Gmail label to list from: INBOX, SENT, DRAFT, SPAM, STARRED, UNREAD.
    """
    try:
        return _list_messages(query=None, label=label, max_results=max_results)
    except Exception as exc:
        return _err("list emails", exc)


@tool
def search_emails(query: str, max_results: int = 10) -> str:
    """Search Gmail using Gmail search syntax and return matching emails with ids.

    Args:
        query: Gmail search query, e.g. "from:boss@work.com", "subject:invoice",
            "is:unread", "after:2026/01/01", or free text.
        max_results: Number of results to return (1-50).
    """
    try:
        if not query.strip():
            return "Search query must not be empty."
        return _list_messages(query=query, label=None, max_results=max_results)
    except Exception as exc:
        return _err("search emails", exc)


@tool
def read_email(email_id: str) -> str:
    """Read the full content of one email (headers + body text) by its id.

    Use the id shown by list_emails or search_emails. Returns the raw text so
    you can quote, answer questions about, or summarize it.

    Args:
        email_id: The Gmail message id.
    """
    try:
        if not email_id.strip():
            return "An email id is required. Use list_emails or search_emails to find it."
        msg = _service().users().messages().get(userId="me", id=email_id, format="full").execute()
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        body = _decode_body(payload) or msg.get("snippet", "") or "(empty body)"
        if len(body) > 4000:
            body = body[:4000] + "... [truncated]"
        return "\n".join(
            [
                f"Subject: {_header(headers, 'Subject') or '(no subject)'}",
                f"From: {_header(headers, 'From')}",
                f"To: {_header(headers, 'To')}",
                f"Date: {_short_date(_header(headers, 'Date'))}",
                "",
                body,
            ]
        )
    except Exception as exc:
        return _err(f"read email {email_id}", exc)


@tool
def draft_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """Save an email as a Gmail draft (does NOT send it).

    Args:
        to: Recipient address(es), comma-separated.
        subject: Subject line.
        body: Plain-text body.
        cc: Optional CC address(es), comma-separated.
    """
    try:
        if error := _validate_recipients(to, "to"):
            return error
        raw = _build_message(to, subject, body, cc)
        result = (
            _service()
            .users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return (
            f"Draft saved (id: {result.get('id', 'unknown')}) to {to}, subject '{subject}'. "
            "It is in the Gmail Drafts folder, not sent."
        )
    except Exception as exc:
        return _err("save the draft", exc)


@tool
def send_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """Send an email from the user's Gmail account. Confirm details with the user first.

    Args:
        to: Recipient address(es), comma-separated.
        subject: Subject line.
        body: Plain-text body.
        cc: Optional CC address(es), comma-separated.
    """
    try:
        if error := _validate_recipients(to, "to"):
            return error
        if cc and (error := _validate_recipients(cc, "cc")):
            return error
        raw = _build_message(to, subject, body, cc)
        result = _service().users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to}, subject '{subject}' (id: {result.get('id', 'unknown')})."
    except Exception as exc:
        return _err("send the email", exc)


TOOLS = [
    list_emails,
    search_emails,
    read_email,
    draft_email,
    send_email,
]

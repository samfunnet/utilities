from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from simplegmail import Gmail

if TYPE_CHECKING:
    # from simplegmail.draft import Draft
    from simplegmail.message import Message

DEFAULT_CREDS_DIR = Path.home() / ".config" / "credentials" / "gmail"


def get_gmail(creds_dir: Path | str | None = None) -> Gmail:
    """Kobler til Gmail og returnerer en autentisert klient.

    Bruker som standard filene i ~/.config/credentials/gmail/
    """
    base_path = Path(creds_dir) if creds_dir else DEFAULT_CREDS_DIR

    secret_file = base_path / "client_secret.json"
    token_file = base_path / "gmail_token.json"

    if not token_file.exists() and not secret_file.exists():
        raise FileNotFoundError(
            f"Fant verken token eller client_secret i mappen: {base_path}"
        )

    return Gmail(
        client_secret_file=str(secret_file),
        creds_file=str(token_file),
    )


def find_emails(
    query: str | None = None,
    sender: str | None = None,
    subject: str | None = None,
    label: str | None = None,
    unread_only: bool = False,
    max_results: int | None = None,
    client: Gmail | None = None,
) -> list[Message]:
    """Finner e-poster basert på kriterier eller en rå Gmail-søkestreng."""
    if client is None:
        client = get_gmail()

    # Bygg søkestreng automatisk dersom spesifikke filtre sendes inn
    parts: list[str] = []
    if query:
        parts.append(query)
    if sender:
        parts.append(f"from:{sender}")
    if subject:
        parts.append(f'subject:"{subject}"' if " " in subject else f"subject:{subject}")
    if label:
        parts.append(f"label:{label}")
    if unread_only:
        parts.append("is:unread")

    final_query = " ".join(parts) if parts else "label:INBOX"

    return client.get_messages(query=final_query, max_results=max_results)


def find_email(
    query: str | None = None,
    sender: str | None = None,
    subject: str | None = None,
    label: str | None = None,
    unread_only: bool = False,
    client: Gmail | None = None,
) -> Message | None:
    """Finner den nyeste e-posten som matcher kriteriene.

    Returnerer et Message-objekt, eller None hvis ingen ble funnet.
    """
    results = find_emails(
        query=query,
        sender=sender,
        subject=subject,
        label=label,
        unread_only=unread_only,
        max_results=1,
        client=client,
    )
    return results[0] if results else None


class EmailDraft(dict):
    """Wrapper rundt Gmail API sitt utkast-objekt slik at både utkast['id'] og utkast.id fungerer."""

    @property
    def id(self) -> str | None:
        return self.get("id")


def _prepare_email_kwargs(
    to: str | Sequence[str],
    subject: str,
    body_html: str | None = None,
    body_text: str | None = None,
    attachments: Sequence[Path | str] | None = None,
    sender: str = "me",
    cc: Sequence[str] | str | None = None,
    bcc: Sequence[str] | str | None = None,
    signature: bool = False,
    client: Gmail | None = None,
) -> tuple[Gmail, dict[str, Any]]:
    """Forbereder og normaliserer felles parametere og Gmail-klient for sending og utkast."""
    if client is None:
        client = get_gmail()

    to_str = to if isinstance(to, str) else ", ".join(to)
    att_paths = [str(p) for p in attachments] if attachments else None
    cc_list = [cc] if isinstance(cc, str) else list(cc) if cc else None
    bcc_list = [bcc] if isinstance(bcc, str) else list(bcc) if bcc else None

    kwargs: dict[str, Any] = {
        "sender": sender,
        "to": to_str,
        "subject": subject,
        "msg_html": body_html,
        "msg_plain": body_text,
        "attachments": att_paths,
        "cc": cc_list,
        "bcc": bcc_list,
        "signature": signature,
    }
    return client, kwargs


def create_email_draft(
    to: str | Sequence[str],
    subject: str,
    body_html: str | None = None,
    body_text: str | None = None,
    attachments: Sequence[Path | str] | None = None,
    sender: str = "me",
    cc: Sequence[str] | str | None = None,
    bcc: Sequence[str] | str | None = None,
    signature: bool = False,
    client: Gmail | None = None,
) -> EmailDraft:
    """Oppretter et utkast i Gmail.

    Støtter både HTML-kropp, tekst og vedlegg (godtar Path-objekter).
    'sender' er satt til 'me' som standard (din egen Workspace-bruker).
    """
    client, kwargs = _prepare_email_kwargs(
        to=to,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        attachments=attachments,
        sender=sender,
        cc=cc,
        bcc=bcc,
        signature=signature,
        client=client,
    )

    # simplegmail krever 'sender', men tar ikke 'reply_to' på utkast
    draft_dict = client.create_draft(**kwargs)
    return EmailDraft(draft_dict)


def send_email(
    to: str | Sequence[str],
    subject: str,
    body_html: str | None = None,
    body_text: str | None = None,
    attachments: Sequence[Path | str] | None = None,
    sender: str = "me",
    cc: Sequence[str] | str | None = None,
    bcc: Sequence[str] | str | None = None,
    signature: bool = False,
    reply_to: Message | None = None,
    client: Gmail | None = None,
) -> Message:
    """Sender en e-post direkte via Gmail.

    Støtter både HTML-kropp, tekst og vedlegg (godtar Path-objekter).
    'sender' er satt til 'me' som standard (din egen Workspace-bruker).
    'reply_to' kan settes til et Message-objekt for å svare i en eksisterende tråd.
    """
    client, kwargs = _prepare_email_kwargs(
        to=to,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        attachments=attachments,
        sender=sender,
        cc=cc,
        bcc=bcc,
        signature=signature,
        client=client,
    )

    if reply_to is not None:
        kwargs["reply_to"] = reply_to

    return client.send_message(**kwargs)

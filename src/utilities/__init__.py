"""Utilities package."""

from utilities.pdf import convert_to_pdf
from utilities.merge import merge_odt
from utilities.files import get_newest_file
from utilities.qr import generate_qrcode, generate_qrcode_mikaelkirken
from .fnr import fnr_detaljer
from utilities.gmail import create_email_draft, find_emails, find_email, get_gmail

__all__ = [
    "convert_to_pdf",
    "get_newest_file",
    "generate_qrcode",
    "generate_qrcode_mikaelkirken",
    "merge_odt",
    "fnr_detaljer",
    "get_gmail",
    "find_emails",
    "find_email",
    "create_email_draft",
]

"""Utilities package."""

from utilities.pdf import convert_to_pdf
from utilities.merge import merge_odt
from utilities.files import get_newest_file
from utilities.qr import generate_qrcode, generate_qrcode_mikaelkirken
from .fnr import fnr_detaljer

__all__ = [
    "convert_to_pdf",
    "get_newest_file",
    "generate_qrcode",
    "generate_qrcode_mikaelkirken",
    "merge_odt",
    "fnr_detaljer",
]

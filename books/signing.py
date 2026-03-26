"""
Signed, time-limited download tokens for PDF delivery emails.

The token encodes the book ID and is signed with Django's SECRET_KEY.
It can be verified without requiring the user to be logged in, so
email download links work directly.
"""

from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired


_signer = TimestampSigner(salt="pdf-download")


def make_download_token(book_id: int) -> str:
    """Create a signed token encoding the book ID."""
    return _signer.sign(str(book_id))


def verify_download_token(token: str) -> int | None:
    """
    Verify the token and return the book ID, or None if invalid/expired.

    Tokens expire after PDF_LINK_EXPIRY_DAYS (default 7 days).
    """
    max_age = getattr(settings, "PDF_LINK_EXPIRY_DAYS", 7) * 86400
    try:
        value = _signer.unsign(token, max_age=max_age)
        return int(value)
    except (BadSignature, SignatureExpired, ValueError):
        return None

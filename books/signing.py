"""
Signed, time-limited download tokens for PDF delivery emails.

The token encodes the book ID and user ID, signed with Django's SECRET_KEY.
It can be verified without requiring the user to be logged in, so
email download links work directly. The user ID binding prevents tokens
from being used to download other users' PDFs.
"""

from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired


_signer = TimestampSigner(salt="pdf-download")


def make_download_token(book_id: int, user_id: int | None = None) -> str:
    """Create a signed token encoding the book ID and user ID."""
    value = f"{book_id}:{user_id or 0}"
    return _signer.sign(value)


def verify_download_token(token: str) -> tuple[int, int] | None:
    """
    Verify the token and return (book_id, user_id), or None if invalid/expired.

    Tokens expire after PDF_LINK_EXPIRY_DAYS (default 7 days).
    Backwards-compatible: old tokens without user_id return user_id=0.
    """
    max_age = getattr(settings, "PDF_LINK_EXPIRY_DAYS", 7) * 86400
    try:
        value = _signer.unsign(token, max_age=max_age)
        if ":" in value:
            book_id, user_id = value.split(":", 1)
            return int(book_id), int(user_id)
        # Backwards compat: old tokens have only book_id
        return int(value), 0
    except (BadSignature, SignatureExpired, ValueError):
        return None

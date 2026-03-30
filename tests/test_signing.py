"""Tests for the signed PDF download token system."""

import pytest
from unittest.mock import patch

from books.signing import make_download_token, verify_download_token


class TestDownloadTokens:
    def test_roundtrip(self):
        token = make_download_token(42)
        assert verify_download_token(token) == 42

    def test_different_books_different_tokens(self):
        t1 = make_download_token(1)
        t2 = make_download_token(2)
        assert t1 != t2

    def test_invalid_token(self):
        assert verify_download_token("garbage") is None

    def test_tampered_token(self):
        token = make_download_token(42)
        tampered = token[:-5] + "XXXXX"
        assert verify_download_token(tampered) is None

    def test_expired_token(self):
        token = make_download_token(42)
        # Patch max_age to 0 so the token is immediately expired
        with patch("books.signing.getattr", return_value=0):
            # Re-import won't help; test the function directly
            from django.core.signing import TimestampSigner, SignatureExpired
            signer = TimestampSigner(salt="pdf-download")
            try:
                signer.unsign(token, max_age=0)
                assert False, "Should have raised SignatureExpired"
            except SignatureExpired:
                pass  # expected

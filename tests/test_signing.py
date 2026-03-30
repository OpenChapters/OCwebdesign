"""Tests for the signed PDF download token system."""

import pytest
from django.core.signing import TimestampSigner, SignatureExpired

from books.signing import make_download_token, verify_download_token


class TestDownloadTokens:
    def test_roundtrip(self):
        token = make_download_token(42, user_id=7)
        result = verify_download_token(token)
        assert result == (42, 7)

    def test_roundtrip_without_user(self):
        token = make_download_token(42)
        result = verify_download_token(token)
        assert result == (42, 0)

    def test_different_books_different_tokens(self):
        t1 = make_download_token(1, user_id=1)
        t2 = make_download_token(2, user_id=1)
        assert t1 != t2

    def test_different_users_different_tokens(self):
        t1 = make_download_token(1, user_id=1)
        t2 = make_download_token(1, user_id=2)
        assert t1 != t2

    def test_invalid_token(self):
        assert verify_download_token("garbage") is None

    def test_tampered_token(self):
        token = make_download_token(42, user_id=7)
        tampered = token[:-5] + "XXXXX"
        assert verify_download_token(tampered) is None

    def test_expired_token(self):
        token = make_download_token(42, user_id=7)
        signer = TimestampSigner(salt="pdf-download")
        try:
            signer.unsign(token, max_age=0)
            assert False, "Should have raised SignatureExpired"
        except SignatureExpired:
            pass  # expected

"""Tests for verification-code extraction (no live IMAP)."""

from __future__ import annotations

from ats.email_codes import extract_code_with_regex


def test_extract_six_digit_code():
    body = "Your verification code is 482913. It expires in 10 minutes."
    assert extract_code_with_regex(body) == "482913"


def test_extract_code_near_label():
    body = "Please enter this OTP: 7712 to continue."
    assert extract_code_with_regex(body) == "7712"


def test_no_code_returns_none():
    assert extract_code_with_regex("Thanks for applying to ACME.") is None

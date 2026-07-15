"""Unit tests for employer-site account vault and auth-gate heuristics."""

from __future__ import annotations

import json

from ats.accounts import (
    SiteAccount,
    get_or_create_account,
    host_for_url,
    session_path_for_host,
)
from ats.auth_gate import (
    _LOGIN_MARKERS,
    _REGISTER_MARKERS,
    _VERIFY_MARKERS,
)


def test_host_for_url():
    assert host_for_url("https://www.company.myworkdayjobs.com/en-US/job/123") == (
        "company.myworkdayjobs.com"
    )


def test_get_or_create_account_persists(tmp_path, monkeypatch):
    accounts_file = tmp_path / "site_accounts.json"
    monkeypatch.setattr("ats.accounts.ACCOUNTS_PATH", accounts_file)
    monkeypatch.delenv("ATS_ACCOUNT_EMAIL", raising=False)
    monkeypatch.setenv("ATS_SITE_PASSWORD", "TestPass!123")

    acc = get_or_create_account(
        "https://acme.myworkdayjobs.com/en/job/1",
        profile_email="applicant@example.com",
    )
    assert isinstance(acc, SiteAccount)
    assert acc.email == "applicant@example.com"
    assert acc.password == "TestPass!123"
    assert accounts_file.exists()

    raw = json.loads(accounts_file.read_text())
    assert "acme.myworkdayjobs.com" in raw

    again = get_or_create_account(
        "https://acme.myworkdayjobs.com/en/job/2",
        profile_email="other@example.com",
    )
    assert again.email == "applicant@example.com"
    assert again.password == "TestPass!123"


def test_session_path_safe(tmp_path, monkeypatch):
    monkeypatch.setattr("ats.accounts.SESSIONS_DIR", tmp_path)
    path = session_path_for_host("jobs.example.com")
    assert path.name == "jobs.example.com.json"
    assert path.parent == tmp_path


def test_auth_markers_cover_common_copy():
    body = "create an account or sign in to continue"
    assert any(m in body for m in _REGISTER_MARKERS)
    assert any(m in body for m in _LOGIN_MARKERS)
    verify = "please verify your email to continue"
    assert any(m in verify for m in _VERIFY_MARKERS)


def test_account_email_override(monkeypatch):
    from ats.accounts import account_email

    monkeypatch.setenv("ATS_ACCOUNT_EMAIL", "pmochoki@gmail.com")
    assert account_email("other@example.com") == "pmochoki@gmail.com"

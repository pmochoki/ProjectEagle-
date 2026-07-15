"""Per-host employer-site credentials + Playwright session storage.

Credentials live in data/site_accounts.json (gitignored). Sessions live under
data/site_sessions/<host>.json. Never commit these files.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS_PATH = PROJECT_ROOT / "data" / "site_accounts.json"
SESSIONS_DIR = PROJECT_ROOT / "data" / "site_sessions"


@dataclass
class SiteAccount:
    host: str
    email: str
    password: str
    created: bool = False
    notes: str = ""


def _host_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _safe_host_filename(host: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "_", host.lower()) or "unknown"


def auto_register_enabled() -> bool:
    return os.getenv("ATS_AUTO_REGISTER", "true").lower() not in ("0", "false", "no")


def session_path_for_host(host: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{_safe_host_filename(host)}.json"


def session_exists(host: str) -> bool:
    path = session_path_for_host(host)
    return path.exists() and path.stat().st_size > 0


def _load_accounts() -> dict[str, SiteAccount]:
    if not ACCOUNTS_PATH.exists():
        return {}
    try:
        raw = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, SiteAccount] = {}
    for host, entry in (raw or {}).items():
        if not isinstance(entry, dict):
            continue
        out[host] = SiteAccount(
            host=host,
            email=str(entry.get("email") or ""),
            password=str(entry.get("password") or ""),
            created=bool(entry.get("created")),
            notes=str(entry.get("notes") or ""),
        )
    return out


def _save_accounts(accounts: dict[str, SiteAccount]) -> None:
    ACCOUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {host: asdict(acc) for host, acc in accounts.items()}
    ACCOUNTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_password(host: str, email: str) -> str:
    """Stable-ish password when ATS_SITE_PASSWORD is unset (still unique-ish per host)."""
    fixed = os.getenv("ATS_SITE_PASSWORD", "").strip()
    if fixed:
        return fixed
    seed = os.getenv("ATS_SITE_PASSWORD_SEED", "projecteagle").strip() or "projecteagle"
    digest = hashlib.sha256(f"{seed}:{host}:{email}".encode()).hexdigest()[:18]
    # Meet common complexity rules without embedding secrets in source.
    return f"Pe!{digest}9A"


def get_or_create_account(url: str, *, profile_email: str) -> SiteAccount:
    host = _host_from_url(url)
    accounts = _load_accounts()
    if host in accounts and accounts[host].email and accounts[host].password:
        return accounts[host]

    email = (profile_email or "").strip()
    if not email:
        raise ValueError("Profile email required to create a site account")
    account = SiteAccount(
        host=host,
        email=email,
        password=_default_password(host, email),
        created=False,
        notes="auto-provisioned",
    )
    accounts[host] = account
    _save_accounts(accounts)
    return account


def mark_account_created(host: str, *, notes: str = "") -> None:
    accounts = _load_accounts()
    if host not in accounts:
        return
    accounts[host].created = True
    if notes:
        accounts[host].notes = notes
    _save_accounts(accounts)


def generate_ephemeral_password() -> str:
    return f"Pe!{secrets.token_urlsafe(10)}9A"


async def save_site_session(context, host: str) -> Path:
    path = session_path_for_host(host)
    state = await context.storage_state()
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


async def load_site_context(browser, url: str, *, headless: bool = True):
    """Browser context that reuses a saved employer-site session when present."""
    host = _host_from_url(url)
    if session_exists(host):
        return await browser.new_context(storage_state=str(session_path_for_host(host)))
    return await browser.new_context()


def host_for_url(url: str) -> str:
    return _host_from_url(url)

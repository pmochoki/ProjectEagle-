#!/usr/bin/env bash
# Idempotent Cloud Agent dependency setup for Jantasearcher / ProjectEagle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Jantasearcher cloud install (root: $ROOT)"

# Python backend venv + deps
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
playwright install chromium

# Frontend deps
cd frontend
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
cd "$ROOT"

# Applicant profile (gitignored locally; required for tailoring/apply)
if [ ! -f data/profile.json ]; then
  cp data/profile.example.json data/profile.json
  echo "==> Created data/profile.json from example — fill with real details via agent task."
fi

# .env for runtime (secrets come from Cursor Cloud Secrets as env vars)
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from example — values are injected from Cloud Agent Secrets."
fi

echo "==> Cloud install complete."

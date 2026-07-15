# Employer-site apply automation
#
# Flow per job:
# 1. Claude writes cover letter + tailored resume from data/profile.json (no fabrication)
# 2. If the ATS needs an account (Workday / SmartRecruiters), ProjectEagle can
#    auto-register using your profile email + a vaulted password (ATS_AUTO_REGISTER)
# 3. Upload CV + fill cover letter / contact fields
# 4. Pause for Telegram /approve when REVIEW_BEFORE_SUBMIT=true (default)
# 5. If a verification code is emailed: IMAP reads the inbox, Claude extracts the OTP,
#    and ProjectEagle fills it in (Gmail App Password recommended for EMAIL_IMAP_PASSWORD)
#
# Hard limits:
# - No CAPTCHA bypass — solve on your phone, then retry
# - Session cookies saved under data/site_sessions/ (gitignored)
# - Passwords in data/site_accounts.json / .env (gitignored) — never commit secrets

## Platforms
- greenhouse, lever — guest forms (preferred)
- workday, smartrecruiters — register/login + apply when possible

## Env
```
ATS_AUTO_REGISTER=true
ATS_ACCOUNT_EMAIL=you@example.com
ATS_SITE_PASSWORD=  # employer-site password (hidden in secrets)
REVIEW_BEFORE_SUBMIT=true
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_USER=you@example.com
EMAIL_IMAP_PASSWORD=  # Gmail App Password preferred
CLAUDE_API_KEY=
```

# Employer-site apply automation
#
# Flow per job:
# 1. Claude writes cover letter + tailored resume from data/profile.json (no fabrication)
# 2. If the ATS needs an account (Workday / SmartRecruiters), ProjectEagle can
#    auto-register using your profile email + a vaulted password (ATS_AUTO_REGISTER)
# 3. Upload CV + fill cover letter / contact fields
# 4. Pause for Telegram /approve when REVIEW_BEFORE_SUBMIT=true (default)
#
# Hard limits:
# - No CAPTCHA bypass — solve on your phone, then retry
# - Email verification is manual (Telegram alerts you)
# - Session cookies saved under data/site_sessions/ (gitignored)
# - Passwords in data/site_accounts.json (gitignored)

## Platforms
- greenhouse, lever — guest forms (preferred)
- workday, smartrecruiters — register/login + apply when possible

## Env
```
ATS_AUTO_REGISTER=true
REVIEW_BEFORE_SUBMIT=true
# ATS_SITE_PASSWORD=   # optional shared password for all site accounts
```

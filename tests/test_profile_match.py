from __future__ import annotations

from scraper.profile_match import compute_profile_match
from scraper.sponsorship import applicant_needs_sponsorship, detect_sponsorship


def test_detect_sponsorship_offered():
    text = "We offer visa sponsorship for the right candidate."
    result = detect_sponsorship(text)
    assert result["sponsorship_offered"] is True
    assert result["sponsorship_status"] == "offered"


def test_detect_sponsorship_denied():
    text = "Must have right to work in the EU. No visa sponsorship."
    result = detect_sponsorship(text)
    assert result["sponsorship_offered"] is False
    assert result["sponsorship_status"] == "not_offered"


def test_profile_match_with_skills():
    profile = {
        "contact": {"full_name": "Test", "email": "t@example.com"},
        "summary": "Mechatronics graduate",
        "skills": {"programming": ["Python", "PLC programming"], "control_systems": ["PID tuning"]},
        "experience": [{"role": "Automation Engineer", "company": "ACME", "start_date": "2024-01", "bullets": ["Built robots"]}],
        "projects": [],
        "education": [{"institution": "Uni", "degree": "BSc", "field": "Mechatronics Engineering"}],
        "preferences": {"needs_visa_sponsorship": True},
    }
    score, reasons, meta = compute_profile_match(
        profile,
        title="Graduate Mechatronics Engineer",
        location="Budapest, Hungary",
        description="Python and PLC programming for robotics automation. Visa sponsorship available.",
        ats_platform="greenhouse",
    )
    assert score >= 50
    assert any("Skills" in r for r in reasons)
    assert meta["sponsorship_offered"] is True


def test_profile_match_penalizes_no_sponsorship():
    profile = {
        "contact": {"full_name": "Test", "email": "t@example.com"},
        "summary": "Mechatronics",
        "skills": {"programming": ["Python"]},
        "experience": [],
        "projects": [],
        "education": [],
        "preferences": {"needs_visa_sponsorship": True},
    }
    score_with, _, _ = compute_profile_match(
        profile,
        title="Engineer",
        location="Germany",
        description="Python mechatronics role. Visa sponsorship offered.",
    )
    score_without, reasons, _ = compute_profile_match(
        profile,
        title="Engineer",
        location="Germany",
        description="Python mechatronics role. Must have right to work. No visa sponsorship.",
    )
    assert score_with > score_without
    assert applicant_needs_sponsorship(profile) is True
    assert any("No visa sponsorship" in r for r in reasons)

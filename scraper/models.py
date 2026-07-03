from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScrapedJob:
    title: str
    company: str
    location: str
    description: str
    linkedin_url: str
    external_apply_url: str
    is_easy_apply: bool

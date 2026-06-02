from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScrapedJob:
    title: str
    company: str
    location: str
    description: str
    apply_url: str
    is_easy_apply: bool


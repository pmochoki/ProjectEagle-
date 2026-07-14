from __future__ import annotations


def is_relevant_listing(
    *,
    title: str,
    description: str,
    keywords: tuple[str, ...],
    opportunity_type: str | None = None,
) -> bool:
    """Keep listings that match profile-related keywords (jobs + scholarships)."""
    if not keywords:
        return True

    haystack = f"{title}\n{description}".lower()
    if opportunity_type == "scholarship":
        scholarship_terms = (
            "scholarship",
            "stipend",
            "funding",
            "grant",
            "master",
            "masters",
            "msc",
            "m.sc",
            "phd",
            "graduate",
            "erasmus",
            "daad",
            "stipendium",
            "tuition",
            "fellowship",
        )
        if any(term in haystack for term in scholarship_terms):
            return True

    return any(keyword.lower() in haystack for keyword in keywords)

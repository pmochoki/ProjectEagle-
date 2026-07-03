from __future__ import annotations

import asyncio
from dataclasses import dataclass

from playwright.async_api import async_playwright

from notifications.telegram import notify_canary_failure, notify_canary_ok
from scraper.config import ScraperConfig


@dataclass
class CanaryResult:
    scraper: str
    ok: bool
    message: str


LINKEDIN_CHECKS = [
    ("job list cards", "li.scaffold-layout__list-item"),
    ("job title", ".job-details-jobs-unified-top-card__job-title"),
    ("company name", ".job-details-jobs-unified-top-card__company-name"),
]

PROFESSION_CHECKS = [
    ("job cards", "div.list.main_category"),
    ("job title link", "h2 a"),
]


async def _run_checks(
    *,
    name: str,
    url: str,
    checks: list[tuple[str, str]],
    headless: bool,
) -> CanaryResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            failures: list[str] = []
            for label, selector in checks:
                if await page.locator(selector).count() == 0:
                    failures.append(f"{label} ({selector})")
            if failures:
                msg = f"{name} canary failed: missing {', '.join(failures)}"
                return CanaryResult(scraper=name, ok=False, message=msg)
            return CanaryResult(scraper=name, ok=True, message=f"{name} canary passed")
        except Exception as exc:
            return CanaryResult(scraper=name, ok=False, message=f"{name} canary error: {exc}")
        finally:
            await browser.close()


async def run_linkedin_canary(cfg: ScraperConfig) -> CanaryResult:
    from urllib.parse import quote_plus

    keywords = quote_plus(cfg.job_title)
    location = quote_plus(cfg.location)
    url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"
    return await _run_checks(
        name="linkedin",
        url=url,
        checks=LINKEDIN_CHECKS,
        headless=cfg.headless,
    )


async def run_profession_canary(cfg: ScraperConfig) -> CanaryResult:
    from urllib.parse import quote_plus

    q = quote_plus(cfg.job_title)
    url = f"https://www.profession.hu/allasok/{q}"
    return await _run_checks(
        name="profession_hu",
        url=url,
        checks=PROFESSION_CHECKS,
        headless=cfg.headless,
    )


async def run_all_canaries(cfg: ScraperConfig) -> list[CanaryResult]:
    results = await asyncio.gather(
        run_linkedin_canary(cfg),
        run_profession_canary(cfg),
    )
    for result in results:
        if result.ok:
            notify_canary_ok(result.scraper, result.message)
        else:
            notify_canary_failure(result.scraper, result.message)
    return list(results)


def run_all_canaries_sync(cfg: ScraperConfig) -> list[dict]:
    results = asyncio.run(run_all_canaries(cfg))
    return [{"scraper": r.scraper, "ok": r.ok, "message": r.message} for r in results]

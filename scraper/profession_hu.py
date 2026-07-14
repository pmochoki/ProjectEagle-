from __future__ import annotations

import asyncio
import random
import re
from dataclasses import asdict, dataclass
from urllib.parse import quote_plus, urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from database.jobs import insert_job_if_new
from database.models import JobInsert, detect_ats_platform
from notifications.telegram import notify_new_jobs, notify_scrape_complete
from scraper.config import ScraperConfig


@dataclass
class ProfessionScrapeResult:
    found: int
    inserted: int
    pages_visited: int
    message: str


async def _human_delay(cfg: ScraperConfig) -> None:
    await asyncio.sleep(random.uniform(cfg.delay_min_seconds, cfg.delay_max_seconds))


def _parse_posted_date(text: str):
    """Best-effort parse of HU posting hints; returns ISO date string or None."""
    from datetime import date, timedelta

    t = text.lower().strip()
    today = date.today()
    if "ma" in t or "today" in t:
        return today.isoformat()
    m = re.search(r"(\d+)\s*(nap|day)", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s*(hét|week)", t)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).isoformat()
    return None


async def _scrape_page(page, cfg: ScraperConfig) -> list[dict]:
    await page.wait_for_timeout(1500)
    cards = page.locator("div.list.main_category, article.job-card, li.list_adv")
    count = await cards.count()
    jobs: list[dict] = []

    for idx in range(count):
        card = cards.nth(idx)
        try:
            title_el = card.locator("h2 a, a.position_and_company, a[href*='/allas/']").first
            if await title_el.count() == 0:
                continue
            title = (await title_el.inner_text(timeout=2000)).strip()
            href = await title_el.get_attribute("href")
            if not href:
                continue
            detail_url = urljoin("https://www.profession.hu", href)

            company_el = card.locator(".company, .position_and_company span, .adv_ceg")
            company = (
                (await company_el.first.inner_text(timeout=1500)).strip()
                if await company_el.count()
                else "Unknown company"
            )

            location_el = card.locator(".location, .adv_hely")
            location = (
                (await location_el.first.inner_text(timeout=1500)).strip()
                if await location_el.count()
                else cfg.location
            )

            date_el = card.locator(".date, .adv_date, time")
            posted_raw = (
                (await date_el.first.inner_text(timeout=1000)).strip()
                if await date_el.count()
                else ""
            )

            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "detail_url": detail_url,
                    "posted_raw": posted_raw,
                }
            )
        except PlaywrightTimeoutError:
            continue
    return jobs


async def _fetch_detail(page, detail_url: str) -> tuple[str, str]:
    """Return (description, external_apply_url)."""
    await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1200)

    desc_el = page.locator(
        ".job-text, .job_description, .adv_body, [class*='description']"
    )
    description = (
        (await desc_el.first.inner_text(timeout=2000)).strip()
        if await desc_el.count()
        else ""
    )

    apply_el = page.locator(
        "a[href*='greenhouse'], a[href*='lever'], a[href*='apply'], "
        "a.btn-primary[href^='http'], a[href*='karrier']"
    )
    external_url = detail_url
    for i in range(await apply_el.count()):
        href = await apply_el.nth(i).get_attribute("href")
        if href and href.startswith("http"):
            if any(x in href.lower() for x in ("greenhouse", "lever", "apply", "karrier")):
                external_url = href.strip()
                break

    return description, external_url


async def run_profession_scraper(cfg: ScraperConfig) -> ProfessionScrapeResult:
    cfg.validate_scrape_only()
    inserted = 0
    found_jobs: list[JobInsert] = []
    pages_visited = 0

    q = quote_plus(cfg.job_title)
    base_url = f"https://www.profession.hu/allasok/{q}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, slow_mo=75)
        page = await browser.new_page()

        for page_num in range(1, cfg.max_pages + 1):
            pages_visited += 1
            url = base_url if page_num == 1 else f"{base_url}?page={page_num}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _human_delay(cfg)

            listings = await _scrape_page(page, cfg)
            for listing in listings:
                description, external_url = await _fetch_detail(page, listing["detail_url"])
                await _human_delay(cfg)

                posted = _parse_posted_date(listing.get("posted_raw", ""))
                from datetime import date as date_cls

                posted_date = date_cls.fromisoformat(posted) if posted else None

                from scraper.relevance import is_relevant_listing

                if not is_relevant_listing(
                    title=listing["title"],
                    description=description,
                    keywords=cfg.relevance_keywords,
                ):
                    continue

                job = JobInsert(
                    source="profession_hu",
                    title=listing["title"],
                    company=listing["company"],
                    external_url=external_url,
                    location=listing["location"],
                    description=description,
                    posted_date=posted_date,
                    ats_platform=detect_ats_platform(external_url),
                    metadata={"profession_url": listing["detail_url"]},
                )
                found_jobs.append(job)
                record, outcome = insert_job_if_new(job)
                if outcome == "inserted":
                    inserted += 1

            next_btn = page.locator("a[rel='next'], a.pagination-next")
            if await next_btn.count() == 0:
                break
            try:
                await next_btn.first.click(timeout=3000)
            except PlaywrightTimeoutError:
                break

        await browser.close()

    notify_scrape_complete(
        found=len(found_jobs),
        inserted=inserted,
        skipped_easy_apply=0,
        captcha=False,
        source="profession.hu",
    )
    if found_jobs:
        notify_new_jobs(
            [
                {
                    "title": j.title,
                    "company": j.company,
                    "external_apply_url": j.external_url,
                }
                for j in found_jobs[:10]
            ]
        )

    return ProfessionScrapeResult(
        found=len(found_jobs),
        inserted=inserted,
        pages_visited=pages_visited,
        message=f"Profession.hu scrape done. {inserted} new jobs saved.",
    )


def run_profession_scraper_sync(cfg: ScraperConfig) -> dict:
    return asdict(asyncio.run(run_profession_scraper(cfg)))

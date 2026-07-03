from __future__ import annotations

import asyncio
import random
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from urllib.parse import quote_plus

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from database.jobs import save_scraped_jobs
from notifications.telegram import notify_new_jobs, notify_scrape_complete
from scraper.config import ScraperConfig
from scraper.models import ScrapedJob
from scraper.session import load_session_context, save_session


@dataclass
class ScrapeResult:
    found: int
    inserted: int
    skipped_easy_apply: int
    captcha_detected: bool
    pages_visited: int
    message: str
    public_mode: bool


async def _human_delay(cfg: ScraperConfig) -> None:
    await asyncio.sleep(random.uniform(cfg.delay_min_seconds, cfg.delay_max_seconds))


def _date_posted_filter(code: str) -> str:
    """LinkedIn f_TPR filter codes."""
    mapping = {
        "past_24_hours": "r86400",
        "past_week": "r604800",
        "past_month": "r2592000",
        "any": "",
    }
    return mapping.get(code, "r604800")


def _experience_filter(code: str) -> str:
    mapping = {
        "internship": "1",
        "entry": "2",
        "associate": "3",
        "mid": "4",
        "director": "5",
        "executive": "6",
    }
    return mapping.get(code, "")


def _build_search_url(cfg: ScraperConfig) -> str:
    keywords = quote_plus(cfg.job_title)
    location = quote_plus(cfg.location)
    parts = [
        "https://www.linkedin.com/jobs/search/?",
        f"keywords={keywords}&location={location}",
    ]
    tpr = _date_posted_filter(cfg.date_posted)
    if tpr:
        parts.append(f"&f_TPR={tpr}")
    exp = _experience_filter(cfg.experience_level)
    if exp:
        parts.append(f"&f_E={exp}")
    return "".join(parts)


async def _detect_captcha(page) -> bool:
    body_text = (await page.content()).lower()
    return (
        "captcha" in body_text
        or "security verification" in body_text
        or "let's do a quick security check" in body_text
    )


def _parse_relative_posted(text: str) -> date | None:
    t = text.lower()
    today = date.today()
    if "just now" in t or "today" in t:
        return today
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)", t)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "minute" or unit == "hour":
        return today
    if unit == "day":
        return today - timedelta(days=n)
    if unit == "week":
        return today - timedelta(weeks=n)
    if unit == "month":
        return today - timedelta(days=n * 30)
    return None


async def _extract_posted_date(page) -> date | None:
    selectors = [
        ".job-details-jobs-unified-top-card__primary-description-container",
        ".job-details-jobs-unified-top-card__bullet",
        "span.posted-time-ago__text",
    ]
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count() == 0:
            continue
        text = (await loc.first.inner_text(timeout=1500)).strip()
        parsed = _parse_relative_posted(text)
        if parsed:
            return parsed
    return None


async def _extract_external_apply_url(page) -> str:
    selectors = [
        "a[data-tracking-control-name='public_jobs_apply-link-offsite']",
        "a.jobs-apply-button[href^='http']",
        ".jobs-apply-button--top-card a[href^='http']",
        "a[aria-label*='Apply on company website']",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if await locator.count() > 0:
            href = await locator.get_attribute("href")
            if href and href.startswith("http") and "linkedin.com" not in href:
                return href.strip()
    return ""


async def _extract_jobs_on_page(page) -> tuple[list[ScrapedJob], int]:
    await page.wait_for_timeout(1500)
    cards = page.locator("li.scaffold-layout__list-item")
    count = await cards.count()
    jobs: list[ScrapedJob] = []
    skipped_easy_apply = 0

    for idx in range(count):
        card = cards.nth(idx)
        try:
            await card.scroll_into_view_if_needed(timeout=3000)
            await card.click(timeout=3000)
        except PlaywrightTimeoutError:
            continue

        await page.wait_for_timeout(1200)

        easy_apply_button = page.get_by_role("button", name="Easy Apply")
        if await easy_apply_button.count() > 0:
            skipped_easy_apply += 1
            continue

        title_locator = page.locator(".job-details-jobs-unified-top-card__job-title")
        title = (
            (await title_locator.inner_text(timeout=2000)).strip()
            if await title_locator.count()
            else "Unknown role"
        )

        company_locator = page.locator(
            ".job-details-jobs-unified-top-card__company-name a, "
            ".job-details-jobs-unified-top-card__company-name"
        )
        company = (
            (await company_locator.first.inner_text(timeout=2000)).strip()
            if await company_locator.count()
            else "Unknown company"
        )

        location_locator = page.locator(".job-details-jobs-unified-top-card__bullet")
        location = (
            (await location_locator.first.inner_text(timeout=2000)).strip()
            if await location_locator.count()
            else "Unknown location"
        )

        description_locator = page.locator("#job-details")
        description = (
            (await description_locator.inner_text(timeout=2000)).strip()
            if await description_locator.count()
            else ""
        )

        posted_date = await _extract_posted_date(page)
        linkedin_url = page.url
        external_apply_url = await _extract_external_apply_url(page)

        if not external_apply_url:
            skipped_easy_apply += 1
            continue

        jobs.append(
            ScrapedJob(
                title=title,
                company=company,
                location=location,
                description=description,
                linkedin_url=linkedin_url,
                external_apply_url=external_apply_url,
                is_easy_apply=False,
                posted_date=posted_date,
            )
        )
    return jobs, skipped_easy_apply


async def _login_if_needed(page, cfg: ScraperConfig) -> bool:
    """Returns False if CAPTCHA blocked login."""
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    await _human_delay(cfg)

    if await page.locator("#username").count() == 0:
        return True

    await page.fill("#username", cfg.linkedin_email)
    await _human_delay(cfg)
    await page.fill("#password", cfg.linkedin_password)
    await _human_delay(cfg)
    await page.click("button[type='submit']")
    await page.wait_for_load_state("domcontentloaded")
    await _human_delay(cfg)
    return not await _detect_captcha(page)


async def run_scraper(cfg: ScraperConfig) -> ScrapeResult:
    cfg.validate()

    found_jobs: list[ScrapedJob] = []
    skipped_easy_apply = 0
    captcha_detected = False
    pages_visited = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, slow_mo=75)
        context = await load_session_context(browser, headless=cfg.headless)
        page = await context.new_page()

        if cfg.public_mode:
            await page.goto(_build_search_url(cfg), wait_until="domcontentloaded")
            await _human_delay(cfg)
        else:
            logged_in = await _login_if_needed(page, cfg)
            if not logged_in:
                await browser.close()
                return ScrapeResult(
                    found=0,
                    inserted=0,
                    skipped_easy_apply=0,
                    captcha_detected=True,
                    pages_visited=0,
                    message="CAPTCHA detected during login; scraper paused.",
                    public_mode=False,
                )
            await save_session(context)
            await page.goto(_build_search_url(cfg), wait_until="domcontentloaded")

        for _ in range(cfg.max_pages):
            pages_visited += 1
            if await _detect_captcha(page):
                captcha_detected = True
                break

            jobs, skipped = await _extract_jobs_on_page(page)
            found_jobs.extend(jobs)
            skipped_easy_apply += skipped

            next_button = page.get_by_role("button", name="View next page")
            if await next_button.count() == 0:
                break

            try:
                await _human_delay(cfg)
                await next_button.click(timeout=4000)
                await page.wait_for_load_state("domcontentloaded")
            except PlaywrightTimeoutError:
                break

        if not cfg.public_mode:
            await save_session(context)
        await browser.close()

    inserted = save_scraped_jobs(found_jobs)
    msg = f"Scrape completed. {inserted} new external-apply jobs saved."
    if captcha_detected:
        msg = "CAPTCHA detected; run paused and partial results saved. Solve manually in browser, then retry."

    notify_scrape_complete(
        found=len(found_jobs),
        inserted=inserted,
        skipped_easy_apply=skipped_easy_apply,
        captcha=captcha_detected,
        source="LinkedIn",
    )
    if found_jobs:
        notify_new_jobs(found_jobs[:10])

    return ScrapeResult(
        found=len(found_jobs),
        inserted=inserted,
        skipped_easy_apply=skipped_easy_apply,
        captcha_detected=captcha_detected,
        pages_visited=pages_visited,
        message=msg,
        public_mode=cfg.public_mode,
    )


def run_scraper_sync(cfg: ScraperConfig) -> dict:
    result = asyncio.run(run_scraper(cfg))
    return asdict(result)

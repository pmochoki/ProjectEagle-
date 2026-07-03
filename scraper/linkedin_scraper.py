from __future__ import annotations

import asyncio
import random
from dataclasses import asdict, dataclass
from urllib.parse import quote_plus

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from database.jobs import save_scraped_jobs
from notifications.telegram import notify_new_jobs, notify_scrape_complete
from scraper.config import ScraperConfig
from scraper.models import ScrapedJob


@dataclass
class ScrapeResult:
    found: int
    inserted: int
    skipped_easy_apply: int
    captcha_detected: bool
    pages_visited: int
    message: str


async def _human_delay(cfg: ScraperConfig) -> None:
    await asyncio.sleep(random.uniform(cfg.delay_min_seconds, cfg.delay_max_seconds))


def _build_search_url(cfg: ScraperConfig) -> str:
    keywords = quote_plus(cfg.job_title)
    location = quote_plus(cfg.location)
    # No f_AL filter — we want all jobs, then keep external-apply only.
    return (
        "https://www.linkedin.com/jobs/search/?"
        f"keywords={keywords}&location={location}"
    )


async def _detect_captcha(page) -> bool:
    body_text = (await page.content()).lower()
    return (
        "captcha" in body_text
        or "security verification" in body_text
        or "let's do a quick security check" in body_text
    )


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
            )
        )
    return jobs, skipped_easy_apply


async def run_scraper(cfg: ScraperConfig) -> ScrapeResult:
    cfg.validate()

    found_jobs: list[ScrapedJob] = []
    skipped_easy_apply = 0
    captcha_detected = False
    pages_visited = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, slow_mo=75)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await _human_delay(cfg)

        await page.fill("#username", cfg.linkedin_email)
        await _human_delay(cfg)
        await page.fill("#password", cfg.linkedin_password)
        await _human_delay(cfg)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("domcontentloaded")
        await _human_delay(cfg)

        if await _detect_captcha(page):
            await browser.close()
            return ScrapeResult(
                found=0,
                inserted=0,
                skipped_easy_apply=0,
                captcha_detected=True,
                pages_visited=0,
                message="CAPTCHA detected during login; scraper paused.",
            )

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

        await browser.close()

    inserted = save_scraped_jobs(found_jobs)
    msg = f"Scrape completed. {inserted} new external-apply jobs saved."
    if captcha_detected:
        msg = "CAPTCHA detected; run paused and partial results saved."

    notify_scrape_complete(
        found=len(found_jobs),
        inserted=inserted,
        skipped_easy_apply=skipped_easy_apply,
        captcha=captcha_detected,
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
    )


def run_scraper_sync(cfg: ScraperConfig) -> dict:
    result = asyncio.run(run_scraper(cfg))
    return asdict(result)

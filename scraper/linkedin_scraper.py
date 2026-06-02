from __future__ import annotations

import asyncio
import random
from dataclasses import asdict, dataclass
from urllib.parse import quote_plus

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from scraper.config import ScraperConfig
from scraper.db import init_db, save_jobs
from scraper.models import ScrapedJob


@dataclass
class ScrapeResult:
    found: int
    inserted: int
    captcha_detected: bool
    pages_visited: int
    message: str


async def _human_delay(cfg: ScraperConfig) -> None:
    await asyncio.sleep(random.uniform(cfg.delay_min_seconds, cfg.delay_max_seconds))


def _build_search_url(cfg: ScraperConfig) -> str:
    keywords = quote_plus(cfg.job_title)
    location = quote_plus(cfg.location)
    # Date/experience filters are intentionally lightweight in v1.
    return (
        "https://www.linkedin.com/jobs/search/?"
        f"keywords={keywords}&location={location}&f_AL=true"
    )


async def _detect_captcha(page) -> bool:
    body_text = (await page.content()).lower()
    return (
        "captcha" in body_text
        or "security verification" in body_text
        or "let's do a quick security check" in body_text
    )


async def _extract_jobs_on_page(page) -> list[ScrapedJob]:
    await page.wait_for_timeout(1500)
    cards = page.locator("li.scaffold-layout__list-item")
    count = await cards.count()
    jobs: list[ScrapedJob] = []

    for idx in range(count):
        card = cards.nth(idx)
        try:
            await card.scroll_into_view_if_needed(timeout=3000)
            await card.click(timeout=3000)
        except PlaywrightTimeoutError:
            continue

        await page.wait_for_timeout(1200)
        title = (await page.locator(".job-details-jobs-unified-top-card__job-title").inner_text(timeout=2000)).strip() if await page.locator(".job-details-jobs-unified-top-card__job-title").count() else "Unknown role"
        company = (await page.locator(".job-details-jobs-unified-top-card__company-name a, .job-details-jobs-unified-top-card__company-name").first.inner_text(timeout=2000)).strip() if await page.locator(".job-details-jobs-unified-top-card__company-name").count() else "Unknown company"
        location = (await page.locator(".job-details-jobs-unified-top-card__bullet").first.inner_text(timeout=2000)).strip() if await page.locator(".job-details-jobs-unified-top-card__bullet").count() else "Unknown location"
        description = (await page.locator("#job-details").inner_text(timeout=2000)).strip() if await page.locator("#job-details").count() else ""

        easy_apply_button = page.get_by_role("button", name="Easy Apply")
        is_easy_apply = await easy_apply_button.count() > 0
        apply_url = page.url

        jobs.append(
            ScrapedJob(
                title=title,
                company=company,
                location=location,
                description=description,
                apply_url=apply_url,
                is_easy_apply=is_easy_apply,
            )
        )
    return jobs


async def run_scraper(cfg: ScraperConfig) -> ScrapeResult:
    cfg.validate()
    init_db()

    found_jobs: list[ScrapedJob] = []
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

            jobs = await _extract_jobs_on_page(page)
            found_jobs.extend(jobs)

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

    inserted = save_jobs(found_jobs)
    msg = "Scrape completed."
    if captcha_detected:
        msg = "CAPTCHA detected; run paused and partial results saved."
    return ScrapeResult(
        found=len(found_jobs),
        inserted=inserted,
        captcha_detected=captcha_detected,
        pages_visited=pages_visited,
        message=msg,
    )


def run_scraper_sync(cfg: ScraperConfig) -> dict:
    result = asyncio.run(run_scraper(cfg))
    return asdict(result)


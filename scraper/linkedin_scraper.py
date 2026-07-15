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
from notifications.telegram import (
    notify_linkedin_auth_issue,
    notify_new_jobs,
    notify_scrape_complete,
)
from scraper.config import ScraperConfig
from scraper.linkedin_page import (
    detect_account_restricted,
    detect_captcha,
    session_looks_authenticated,
)
from scraper.models import ScrapedJob
from scraper.session import clear_session, load_session_context, save_session


@dataclass
class ScrapeResult:
    found: int
    inserted: int
    skipped_easy_apply: int
    captcha_detected: bool
    pages_visited: int
    message: str
    public_mode: bool
    auth_blocked: bool = False
    search_location: str = ""
    search_title: str = ""


async def _human_delay(cfg: ScraperConfig, *, failure_multiplier: int = 0) -> None:
    from scraper.backoff import scale_delay_max

    delay_max = scale_delay_max(float(cfg.delay_max_seconds), failure_multiplier)
    await asyncio.sleep(random.uniform(cfg.delay_min_seconds, delay_max))


async def _detect_captcha(page) -> bool:
    return await detect_captcha(page)


def _date_posted_filter(code: str) -> str:
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
    if unit in ("minute", "hour"):
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


async def _extract_jobs_on_page(
    page,
    cfg: ScraperConfig,
    *,
    require_external_apply: bool,
    source: str,
    opportunity_type: str | None,
) -> tuple[list[ScrapedJob], int]:
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

        if cfg.location_is_excluded(location):
            skipped_easy_apply += 1
            continue

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
            if require_external_apply:
                skipped_easy_apply += 1
                continue
            external_apply_url = linkedin_url

        metadata: dict = {"linkedin_url": linkedin_url}
        if opportunity_type:
            metadata["opportunity_type"] = opportunity_type
        if cfg.location:
            metadata["search_location"] = cfg.location
        if cfg.job_title:
            metadata["search_title"] = cfg.job_title

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
                source=source,
                metadata=metadata,
            )
        )
    return jobs, skipped_easy_apply


async def _login_if_needed(page, cfg: ScraperConfig, *, failures: int = 0) -> tuple[bool, str]:
    """Returns (ok, reason). reason is empty when ok."""
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    await _human_delay(cfg, failure_multiplier=failures)

    if await detect_account_restricted(page):
        clear_session()
        return False, "account_restricted"

    if await _detect_captcha(page):
        return False, "captcha"

    if await session_looks_authenticated(page):
        return True, ""

    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    await _human_delay(cfg, failure_multiplier=failures)

    # Restriction banner often appears on the login screen — do not submit credentials.
    if await detect_account_restricted(page):
        clear_session()
        return False, "account_restricted"

    if await session_looks_authenticated(page):
        return True, ""

    if await page.locator("#username").count() == 0:
        if "feed" in page.url or "jobs" in page.url:
            return True, ""
        return False, "login_failed"

    if not cfg.linkedin_email or not cfg.linkedin_password:
        return False, "bad_credentials"

    await page.fill("#username", cfg.linkedin_email)
    await _human_delay(cfg, failure_multiplier=failures)
    await page.fill("#password", cfg.linkedin_password)
    await _human_delay(cfg, failure_multiplier=failures)
    await page.click("button[type='submit']")
    await page.wait_for_load_state("domcontentloaded")
    await _human_delay(cfg, failure_multiplier=failures)

    if await detect_account_restricted(page):
        clear_session()
        return False, "account_restricted"

    if await _detect_captcha(page):
        return False, "captcha"

    if await page.locator("#username").count() > 0:
        if await detect_account_restricted(page):
            clear_session()
            return False, "account_restricted"
        error_loc = page.locator("#error-for-password, .form__label--error, [data-test-id='login-error']")
        if await error_loc.count() > 0:
            clear_session()
            return False, "bad_credentials"
        return False, "login_failed"

    if "checkpoint" in page.url.lower() or "challenge" in page.url.lower():
        return False, "verification_required"

    return True, ""


async def run_scraper(
    cfg: ScraperConfig,
    *,
    require_external_apply: bool = True,
    source: str = "linkedin",
    opportunity_type: str | None = None,
) -> ScrapeResult:
    cfg.validate()

    from automation.state import AutomationState
    from scraper.linkedin_auth import clear_linkedin_auth_block, record_linkedin_auth_failure

    state = AutomationState.load()
    if getattr(state, "linkedin_account_restricted", False) and not cfg.public_mode:
        notify_linkedin_auth_issue(
            reason="account_restricted",
            search_title=cfg.job_title,
            search_location=cfg.location,
        )
        return ScrapeResult(
            found=0,
            inserted=0,
            skipped_easy_apply=0,
            captcha_detected=False,
            pages_visited=0,
            message=(
                "LinkedIn account restricted — logged-in scrape stopped. "
                "Set SCRAPER_PUBLIC_MODE=true or LINKEDIN_ENABLED=false."
            ),
            public_mode=False,
            auth_blocked=True,
            search_location=cfg.location,
            search_title=cfg.job_title,
        )

    failures = state.linkedin_auth_failures

    found_jobs: list[ScrapedJob] = []
    skipped_easy_apply = 0
    captcha_detected = False
    auth_blocked = False
    pages_visited = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, slow_mo=75)
        context = await load_session_context(browser, headless=cfg.headless)
        page = await context.new_page()

        if cfg.public_mode:
            await page.goto(_build_search_url(cfg), wait_until="domcontentloaded")
            await _human_delay(cfg, failure_multiplier=failures)
        else:
            logged_in, reason = await _login_if_needed(page, cfg, failures=failures)
            if not logged_in:
                auth_blocked = True
                captcha_detected = reason == "captcha"
                if reason == "bad_credentials":
                    clear_session()
                record_linkedin_auth_failure(state, reason)
                state.save()
                notify_linkedin_auth_issue(
                    reason=reason,
                    search_title=cfg.job_title,
                    search_location=cfg.location,
                )
                await browser.close()
                return ScrapeResult(
                    found=0,
                    inserted=0,
                    skipped_easy_apply=0,
                    captcha_detected=captcha_detected,
                    pages_visited=0,
                    message=f"LinkedIn auth blocked ({reason}). Check Telegram for steps.",
                    public_mode=False,
                    auth_blocked=True,
                    search_location=cfg.location,
                    search_title=cfg.job_title,
                )
            await save_session(context)
            await page.goto(_build_search_url(cfg), wait_until="domcontentloaded")

        for _ in range(cfg.max_pages):
            pages_visited += 1
            if await _detect_captcha(page):
                if not cfg.public_mode:
                    clear_session()
                    logged_in, reason = await _login_if_needed(page, cfg, failures=failures + 1)
                    if logged_in:
                        await save_session(context)
                        await page.goto(_build_search_url(cfg), wait_until="domcontentloaded")
                        continue
                captcha_detected = True
                auth_blocked = True
                record_linkedin_auth_failure(state, "captcha")
                state.save()
                notify_linkedin_auth_issue(
                    reason="captcha",
                    search_title=cfg.job_title,
                    search_location=cfg.location,
                )
                break

            jobs, skipped = await _extract_jobs_on_page(
                page,
                cfg,
                require_external_apply=require_external_apply,
                source=source,
                opportunity_type=opportunity_type,
            )
            found_jobs.extend(jobs)
            skipped_easy_apply += skipped

            next_button = page.get_by_role("button", name="View next page")
            if await next_button.count() == 0:
                break

            try:
                await _human_delay(cfg, failure_multiplier=failures)
                await next_button.click(timeout=4000)
                await page.wait_for_load_state("domcontentloaded")
            except PlaywrightTimeoutError:
                break

        if not cfg.public_mode:
            await save_session(context)
        await browser.close()

    inserted = save_scraped_jobs(found_jobs, default_source=source).inserted
    label = "Scholarship" if opportunity_type == "scholarship" else "LinkedIn"
    msg = f"{label} scrape completed. {inserted} new listings saved."
    if captcha_detected:
        msg = "CAPTCHA detected; partial results saved. Open LinkedIn on your phone, complete verification, then retry."

    if not auth_blocked and not cfg.public_mode:
        clear_linkedin_auth_block(state)
        state.save()

    notify_scrape_complete(
        found=len(found_jobs),
        inserted=inserted,
        skipped_easy_apply=skipped_easy_apply,
        captcha=captcha_detected,
        source=label,
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
        auth_blocked=auth_blocked,
        search_location=cfg.location,
        search_title=cfg.job_title,
    )


def run_scraper_sync(
    cfg: ScraperConfig,
    *,
    require_external_apply: bool = True,
    source: str = "linkedin",
    opportunity_type: str | None = None,
) -> dict:
    result = asyncio.run(
        run_scraper(
            cfg,
            require_external_apply=require_external_apply,
            source=source,
            opportunity_type=opportunity_type,
        )
    )
    return asdict(result)

"""Scraper persistence — uses Supabase via database.jobs."""

from database.jobs import save_scraped_jobs

__all__ = ["save_scraped_jobs"]

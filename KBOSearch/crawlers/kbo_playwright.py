"""
Playwright 기반 KBO 공식 사이트 페이지 수집 헬퍼.
koreabaseball.com은 JavaScript 렌더링이 필요해 requests 대신 Playwright 사용.
"""
import asyncio
import logging

from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def fetch_html(url: str, timeout: int = 15000) -> str:
    """단일 URL을 브라우저로 렌더링 후 HTML 반환."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout)
            page.wait_for_load_state("networkidle", timeout=timeout)
            html = page.content()
        finally:
            browser.close()
    return html


def fetch_multiple_html(
    urls: list[str],
    timeout: int = 15000,
    max_concurrency: int = 4,
) -> list[str]:
    """여러 URL을 하나의 브라우저 세션에서 병렬 수집."""
    if not urls:
        return []

    return asyncio.run(_fetch_multiple_html_async(urls, timeout, max_concurrency))


async def _fetch_multiple_html_async(
    urls: list[str],
    timeout: int,
    max_concurrency: int,
) -> list[str]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    results = [""] * len(urls)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            async def fetch_one(index: int, url: str) -> None:
                async with semaphore:
                    page = await browser.new_page()
                    try:
                        await page.goto(url, timeout=timeout)
                        await page.wait_for_load_state("networkidle", timeout=timeout)
                        results[index] = await page.content()
                    except Exception:
                        logger.exception("Failed to fetch URL: %s", url)
                        results[index] = ""
                    finally:
                        await page.close()

            await asyncio.gather(
                *(fetch_one(index, url) for index, url in enumerate(urls))
            )
        finally:
            await browser.close()

    return results


def fetch_multiple_html_sequential(urls: list[str], timeout: int = 15000) -> list[str]:
    """성능 비교용 순차 수집. 운영 경로에서는 fetch_multiple_html() 사용."""
    if not urls:
        return []
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for url in urls:
                page = browser.new_page()
                try:
                    page.goto(url, timeout=timeout)
                    page.wait_for_load_state("networkidle", timeout=timeout)
                    results.append(page.content())
                except Exception:
                    logger.exception("Failed to fetch URL sequentially: %s", url)
                    results.append("")
                finally:
                    page.close()
        finally:
            browser.close()
    return results


def fetch_html_with_select(
    url: str,
    selector_id: str,
    value: str,
    timeout: int = 15000,
    update_wait_ms: int = 2000,
) -> str:
    """URL 로드 후 select 값을 바꾼 HTML 반환. 실패 시 빈 문자열 반환."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            try:
                page.goto(url, timeout=timeout)
                page.wait_for_load_state("networkidle", timeout=timeout)

                selector = f"#{selector_id}"
                current_val = page.locator(selector).input_value()
                if current_val != value:
                    page.select_option(selector, value)
                    page.wait_for_load_state("networkidle", timeout=timeout)
                    page.wait_for_timeout(update_wait_ms)

                return page.content()
            except Exception:
                logger.exception("Failed to fetch URL with select: url=%s selector_id=%s value=%s", url, selector_id, value)
                return ""
            finally:
                page.close()
        finally:
            browser.close()

"""
Playwright 기반 KBO 공식 사이트 페이지 수집 헬퍼.
koreabaseball.com은 JavaScript 렌더링이 필요해 requests 대신 Playwright 사용.
"""
from playwright.sync_api import sync_playwright


def fetch_html(url: str, timeout: int = 15000) -> str:
    """단일 URL을 브라우저로 렌더링 후 HTML 반환."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=timeout)
        html = page.content()
        browser.close()
    return html


def fetch_multiple_html(urls: list[str], timeout: int = 15000) -> list[str]:
    """여러 URL을 하나의 브라우저 세션으로 순차 수집 (브라우저 기동 비용 절감)."""
    if not urls:
        return []
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for url in urls:
            page = browser.new_page()
            try:
                page.goto(url, timeout=timeout)
                page.wait_for_load_state("networkidle", timeout=timeout)
                results.append(page.content())
            except Exception:
                results.append("")
            finally:
                page.close()
        browser.close()
    return results

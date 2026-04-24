"""연도별 선수 스탯 조회 + FIP 계산."""
from __future__ import annotations
from functools import lru_cache
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CURRENT_YEAR = datetime.today().year
PREV_YEAR = CURRENT_YEAR - 1

BASE = "https://www.koreabaseball.com"
_PIT_URL = f"{BASE}/Record/Player/PitcherBasic/Basic1.aspx"
_BAT_URL = f"{BASE}/Record/Player/HitterBasic/Basic2.aspx"
_SEL = "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"


def _fetch_with_year(url: str, year: int) -> str:
    """Playwright로 연도 드롭다운 선택 후 HTML 반환."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)

            # 현재 선택된 연도 확인 후, 다를 때만 변경
            try:
                current_val = page.locator(f"#{_SEL}").input_value()
                if current_val != str(year):
                    page.select_option(f"#{_SEL}", str(year))
                    # ASP.NET UpdatePanel이 AJAX 응답 후 DOM 업데이트하는 시간 대기
                    page.wait_for_load_state("networkidle", timeout=10000)
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            html = page.content()
        except Exception:
            html = ""
        finally:
            browser.close()
    return html


def _parse_table(html: str) -> tuple[list[str], dict[str, list[str]]]:
    """
    HTML 테이블 파싱.
    반환: (headers, {선수명: row_cells})
    """
    if not html:
        return [], {}
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return [], {}

    rows = table.find_all("tr")
    if not rows:
        return [], {}

    headers = [td.get_text(strip=True) for td in rows[0].find_all(["th", "td"])]
    data: dict[str, list[str]] = {}

    # 선수명 컬럼 인덱스 찾기
    try:
        name_idx = headers.index("선수명")
    except ValueError:
        return headers, {}

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if len(cells) > name_idx:
            name = cells[name_idx]
            if name:
                data[name] = cells

    return headers, data


@lru_cache(maxsize=8)
def _pitcher_table(year: int) -> tuple[list[str], dict[str, list[str]]]:
    """투수 스탯 테이블 fetch (lru_cache)."""
    html = _fetch_with_year(_PIT_URL, year)
    return _parse_table(html)


@lru_cache(maxsize=8)
def _batter_table(year: int) -> tuple[list[str], dict[str, list[str]]]:
    """타자 스탯 테이블 fetch (lru_cache)."""
    html = _fetch_with_year(_BAT_URL, year)
    return _parse_table(html)


def clear_cache() -> None:
    """lru_cache 전체 초기화 (재수집 필요 시 호출)."""
    _pitcher_table.cache_clear()
    _batter_table.cache_clear()


def _safe_get(row: list[str], headers: list[str], col: str) -> str:
    try:
        idx = headers.index(col)
        val = row[idx] if idx < len(row) else "-"
        return val if val else "-"
    except (ValueError, IndexError):
        return "-"


def _calc_fip(row: list[str], headers: list[str]) -> str:
    """FIP = (13×HR + 3×(BB+HBP) - 2×SO) / IP + 3.15"""
    try:
        hr  = float(_safe_get(row, headers, "HR"))
        bb  = float(_safe_get(row, headers, "BB"))
        hbp = float(_safe_get(row, headers, "HBP"))
        so  = float(_safe_get(row, headers, "SO"))
        ip_str = _safe_get(row, headers, "IP")

        # IP 파싱: "123.1" 또는 "180 2/3" 또는 "123" 형식
        ip_str = ip_str.replace(",", "")
        if "/" in ip_str:
            # "180 2/3" 형식
            parts = ip_str.split()
            whole = float(parts[0]) if parts else 0.0
            frac_parts = parts[1].split("/") if len(parts) > 1 else ["0", "1"]
            ip = whole + float(frac_parts[0]) / float(frac_parts[1])
        elif "." in ip_str:
            # "123.1" 형식 (소수점 이하는 아웃 수)
            parts = ip_str.split(".")
            ip = float(parts[0]) + float(parts[1]) / 3
        else:
            ip = float(ip_str)

        if ip <= 0:
            return "-"

        fip = (13 * hr + 3 * (bb + hbp) - 2 * so) / ip + 3.15
        return f"{fip:.2f}"
    except (ValueError, ZeroDivisionError, Exception):
        return "-"


def get_pitcher_stats(name: str, year: int) -> dict:
    """
    투수 이름+연도로 스탯 조회.

    Returns:
        {"ERA", "WHIP", "FIP", "W", "L", "SO", "BB", "IP", "record"} or {}
    """
    try:
        headers, data = _pitcher_table(year)
        if name not in data:
            return {}

        row = data[name]

        def g(col):
            return _safe_get(row, headers, col)

        w = g("W")
        l = g("L")
        record = f"{w}승 {l}패" if w != "-" and l != "-" else "-"
        fip = _calc_fip(row, headers)

        result = {
            "ERA":    g("ERA"),
            "WHIP":   g("WHIP"),
            "FIP":    fip,
            "W":      w,
            "L":      l,
            "SO":     g("SO"),
            "BB":     g("BB"),
            "IP":     g("IP"),
            "record": record,
        }
        return result
    except Exception:
        return {}


def get_batter_stats(name: str, year: int) -> dict:
    """
    타자 이름+연도로 스탯 조회.

    Returns:
        {"AVG", "OPS", "OBP", "SLG"} or {}
    """
    try:
        headers, data = _batter_table(year)
        if name not in data:
            return {}

        row = data[name]

        def g(col):
            return _safe_get(row, headers, col)

        result = {
            "AVG": g("AVG"),
            "OPS": g("OPS"),
            "OBP": g("OBP"),
            "SLG": g("SLG"),
        }
        return result
    except Exception:
        return {}

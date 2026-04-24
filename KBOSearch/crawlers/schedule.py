"""
KBO 공식 사이트에서 경기 일정 + 선발 투수 파싱.
- /Schedule/Schedule.aspx?gameDate=YYYYMMDD  →  경기 목록
- /Schedule/GameCenter/Main.aspx?...&section=START_PIT  →  선발 투수 이름
"""
import re
from bs4 import BeautifulSoup
from datetime import datetime

from crawlers.kbo_playwright import fetch_html, fetch_multiple_html

BASE = "https://www.koreabaseball.com"


def fetch_game_list(date_str: str | None = None) -> list[dict]:
    """
    특정 날짜의 KBO 경기 목록 반환.

    Args:
        date_str: "YYYY-MM-DD" 형식. None이면 오늘.

    Returns:
        [
            {
                "game_id": "20260424LGOB0",
                "date":    "2026-04-24",
                "away":    "LG",
                "home":    "두산",
                "time":    "18:30",
                "away_pitcher": "임찬규",
                "home_pitcher": "최승용",
            },
            ...
        ]
    """
    if not date_str:
        date_str = datetime.today().strftime("%Y-%m-%d")

    g_date = date_str.replace("-", "")   # YYYYMMDD
    # MM.DD 형식으로 날짜 행 매칭
    target_md = f"{date_str[5:7]}.{date_str[8:]}"  # "04.24"

    sched_url = f"{BASE}/Schedule/Schedule.aspx?gameDate={g_date}"
    html = fetch_html(sched_url)
    games = _parse_schedule(html, date_str, target_md)

    if not games:
        return []

    # 선발 투수 조회 (START_PIT 섹션)
    pit_urls = [
        f"{BASE}/Schedule/GameCenter/Main.aspx"
        f"?gameDate={g_date}&gameId={g['game_id']}&section=START_PIT"
        for g in games
    ]
    pit_htmls = fetch_multiple_html(pit_urls)

    # pitcher 모듈에 스탯 사전 캐시 (이후 fetch_pitcher_stats 호출 시 Playwright 불필요)
    from crawlers import pitcher as pitcher_mod

    for g, pit_html in zip(games, pit_htmls):
        away_p, home_p = _parse_starters(pit_html)
        g["away_pitcher"] = away_p
        g["home_pitcher"] = home_p
        pitcher_mod._cache_stats(g["game_id"], pit_html)

    return games


def _parse_schedule(html: str, date_str: str, target_md: str) -> list[dict]:
    """경기 일정 테이블에서 target_md 날짜의 경기 파싱."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    games = []
    in_target = False

    for row in table.find_all("tr")[1:]:   # 헤더 제외
        # 날짜 셀이 있으면 날짜 갱신
        day_td = row.find("td", class_="day")
        if day_td:
            day_text = day_td.get_text(strip=True)   # "04.24(금)"
            in_target = day_text.startswith(target_md)

        if not in_target:
            continue

        play_td = row.find("td", class_="play")
        relay_td = row.find("td", class_="relay")
        if not play_td or not relay_td:
            continue

        # 팀명: 첫 번째·마지막 span
        spans = play_td.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        away = spans[0].get_text(strip=True)
        home = spans[-1].get_text(strip=True)

        # 경기 시간
        time_td = row.find("td", class_="time")
        time_str = time_td.get_text(strip=True) if time_td else ""

        # game_id (href에서 추출)
        anchor = relay_td.find("a")
        if not anchor:
            continue
        href = anchor.get("href", "")
        m = re.search(r"gameId=([A-Z0-9]+)", href)
        if not m:
            continue
        game_id = m.group(1)

        games.append({
            "game_id":      game_id,
            "date":         date_str,
            "away":         away,
            "home":         home,
            "time":         time_str,
            "away_pitcher": "미정",
            "home_pitcher": "미정",
        })

    return games


def _parse_starters(html: str) -> tuple[str, str]:
    """START_PIT HTML에서 선발 투수 이름 (원정, 홈) 반환."""
    if not html:
        return "미정", "미정"
    soup = BeautifulSoup(html, "html.parser")
    pit_tds = [td for td in soup.find_all("td", class_="pitcher")]
    names = []
    for td in pit_tds:
        span = td.select_one("span.name")
        if span:
            names.append(span.get_text(strip=True))
    return (
        names[0] if len(names) > 0 else "미정",
        names[1] if len(names) > 1 else "미정",
    )


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    if not games:
        print("경기 없음")
    else:
        for g in games:
            print(
                f"[{g['date']}] {g['away']}({g['away_pitcher']}) "
                f"vs {g['home']}({g['home_pitcher']})  {g['time']}  [{g['game_id']}]"
            )

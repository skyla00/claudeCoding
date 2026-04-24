"""
KBO 게임센터 START_PIT 섹션에서 선발 투수 스탯 크롤링.
제공 스탯: ERA, WAR, 경기, 선발평균이닝, QS, WHIP + 시즌 성적(기록)

캐싱 전략:
  schedule.fetch_game_list()이 START_PIT HTML을 이미 수집하므로,
  _cache_stats()로 미리 파싱 결과를 저장해 두면
  fetch_pitcher_stats()는 Playwright 호출 없이 즉시 반환함.
"""
from bs4 import BeautifulSoup
from crawlers.kbo_playwright import fetch_html
from crawlers.player_stats import get_pitcher_stats, CURRENT_YEAR, PREV_YEAR

BASE = "https://www.koreabaseball.com"

# START_PIT 테이블 컬럼 → 내부 키 매핑
_COL_MAP = {
    "평균자책점": "ERA",
    "WAR":       "WAR",
    "경기":      "G",
    "선발평균이닝": "innings",
    "QS":        "QS",
    "WHIP":      "WHIP",
}

# 프로세스 내 사전 캐시 (schedule.fetch_game_list에서 미리 채워짐)
_stats_cache: dict[str, dict] = {}


def _cache_stats(game_id: str, html: str) -> None:
    """schedule.py가 START_PIT HTML 수집 시 호출해 스탯을 미리 캐시."""
    _stats_cache[game_id] = _parse(html)


def fetch_pitcher_stats(game_id: str) -> dict:
    """
    game_id로 선발 투수 스탯 조회.

    Args:
        game_id: "20260424LGOB0" 형식

    Returns:
        {
            "away": {"name": "임찬규", "ERA": "6.52", "WHIP": "2.07", "WAR": "-0.06",
                     "G": "4", "innings": "5.0", "QS": "0", "record": "시즌 1패"},
            "home": {...}
        }
    """
    # 사전 캐시 우선 (schedule.fetch_game_list에서 미리 채워진 경우 즉시 반환)
    if game_id in _stats_cache:
        result = _stats_cache[game_id]
        # history가 없으면 이 시점에 추가 (캐시 이후에 player_stats가 준비된 경우)
        if result.get("away") and "history" not in result["away"]:
            result = _attach_history(result)
            _stats_cache[game_id] = result
        return result

    date = game_id[:8]
    url = (
        f"{BASE}/Schedule/GameCenter/Main.aspx"
        f"?gameDate={date}&gameId={game_id}&section=START_PIT"
    )
    html = fetch_html(url)
    result = _parse(html)
    result = _attach_history(result)
    _stats_cache[game_id] = result
    return result


def _parse(html: str) -> dict:
    if not html:
        return {"away": {"name": "미정"}, "home": {"name": "미정"}}

    soup = BeautifulSoup(html, "html.parser")

    # ── 1. 투수 이름·기록 (td.pitcher > span.name, div.record) ──────────
    pit_tds = [td for td in soup.find_all("td", class_="pitcher")]
    names_info = []
    for td in pit_tds:
        name_span = td.select_one("span.name")
        record_div = td.select_one("div.record")
        if name_span:
            record_text = record_div.get_text(" ", strip=True) if record_div else "-"
            names_info.append({
                "name":   name_span.get_text(strip=True),
                "record": record_text,
            })

    # ── 2. 스탯 테이블 ────────────────────────────────────────────────────
    table = soup.find("table")
    stats = [{}, {}]
    if table:
        rows = table.find_all("tr")
        if rows:
            headers = [td.get_text(strip=True) for td in rows[0].find_all(["th", "td"])]
            for i, row in enumerate(rows[1:3]):
                cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
                stat = {}
                for j, hdr in enumerate(headers):
                    key = _COL_MAP.get(hdr)
                    if key and j < len(cells):
                        stat[key] = cells[j]
                stats[i] = stat

    def _build(info: dict, stat: dict) -> dict:
        d = {"name": "미정", "record": "-"}
        d.update(info)
        d.update(stat)
        return d

    away = _build(names_info[0] if len(names_info) > 0 else {}, stats[0])
    home = _build(names_info[1] if len(names_info) > 1 else {}, stats[1])

    return {"away": away, "home": home}


def _attach_history(result: dict) -> dict:
    """fetch_pitcher_stats 결과에 연도별 히스토리 추가."""
    for side in ("away", "home"):
        pitcher = result.get(side, {})
        name = pitcher.get("name", "")
        if name and name != "미정":
            history = {}
            for yr in (CURRENT_YEAR, PREV_YEAR):
                s = get_pitcher_stats(name, yr)
                if s:
                    history[str(yr)] = s
            pitcher["history"] = history
    return result


if __name__ == "__main__":
    import argparse, json, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from crawlers.schedule import fetch_game_list

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    for g in games:
        stats = fetch_pitcher_stats(g["game_id"])
        print(f"{g['away']} vs {g['home']}")
        print(f"  원정: {stats['away']}")
        print(f"  홈:   {stats['home']}")
        print()

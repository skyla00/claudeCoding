"""
KBO 공식 사이트에서 특정 팀의 최근 N경기 결과 크롤링.
/Schedule/Schedule.aspx?gameDate=YYYYMMDD 에서 월별 전체 결과를 파싱 후 역순 정렬.
로그인 불필요, robots.txt /Schedule/ 허용.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from functools import lru_cache

from crawlers.kbo_playwright import fetch_html

BASE = "https://www.koreabaseball.com"


@lru_cache(maxsize=12)
def _fetch_month_games(year_month: str) -> list[dict]:
    """
    해당 연월(YYYYMM)의 완료된 전체 경기 결과 파싱.
    Returns: [{"date", "away", "away_score", "home", "home_score"}]
    """
    # 해당 달 1일로 요청 (KBO는 달력 기준으로 전체 월 반환)
    g_date = year_month + "01"
    url = f"{BASE}/Schedule/Schedule.aspx?gameDate={g_date}"
    html = fetch_html(url)
    return _parse_results(html)


def _parse_results(html: str) -> list[dict]:
    """완료된 경기 결과만 파싱."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    games = []
    current_date = ""

    for row in table.find_all("tr")[1:]:
        day_td = row.find("td", class_="day")
        if day_td:
            # "04.24(금)" → "2026-04-24" (연도는 현재 연도로 가정)
            day_text = day_td.get_text(strip=True)
            m = re.match(r"(\d{2})\.(\d{2})", day_text)
            if m:
                year = datetime.today().year
                current_date = f"{year}-{m.group(1)}-{m.group(2)}"

        play_td = row.find("td", class_="play")
        relay_td = row.find("td", class_="relay")
        if not play_td or not relay_td or not current_date:
            continue

        # 완료 경기: 리뷰 버튼(btnReview) 또는 하이라이트 버튼 존재
        if not relay_td.find("a", id="btnReview"):
            continue

        # 팀명
        spans = play_td.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        away = spans[0].get_text(strip=True)
        home = spans[-1].get_text(strip=True)

        # 점수 (em 안의 span.win / span.lose)
        em = play_td.find("em")
        if not em:
            continue
        score_spans = em.find_all("span")
        scores = []
        for s in score_spans:
            txt = s.get_text(strip=True)
            if txt.isdigit():
                scores.append(int(txt))
        if len(scores) < 2:
            continue

        games.append({
            "date":       current_date,
            "away":       away,
            "away_score": scores[0],
            "home":       home,
            "home_score": scores[1],
        })

    return games


def fetch_recent_games(
    team_name: str,
    n: int = 5,
    before_date: str | None = None,
) -> list[dict]:
    """
    특정 팀의 최근 n경기 결과 반환 (before_date 하루 전까지).

    Args:
        team_name:   팀명 (예: "LG", "롯데", "KIA")
        n:           가져올 경기 수
        before_date: 기준 날짜 YYYY-MM-DD (기본: 오늘)

    Returns:
        [
            {
                "date":     "2026-04-23",
                "opponent": "두산",
                "result":   "승",
                "my_score": 5,
                "opp_score":2,
                "home_away":"홈",
            },
            ...
        ]  최신 경기가 앞에 오도록 정렬
    """
    if not before_date:
        before_date = datetime.today().strftime("%Y-%m-%d")

    cutoff = datetime.strptime(before_date, "%Y-%m-%d")
    collected: list[dict] = []

    # 최대 2개월 탐색
    months_checked = set()
    check_dt = cutoff - timedelta(days=1)

    for _ in range(60):   # 안전장치: 최대 60일 역탐색
        if len(collected) >= n:
            break

        ym = check_dt.strftime("%Y%m")
        if ym not in months_checked:
            months_checked.add(ym)
            month_games = _fetch_month_games(ym)
        else:
            month_games = _fetch_month_games(ym)

        # 이 날짜의 경기 찾기
        date_str = check_dt.strftime("%Y-%m-%d")
        for g in month_games:
            if g["date"] != date_str:
                continue
            if g["away"] == team_name:
                result = _result(g["away_score"], g["home_score"])
                collected.append({
                    "date":      g["date"],
                    "opponent":  g["home"],
                    "result":    result,
                    "my_score":  g["away_score"],
                    "opp_score": g["home_score"],
                    "home_away": "원정",
                })
            elif g["home"] == team_name:
                result = _result(g["home_score"], g["away_score"])
                collected.append({
                    "date":      g["date"],
                    "opponent":  g["away"],
                    "result":    result,
                    "my_score":  g["home_score"],
                    "opp_score": g["away_score"],
                    "home_away": "홈",
                })
            if len(collected) >= n:
                break

        check_dt -= timedelta(days=1)

    return collected   # 최신 경기가 앞에


def _result(my: int, opp: int) -> str:
    if my > opp:
        return "승"
    elif my < opp:
        return "패"
    return "무"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, help="팀명 (예: LG, 롯데, KIA)")
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    games = fetch_recent_games(args.team, args.n, args.date)
    if not games:
        print(f"{args.team} 최근 경기 없음")
    else:
        for g in games:
            print(
                f"  {g['date']} ({g['home_away']}) vs {g['opponent']} "
                f"{g['my_score']}-{g['opp_score']} [{g['result']}]"
            )

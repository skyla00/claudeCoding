import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BASE_URL = "https://statiz.co.kr/prediction/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get_target_date(date_str: str | None = None) -> str:
    """날짜 문자열 반환. 기본값: 어제 날짜 (YYYY-MM-DD)"""
    if date_str:
        return date_str
    yesterday = datetime.today() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def fetch_game_list(date_str: str | None = None) -> list[dict]:
    """
    statiz prediction 페이지에서 경기 목록 + 선발 투수 파싱.

    Returns:
        [
            {
                "s_no": "20260071",
                "date": "2026-04-12",
                "away": "롯데",
                "home": "LG",
                "time": "18:30",
                "away_pitcher": "나균안",
                "home_pitcher": "송승기",
            },
            ...
        ]
    """
    date = get_target_date(date_str)
    g_date = date.replace("-", "")  # YYYYMMDD 형식
    res = requests.get(BASE_URL, params={"g_date": g_date}, headers=HEADERS, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    games = []

    for slide in soup.select("div.swiper-slide.item"):
        # s_no 추출
        anchor = slide.select_one("a")
        if not anchor:
            continue
        match = re.search(r"s_no=(\d+)", anchor.get("onclick", ""))
        if not match:
            continue
        s_no = match.group(1)

        # 팀명 (away=첫 번째 li, home=두 번째 li)
        teams = slide.select("div.tname")
        if len(teams) < 2:
            continue
        away = teams[0].get_text(strip=True)
        home = teams[1].get_text(strip=True)

        # 경기 시간
        time_tag = slide.select_one("div.g_info span")
        time_str = time_tag.get_text(strip=True) if time_tag else ""

        # 선발 투수 (개별 경기 페이지)
        away_pitcher, home_pitcher = fetch_starters(s_no)

        games.append({
            "s_no": s_no,
            "date": date,
            "away": away,
            "home": home,
            "time": time_str,
            "away_pitcher": away_pitcher,
            "home_pitcher": home_pitcher,
        })

    return games


def fetch_starters(s_no: str) -> tuple[str, str]:
    """경기 상세 페이지에서 선발 투수 이름 반환 (away, home)"""
    res = requests.get(BASE_URL, params={"s_no": s_no}, headers=HEADERS, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    player_box = soup.find("div", class_="player_box")
    if not player_box:
        return "미정", "미정"

    names = [tag.get_text(strip=True) for tag in player_box.select("div.name")]
    away_pitcher = names[0] if len(names) > 0 else "미정"
    home_pitcher = names[1] if len(names) > 1 else "미정"
    return away_pitcher, home_pitcher


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="KBO 경기 일정 + 선발 투수 조회")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="조회할 날짜 (YYYY-MM-DD). 기본값: 어제",
    )
    args = parser.parse_args()

    games = fetch_game_list(args.date)

    if not games:
        print("경기 없음")
    else:
        for g in games:
            print(f"[{g['date']}] {g['away']}({g['away_pitcher']}) vs {g['home']}({g['home_pitcher']})  {g['time']}")

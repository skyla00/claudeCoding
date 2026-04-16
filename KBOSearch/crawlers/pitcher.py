import requests
from bs4 import BeautifulSoup

BASE_URL = "https://statiz.co.kr/prediction/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# record_box에서 뽑을 스탯 항목
STAT_LABELS = ["경기이닝", "승패", "평균자책", "WHIP", "피안타율", "탈삼진", "볼넷", "WAR"]


def fetch_pitcher_stats(s_no: str) -> dict:
    """
    경기 상세 페이지에서 양 선발 투수 스탯 파싱.

    Returns:
        {
            "away": {"name": "베니지아노", "ERA": "4.35", "WHIP": "1.65", ...},
            "home": {"name": "톨허스트",   "ERA": "8.00", "WHIP": "1.56", ...},
        }
    """
    res = requests.get(BASE_URL, params={"s_no": s_no}, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # 투수 이름 (player_box)
    player_box = soup.find("div", class_="player_box")
    names = ["미정", "미정"]
    if player_box:
        names = [tag.get_text(strip=True) for tag in player_box.select("div.name")]

    # 스탯 (record_box)
    away_stats = {"name": names[0] if names else "미정"}
    home_stats = {"name": names[1] if len(names) > 1 else "미정"}

    record_box = soup.find("div", class_="record_box")
    if not record_box:
        return {"away": away_stats, "home": home_stats}

    label_map = {
        "경기이닝": "innings",
        "승패": "record",
        "평균자책": "ERA",
        "WHIP": "WHIP",
        "피안타율": "opp_avg",
        "탈삼진": "K",
        "볼넷": "BB",
        "WAR": "WAR",
    }

    for ul in record_box.find_all("ul"):
        label_tag = ul.find("li", class_="label")
        if not label_tag:
            continue
        label = label_tag.get_text(strip=True)
        if label not in label_map:
            continue

        values = [" ".join(li.get_text().split()) for li in ul.find_all("li", class_="value")]
        if len(values) < 2:
            continue

        key = label_map[label]
        away_stats[key] = values[0]
        home_stats[key] = values[1]

    return {"away": away_stats, "home": home_stats}


if __name__ == "__main__":
    import argparse
    import json
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from crawlers.schedule import fetch_game_list

    parser = argparse.ArgumentParser(description="KBO 선발 투수 스탯 조회")
    parser.add_argument("--date", type=str, default=None, help="조회 날짜 (YYYY-MM-DD). 기본값: 어제")
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    results = []
    for g in games:
        stats = fetch_pitcher_stats(g["s_no"])
        results.append({
            "matchup": f"{g['away']} vs {g['home']}",
            "away_pitcher": stats["away"],
            "home_pitcher": stats["home"],
        })

    print(json.dumps(results, ensure_ascii=False, indent=2))

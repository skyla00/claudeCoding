import requests
from bs4 import BeautifulSoup

BASE_URL = "https://statiz.co.kr/prediction/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

TEAM_STAT_LABELS = {
    "시즌 성적": "season_record",
    "팀 타율":   "team_avg",
    "팀 OPS":    "team_OPS",
    "팀 평균자책": "team_ERA",
    "팀 WHIP":   "team_WHIP",
    "팀 득점":   "team_runs",
    "팀 실점":   "team_runs_allowed",
}


def fetch_lineup(s_no: str) -> dict:
    """
    경기 상세 페이지에서 팀 스탯 + 핵심 타자 파싱.

    Returns:
        {
            "away": {
                "team_avg": "0.263", "team_OPS": "0.747", "team_ERA": "4.64", "team_WHIP": "1.51",
                "season_record": "5승 0무 8패",
                "key_hitters": [
                    {"name": "박성한", "OPS": "1.417"},
                    ...
                ]
            },
            "home": { ... }
        }
    """
    res = requests.get(BASE_URL, params={"s_no": s_no}, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    away_data: dict = {}
    home_data: dict = {}

    # ── 1. 팀 스탯 (comparison_area > team_season) ──────────────────
    team_season_uls = soup.select("div.comparison_area div.team_season ul")
    for ul in team_season_uls:
        label_tag = ul.find("li", class_="label")
        if not label_tag:
            continue
        label = label_tag.get_text(strip=True)
        if label not in TEAM_STAT_LABELS:
            continue

        key = TEAM_STAT_LABELS[label]
        away_li = ul.find("li", class_="away")
        home_li = ul.find("li", class_="home")

        away_data[key] = " ".join(away_li.get_text().split()) if away_li else "-"
        home_data[key] = " ".join(home_li.get_text().split()) if home_li else "-"

    # ── 2. 핵심 타자 (comparison_con[1] > player_box.hitter x2) ────────
    # 첫 번째 player_box.hitter = away, 두 번째 = home
    hitter_boxes = soup.select("div.player_box.hitter")
    for idx, box in enumerate(hitter_boxes[:2]):
        hitters = []
        for item in box.select("div.item"):
            names = [d.get_text(strip=True) for d in item.select("div.name")]
            if not names:
                continue
            name = names[0]
            ops = names[1].replace("OPS : ", "") if len(names) > 1 else "-"
            hitters.append({"name": name, "OPS": ops})

        if idx == 0:
            away_data["key_hitters"] = hitters
        else:
            home_data["key_hitters"] = hitters

    return {"away": away_data, "home": home_data}


if __name__ == "__main__":
    import argparse
    import json
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__) + "/..")
    from crawlers.schedule import fetch_game_list

    parser = argparse.ArgumentParser(description="KBO 팀 타선 성향 조회")
    parser.add_argument("--date", type=str, default=None, help="조회 날짜 (YYYY-MM-DD). 기본값: 어제")
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    results = []
    for g in games:
        lineup = fetch_lineup(g["s_no"])
        results.append({
            "matchup": f"{g['away']} vs {g['home']}",
            "away_lineup": lineup["away"],
            "home_lineup": lineup["home"],
        })

    print(json.dumps(results, ensure_ascii=False, indent=2))

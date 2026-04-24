"""
KBO 공식 사이트에서 팀 타격/투구 스탯 + 핵심 타자 크롤링.

데이터 출처 (모두 /Record/ 하위, robots.txt 허용):
  - /Record/TeamRank/TeamRankDaily.aspx          → 팀 순위 (시즌 성적)
  - /Record/Team/Hitter/Basic2.aspx              → 팀 타격 (AVG, OPS, OBP, SLG)
  - /Record/Team/Pitcher/Basic1.aspx             → 팀 투구 (ERA, WHIP, 실점)
  - /Record/Player/HitterBasic/Basic2.aspx       → 개인 타격 (OPS) → 핵심 타자

lru_cache로 한 번만 수집 후 재사용 (Streamlit 재실행과 무관하게 프로세스 내 캐시 유지).
"""
from __future__ import annotations
from functools import lru_cache
from bs4 import BeautifulSoup

from crawlers.kbo_playwright import fetch_multiple_html
from crawlers.player_stats import get_batter_stats, CURRENT_YEAR, PREV_YEAR

BASE = "https://www.koreabaseball.com"

_TEAM_RANK_URL    = f"{BASE}/Record/TeamRank/TeamRankDaily.aspx"
_TEAM_HIT_URL     = f"{BASE}/Record/Team/Hitter/Basic2.aspx"
_TEAM_PIT_URL     = f"{BASE}/Record/Team/Pitcher/Basic1.aspx"
_PLAYER_HIT_URL   = f"{BASE}/Record/Player/HitterBasic/Basic2.aspx"


# ── 캐시된 원시 데이터 수집 ──────────────────────────────────────────────────

@lru_cache(maxsize=4)
def _fetch_all_raw() -> dict:
    """4개 페이지를 한 번에 수집, 전체 데이터 반환."""
    urls = [_TEAM_RANK_URL, _TEAM_HIT_URL, _TEAM_PIT_URL, _PLAYER_HIT_URL]
    htmls = fetch_multiple_html(urls)
    rank_html, hit_html, pit_html, player_html = htmls

    return {
        "rank":   _parse_table(rank_html),
        "hit":    _parse_table(hit_html),
        "pit":    _parse_table(pit_html),
        "player": _parse_table(player_html),
    }


def _parse_table(html: str) -> list[list[str]]:
    """HTML 테이블의 모든 행을 list[list[str]]으로 파싱."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    result = []
    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if cells:
            result.append(cells)
    return result


# ── 팀 데이터 추출 헬퍼 ─────────────────────────────────────────────────────

def _col_idx(header_row: list[str], col_name: str) -> int:
    try:
        return header_row.index(col_name)
    except ValueError:
        return -1


def _team_row(rows: list[list[str]], team_name: str, team_col: int = 1) -> list[str] | None:
    for row in rows[1:]:   # 헤더 제외
        if len(row) > team_col and row[team_col] == team_name:
            return row
    return None


def _safe(row: list[str] | None, idx: int) -> str:
    if row is None or idx < 0 or idx >= len(row):
        return "-"
    return row[idx] or "-"


# ── 공개 인터페이스 ─────────────────────────────────────────────────────────

def fetch_lineup(away_team: str, home_team: str) -> dict:
    """
    두 팀의 타선 스탯 반환.

    Returns:
        {
            "away": {
                "season_record":    "14승 0무 7패",
                "team_avg":         "0.267",
                "team_OPS":         "0.767",
                "team_ERA":         "3.47",
                "team_WHIP":        "1.34",
                "team_runs_allowed":"78",
                "key_hitters": [
                    {"name": "박성한", "OPS": "1.257"},
                    ...
                ]
            },
            "home": { ... }
        }
    """
    raw = _fetch_all_raw()

    rank_rows   = raw["rank"]
    hit_rows    = raw["hit"]
    pit_rows    = raw["pit"]
    player_rows = raw["player"]

    result = {}
    for team in (away_team, home_team):
        # ── 팀 순위 (시즌 성적) ────────────────────────────────────────
        rank_hdr  = rank_rows[0] if rank_rows else []
        rank_row  = _team_row(rank_rows, team)
        w_idx = _col_idx(rank_hdr, "승")
        l_idx = _col_idx(rank_hdr, "패")
        d_idx = _col_idx(rank_hdr, "무")
        w = _safe(rank_row, w_idx)
        l = _safe(rank_row, l_idx)
        d = _safe(rank_row, d_idx)
        season_record = f"{w}승 {d}무 {l}패" if w != "-" else "-"

        # ── 팀 타격 ────────────────────────────────────────────────────
        hit_hdr = hit_rows[0] if hit_rows else []
        hit_row = _team_row(hit_rows, team)
        avg_idx = _col_idx(hit_hdr, "AVG")
        ops_idx = _col_idx(hit_hdr, "OPS")
        obp_idx = _col_idx(hit_hdr, "OBP")
        slg_idx = _col_idx(hit_hdr, "SLG")

        team_avg = _safe(hit_row, avg_idx)
        team_ops = _safe(hit_row, ops_idx)

        # ── 팀 투구 ────────────────────────────────────────────────────
        pit_hdr = pit_rows[0] if pit_rows else []
        pit_row = _team_row(pit_rows, team)
        era_idx  = _col_idx(pit_hdr, "ERA")
        whip_idx = _col_idx(pit_hdr, "WHIP")
        r_idx    = _col_idx(pit_hdr, "R")    # 실점

        team_era  = _safe(pit_row, era_idx)
        team_whip = _safe(pit_row, whip_idx)
        team_r_allowed = _safe(pit_row, r_idx)

        # ── 핵심 타자 (팀별 OPS 상위 3명) ──────────────────────────────
        player_hdr = player_rows[0] if player_rows else []
        name_idx  = _col_idx(player_hdr, "선수명")
        tm_idx    = _col_idx(player_hdr, "팀명")
        ops2_idx  = _col_idx(player_hdr, "OPS")

        key_hitters = []
        candidates = []
        for row in player_rows[1:]:
            if len(row) <= max(name_idx, tm_idx, ops2_idx):
                continue
            if row[tm_idx] != team:
                continue
            try:
                ops_val = float(row[ops2_idx])
                candidates.append({"name": row[name_idx], "OPS": row[ops2_idx], "_ops": ops_val})
            except (ValueError, IndexError):
                continue

        candidates.sort(key=lambda x: x["_ops"], reverse=True)
        key_hitters = []
        for c in candidates[:3]:
            hitter = {"name": c["name"], "OPS": c["OPS"]}
            # 연도별 히스토리 추가
            history = {}
            for yr in (CURRENT_YEAR, PREV_YEAR):
                s = get_batter_stats(c["name"], yr)
                if s:
                    history[str(yr)] = s
            if history:
                hitter["history"] = history
            key_hitters.append(hitter)

        result[team] = {
            "season_record":    season_record,
            "team_avg":         team_avg,
            "team_OPS":         team_ops,
            "team_ERA":         team_era,
            "team_WHIP":        team_whip,
            "team_runs_allowed": team_r_allowed,
            "key_hitters":      key_hitters,
        }

    return {"away": result[away_team], "home": result[home_team]}


if __name__ == "__main__":
    import argparse, json, sys, os
    sys.path.insert(0, os.path.dirname(__file__) + "/..")
    from crawlers.schedule import fetch_game_list

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    for g in games:
        lineup = fetch_lineup(g["away"], g["home"])
        print(f"{g['away']} vs {g['home']}")
        print(f"  원정: {lineup['away']}")
        print(f"  홈:   {lineup['home']}")
        print()

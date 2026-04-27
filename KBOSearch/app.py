import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from datetime import datetime

from crawlers.schedule import fetch_game_list
from crawlers.pitcher import fetch_pitcher_stats
from crawlers.lineup import fetch_lineup
from crawlers.recent_games import fetch_recent_games
from crawlers.player_stats import CURRENT_YEAR, PREV_YEAR
from crawlers.types import Game, LineupResponse, PitcherStatsResponse, RecentGame
from analysis.prompt import build_prompt
from analysis.provider import analyze_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(page_title="KBO 매치업 분석기", page_icon="⚾", layout="centered")
st.title("⚾ KBO 선발 매치업 분석기")

DATA_CACHE_VERSION = "2026-04-27-p2-parallel-progressive-v3"

# 사이드바
with st.sidebar:
    st.header("설정")
    date = st.date_input("날짜", value=datetime.today())
    date_str = date.strftime("%Y-%m-%d")
    my_team = st.text_input("내 팀 (선택)", placeholder="예: 두산, LG")

# 경기 목록 로드
@st.cache_data(ttl=300)
def load_games(date_str: str, cache_version: str) -> list[Game]:
    # fetch_game_list 내부에서 START_PIT HTML을 수집하면서
    # pitcher._stats_cache에 스탯을 미리 저장함 → 경기 선택 시 Playwright 재호출 없음
    return fetch_game_list(date_str)

@st.cache_data(ttl=3600)
def load_pitcher_stats(game_id: str, cache_version: str) -> PitcherStatsResponse:
    # pitcher._stats_cache에 이미 있으면 즉시 반환 (load_games 이후)
    return fetch_pitcher_stats(game_id)

@st.cache_data(ttl=3600)
def load_lineup(away: str, home: str, cache_version: str) -> LineupResponse:
    # 내부 _fetch_all_raw()는 lru_cache로 최초 1회만 Playwright 호출
    return fetch_lineup(away, home)

@st.cache_data(ttl=3600)
def load_recent_games(team_name: str, date_str: str, cache_version: str) -> list[RecentGame]:
    return fetch_recent_games(team_name, n=5, before_date=date_str)

with st.spinner("경기 목록 불러오는 중..."):
    try:
        games = load_games(date_str, DATA_CACHE_VERSION)
    except Exception as e:
        logger.exception("Failed to load games: date=%s", date_str)
        st.error(f"경기 목록 로드 실패: {e}")
        games = []

if not games:
    st.info(f"{date_str} 경기가 없습니다.")
    st.stop()

st.subheader(f"{date_str} 경기 목록")

# 선택된 경기 상태
if "selected_game" not in st.session_state:
    st.session_state.selected_game = None

# 경기 버튼
cols = st.columns(min(len(games), 3))
for i, g in enumerate(games):
    with cols[i % 3]:
        label = f"{g['away']} vs {g['home']}\n{g['time']}"
        if st.button(label, key=f"game_{i}", use_container_width=True):
            st.session_state.selected_game = i

# 분석 출력
if st.session_state.selected_game is not None:
    idx = st.session_state.selected_game
    g = games[idx]

    st.divider()
    st.subheader(f"⚾ {g['away']} ({g['away_pitcher']}) vs {g['home']} ({g['home_pitcher']})")
    st.caption(f"선발: {g['away']} {g['away_pitcher']} / {g['home']} {g['home_pitcher']}")

    with st.spinner("데이터 수집 중..."):
        try:
            pitcher_stats = load_pitcher_stats(g["game_id"], DATA_CACHE_VERSION)
            lineup = load_lineup(g["away"], g["home"], DATA_CACHE_VERSION)
            recent = {
                "away": load_recent_games(g["away"], date_str, DATA_CACHE_VERSION),
                "home": load_recent_games(g["home"], date_str, DATA_CACHE_VERSION),
            }
            prompt = build_prompt(g, pitcher_stats, lineup, recent_games=recent, my_team=my_team or None)
        except Exception as e:
            logger.exception("Failed to collect data: game_id=%s", g.get("game_id"))
            st.error(f"데이터 수집 실패: {e}")
            st.stop()

    st.markdown("### 분석 결과")
    result_placeholder = st.empty()
    full_text = ""

    try:
        for chunk in analyze_stream(prompt):
            full_text += chunk
            result_placeholder.markdown(full_text)
    except Exception as e:
        logger.exception("Analysis failed: game_id=%s", g.get("game_id"))
        st.error(f"분석 실패: {e}")

    # ── 판단 근거 데이터 ────────────────────────────────────────────
    stats_date = datetime.today().strftime("%Y.%m.%d")
    with st.expander(f"📊 판단 근거 데이터 보기  (스탯 기준: {stats_date})", expanded=False):
        tab_pitcher, tab_lineup, tab_recent = st.tabs(["선발 투수", "팀 타선", "최근 5경기"])

        away, home = g["away"], g["home"]
        ap, hp = pitcher_stats["away"], pitcher_stats["home"]
        al, hl = lineup["away"], lineup["home"]

        # ── 선발 투수 탭 ──────────────────────────────────────────
        with tab_pitcher:
            PITCHER_LABELS = {
                "ERA":     "평균자책(ERA)",
                "WHIP":    "WHIP",
                "WAR":     "WAR",
                "innings": "선발평균이닝",
                "QS":      "QS(퀄리티스타트)",
                "record":  "시즌 성적",
            }
            rows = []
            for key, label in PITCHER_LABELS.items():
                a_val = ap.get(key, "-")
                h_val = hp.get(key, "-")
                if a_val != "-" or h_val != "-":
                    rows.append({"항목": label, away: a_val, home: h_val})

            st.caption(f"{away} **{ap['name']}** vs {home} **{hp['name']}**")
            st.table(rows)

            # ── 연도별 히스토리 (ERA / FIP / WHIP / 성적) ────────────────
            ah = ap.get("history", {})
            hh = hp.get("history", {})
            if ah or hh:
                HIST_LABELS = [
                    ("ERA",    "ERA"),
                    ("FIP",    "FIP"),
                    ("WHIP",   "WHIP"),
                    ("record", "시즌 성적"),
                ]
                for yr in (str(CURRENT_YEAR), str(PREV_YEAR)):
                    yr_rows = []
                    for key, label in HIST_LABELS:
                        a_val = ah.get(yr, {}).get(key, "N/A")
                        h_val = hh.get(yr, {}).get(key, "N/A")
                        if a_val != "N/A" or h_val != "N/A":
                            yr_rows.append({"항목": label, away: a_val, home: h_val})
                    if yr_rows:
                        st.caption(f"**{yr}시즌 기록**")
                        st.table(yr_rows)

        # ── 팀 타선 탭 ───────────────────────────────────────────
        with tab_lineup:
            LINEUP_LABELS = {
                "season_record":     "시즌 성적",
                "team_avg":          "팀 타율",
                "team_OPS":          "팀 OPS",
                "team_ERA":          "팀 ERA",
                "team_WHIP":         "팀 WHIP",
                "team_runs_allowed": "팀 실점",
            }
            rows = []
            for key, label in LINEUP_LABELS.items():
                a_val = al.get(key, "-")
                h_val = hl.get(key, "-")
                if a_val != "-" or h_val != "-":
                    rows.append({"항목": label, away: a_val, home: h_val})

            st.table(rows)

            def hitter_line(h: dict) -> str:
                cur_ops = h['OPS']
                hist = h.get("history", {})
                prev_ops = hist.get(str(PREV_YEAR), {}).get("OPS", "")
                parts = [f"{CURRENT_YEAR} OPS {cur_ops}"]
                if prev_ops:
                    parts.append(f"{PREV_YEAR} OPS {prev_ops}")
                return f"- {h['name']} ({' / '.join(parts)})"

            col_a, col_h = st.columns(2)
            with col_a:
                st.markdown(f"**{away} 주목할 타자**")
                for h in al.get("key_hitters", []):
                    st.markdown(hitter_line(h))
            with col_h:
                st.markdown(f"**{home} 주목할 타자**")
                for h in hl.get("key_hitters", []):
                    st.markdown(hitter_line(h))

        # ── 최근 5경기 탭 ────────────────────────────────────────
        with tab_recent:
            RESULT_ICON = {"승": "✅", "패": "❌", "무": "➖"}

            def recent_table(games_list):
                return [
                    {
                        "결과": RESULT_ICON.get(g_["result"], "?") + " " + g_["result"],
                        "날짜": g_["date"],
                        "홈/원정": g_["home_away"],
                        "상대": g_["opponent"],
                        "점수": f"{g_['my_score']}-{g_['opp_score']}",
                    }
                    for g_ in games_list
                ]

            col_a, col_h = st.columns(2)
            with col_a:
                st.markdown(f"**{away}**")
                rows_a = recent_table(recent.get("away", []))
                if rows_a:
                    st.table(rows_a)
                else:
                    st.caption("데이터 없음")
            with col_h:
                st.markdown(f"**{home}**")
                rows_h = recent_table(recent.get("home", []))
                if rows_h:
                    st.table(rows_h)
                else:
                    st.caption("데이터 없음")

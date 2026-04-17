import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from datetime import datetime

from crawlers.schedule import fetch_game_list
from crawlers.pitcher import fetch_pitcher_stats
from crawlers.lineup import fetch_lineup
from analysis.prompt import build_prompt
from analysis.gemini import analyze_stream

st.set_page_config(page_title="KBO 매치업 분석기", page_icon="⚾", layout="centered")
st.title("⚾ KBO 선발 매치업 분석기")

# 사이드바
with st.sidebar:
    st.header("설정")
    date = st.date_input("날짜", value=datetime.today())
    date_str = date.strftime("%Y-%m-%d")
    my_team = st.text_input("내 팀 (선택)", placeholder="예: 두산, LG")

# 경기 목록 로드
@st.cache_data(ttl=300)
def load_games(date_str):
    return fetch_game_list(date_str)

with st.spinner("경기 목록 불러오는 중..."):
    try:
        games = load_games(date_str)
    except Exception as e:
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
            pitcher_stats = fetch_pitcher_stats(g["s_no"])
            lineup = fetch_lineup(g["s_no"])
            prompt = build_prompt(g, pitcher_stats, lineup, my_team=my_team or None)
        except Exception as e:
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
        st.error(f"분석 실패: {e}")

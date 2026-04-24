from crawlers.player_stats import CURRENT_YEAR

SYSTEM_PROMPT = """
너는 KBO 야구 전문 분석가야.
주어진 스탯 데이터를 바탕으로 오늘 경기의 매치업을 분석하는 게 역할이야.

분석 원칙:
- 감이나 팬심이 아닌 숫자 근거로만 판단해
- KBO 공식 사이트 기반 데이터를 사용하되, 시즌 초반 샘플 부족 같은 한계는 솔직하게 언급해
- 승부 예측이 아닌 "유리함의 근거"를 설명하는 게 목적이야
- 어려운 야구 용어는 괄호로 간단히 설명해줘 (예: WHIP(이닝당 출루 허용))
- 답변은 한국어로, 간결하고 명확하게

말투 규칙 (반드시 준수):
- 모든 문장을 ~음, ~임, ~함, ~됨 등 '음체'로 끝낼 것
- ~습니다, ~입니다, ~해요, ~합니다 등 존댓말 절대 금지
- ~다 로 끝나는 문어체도 금지
- 올바른 예: "ERA가 낮아 안정적임.", "타선 OPS가 리그 최상위권에 속함.", "투수전 가능성이 높음."
- 잘못된 예: "ERA가 낮습니다.", "좋은 컨디션을 보여주고 있어요.", "유리한 상황입니다."
""".strip()


def build_prompt(
    game: dict,
    pitcher_stats: dict,
    lineup: dict,
    recent_games: dict | None = None,
    my_team: str | None = None,
) -> str:
    """
    크롤링 데이터를 Claude 프롬프트 텍스트로 변환.

    Args:
        game:          schedule.fetch_game_list() 결과 중 1개
        pitcher_stats: pitcher.fetch_pitcher_stats() 결과
        lineup:        lineup.fetch_lineup() 결과
        recent_games:  {"away": [...], "home": [...]} — recent_games.fetch_recent_games() 결과
        my_team:       팬 시각 필터링용 팀명 (없으면 중립)
    """
    away = game["away"]
    home = game["home"]
    date = game["date"]

    ap = pitcher_stats["away"]
    hp = pitcher_stats["home"]
    al = lineup["away"]
    hl = lineup["home"]

    def fmt_hitters(hitters: list) -> str:
        if not hitters:
            return "  정보 없음"
        return "\n".join(f"  - {h['name']} (OPS {h['OPS']})" for h in hitters)

    def fmt_pitcher_history(label: str, p: dict, away_name: str, home_name: str) -> str:
        """선발 투수 연도별 비교 마크다운 테이블 생성."""
        ah = p["away"].get("history", {})
        hh = p["home"].get("history", {})
        if not ah and not hh:
            return ""

        years = sorted({*ah.keys(), *hh.keys()}, reverse=True)

        def val(h: dict, yr: str, key: str) -> str:
            return h.get(yr, {}).get(key, "N/A") or "N/A"

        rows = []
        for stat_key, stat_label in [
            ("ERA", "ERA"),
            ("FIP", "FIP"),
            ("WHIP", "WHIP"),
            ("record", "시즌 성적"),
        ]:
            for yr in years:
                a_val = val(ah, yr, stat_key)
                h_val = val(hh, yr, stat_key)
                # FIP가 모두 N/A면 행 생략
                if a_val == "N/A" and h_val == "N/A":
                    continue
                rows.append(f"| {stat_label} ({yr}) | {a_val} | {h_val} |")

        if not rows:
            return ""

        lines = [
            "### 선발 투수 연도별 비교",
            f"| 항목 | {away} ({away_name}) | {home} ({home_name}) |",
            "|------|---------|---------|",
        ] + rows
        return "\n".join(lines)

    def fmt_hitter_history(team_label: str, hitters: list) -> str:
        """타자 연도별 OPS 목록 생성."""
        lines = []
        for h in hitters:
            hist = h.get("history", {})
            if not hist:
                continue
            years = sorted(hist.keys(), reverse=True)
            parts = []
            prev_ops = None
            for yr in years:
                ops = hist[yr].get("OPS", "N/A")
                parts.append(f"{yr} OPS {ops}")
                if yr == str(CURRENT_YEAR - 1):
                    prev_ops = ops
            # 방향 표시 (현재연도 vs 전년)
            cur_ops_str = hist.get(str(CURRENT_YEAR), {}).get("OPS")
            arrow = ""
            if cur_ops_str and prev_ops and cur_ops_str != "N/A" and prev_ops != "N/A":
                try:
                    arrow = " → 상승" if float(cur_ops_str) > float(prev_ops) else " → 하락"
                except ValueError:
                    pass
            lines.append(f"- {h['name']}: {' / '.join(parts)}{arrow}")
        return "\n".join(lines) if lines else "  정보 없음"

    def fmt_recent(games: list) -> str:
        if not games:
            return "  정보 없음"
        icon = {"승": "✅", "패": "❌", "무": "➖"}
        return "\n".join(
            f"  {icon.get(g['result'], '?')} {g['date']} ({g['home_away']}) vs {g['opponent']} "
            f"{g['my_score']}-{g['opp_score']}"
            for g in games
        )

    # 최근 N경기 섹션
    recent_section = ""
    if recent_games:
        away_recent = fmt_recent(recent_games.get("away", []))
        home_recent = fmt_recent(recent_games.get("home", []))
        n = max(len(recent_games.get("away", [])), len(recent_games.get("home", [])))
        recent_section = f"""
### 최근 {n}경기 흐름
**{away}**
{away_recent}

**{home}**
{home_recent}
"""

    fan_clause = ""
    if my_team:
        fan_clause = f"\n\n※ 분석 시 {my_team} 팬 입장에서 해당 팀에 유리한 포인트를 먼저 짚어줘."

    # 연도별 비교 섹션
    pitcher_history_section = fmt_pitcher_history(
        "선발 투수 연도별 비교", pitcher_stats, ap["name"], hp["name"]
    )
    if pitcher_history_section:
        pitcher_history_section = "\n" + pitcher_history_section + "\n"

    away_hitter_hist = fmt_hitter_history(away, al.get("key_hitters", []))
    home_hitter_hist = fmt_hitter_history(home, hl.get("key_hitters", []))
    hitter_history_section = ""
    if away_hitter_hist != "  정보 없음" or home_hitter_hist != "  정보 없음":
        hitter_history_section = f"""
### 주목 타자 연도별 OPS
**{away}**
{away_hitter_hist}

**{home}**
{home_hitter_hist}
"""

    prompt = f"""
다음은 {date} KBO 경기 데이터야. 데이터를 바탕으로 오늘 매치업을 분석해줘.

## 경기: {away} (원정) vs {home} (홈)

### 선발 투수
| 항목 | {away} ({ap['name']}) | {home} ({hp['name']}) |
|------|----------------------|----------------------|
| ERA  | {ap.get('ERA', '-')} | {hp.get('ERA', '-')} |
| WHIP | {ap.get('WHIP', '-')} | {hp.get('WHIP', '-')} |
| WAR | {ap.get('WAR', '-')} | {hp.get('WAR', '-')} |
| 선발평균이닝 | {ap.get('innings', '-')} | {hp.get('innings', '-')} |
| QS | {ap.get('QS', '-')} | {hp.get('QS', '-')} |
| 시즌 성적 | {ap.get('record', '-')} | {hp.get('record', '-')} |
{pitcher_history_section}
### 팀 타선
| 항목 | {away} | {home} |
|------|--------|--------|
| 시즌 성적 | {al.get('season_record', '-')} | {hl.get('season_record', '-')} |
| 팀 타율 | {al.get('team_avg', '-')} | {hl.get('team_avg', '-')} |
| 팀 OPS | {al.get('team_OPS', '-')} | {hl.get('team_OPS', '-')} |
| 팀 ERA | {al.get('team_ERA', '-')} | {hl.get('team_ERA', '-')} |
| 팀 실점 | {al.get('team_runs_allowed', '-')} | {hl.get('team_runs_allowed', '-')} |

### 주목할 타자
**{away}**
{fmt_hitters(al.get('key_hitters', []))}

**{home}**
{fmt_hitters(hl.get('key_hitters', []))}
{hitter_history_section}{recent_section}{fan_clause}

---
아래 형식을 **그대로** 사용해서 분석해줘. 섹션 제목, 순서, 구조를 절대 바꾸지 마.

## 1. 유리한 팀
**[팀명]** — (이유 2~3줄)

## 2. 핵심 매치업 포인트
(오늘 승부를 가를 변수 1가지, 2줄 이내)

## 3. 예상 경기 성격
**[투수전 / 타격전 / 접전 중 하나만 선택]** — (한 줄 근거)

## 4. 주의 변수
(이 예측이 틀릴 수 있는 이유 1가지, 2줄 이내)
""".strip()

    return prompt

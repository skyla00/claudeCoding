SYSTEM_PROMPT = """
너는 KBO 야구 전문 분석가야.
주어진 스탯 데이터를 바탕으로 오늘 경기의 매치업을 분석하는 게 역할이야.

분석 원칙:
- 감이나 팬심이 아닌 숫자 근거로만 판단해
- statiz에서 가져온 데이터 기반으로 해석하되, 시즌 초반 샘플 부족 같은 한계는 솔직하게 언급해
- 승부 예측이 아닌 "유리함의 근거"를 설명하는 게 목적이야
- 어려운 야구 용어는 괄호로 간단히 설명해줘 (예: WHIP(이닝당 출루 허용))
- 답변은 한국어로, 간결하고 명확하게
""".strip()


def build_prompt(game: dict, pitcher_stats: dict, lineup: dict, my_team: str | None = None) -> str:
    """
    크롤링 데이터를 Claude 프롬프트 텍스트로 변환.

    Args:
        game:          schedule.fetch_game_list() 결과 중 1개
        pitcher_stats: pitcher.fetch_pitcher_stats() 결과
        lineup:        lineup.fetch_lineup() 결과
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

    fan_clause = ""
    if my_team:
        fan_clause = f"\n\n※ 분석 시 {my_team} 팬 입장에서 해당 팀에 유리한 포인트를 먼저 짚어줘."

    prompt = f"""
다음은 {date} KBO 경기 데이터야. 데이터를 바탕으로 오늘 매치업을 분석해줘.

## 경기: {away} (원정) vs {home} (홈)

### 선발 투수
| 항목 | {away} ({ap['name']}) | {home} ({hp['name']}) |
|------|----------------------|----------------------|
| ERA  | {ap.get('ERA', '-')} | {hp.get('ERA', '-')} |
| WHIP | {ap.get('WHIP', '-')} | {hp.get('WHIP', '-')} |
| 피안타율 | {ap.get('opp_avg', '-')} | {hp.get('opp_avg', '-')} |
| 탈삼진 | {ap.get('K', '-')} | {hp.get('K', '-')} |
| 볼넷 | {ap.get('BB', '-')} | {hp.get('BB', '-')} |
| WAR | {ap.get('WAR', '-')} | {hp.get('WAR', '-')} |
| 시즌 성적 | {ap.get('record', '-')} | {hp.get('record', '-')} |

### 팀 타선
| 항목 | {away} | {home} |
|------|--------|--------|
| 시즌 성적 | {al.get('season_record', '-')} | {hl.get('season_record', '-')} |
| 팀 타율 | {al.get('team_avg', '-')} | {hl.get('team_avg', '-')} |
| 팀 OPS | {al.get('team_OPS', '-')} | {hl.get('team_OPS', '-')} |
| 팀 ERA | {al.get('team_ERA', '-')} | {hl.get('team_ERA', '-')} |
| 팀 득점 | {al.get('team_runs', '-')} | {hl.get('team_runs', '-')} |
| 팀 실점 | {al.get('team_runs_allowed', '-')} | {hl.get('team_runs_allowed', '-')} |

### 주목할 타자
**{away}**
{fmt_hitters(al.get('key_hitters', []))}

**{home}**
{fmt_hitters(hl.get('key_hitters', []))}
{fan_clause}

---
위 데이터를 바탕으로 아래 형식으로 분석해줘:

1. **오늘 유리한 팀**: (팀명) — 이유를 3줄 이내로
2. **핵심 매치업 포인트**: 오늘 경기의 승부를 가를 변수 1가지
3. **예상 경기 성격**: 투수전 / 타격전 / 접전 중 1개 + 한 줄 근거
4. **주의 변수**: 이 예측이 틀릴 수 있는 이유 1가지
""".strip()

    return prompt

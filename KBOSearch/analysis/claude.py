import os
import sys
import anthropic
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.prompt import SYSTEM_PROMPT

MODEL = "claude-sonnet-4-6"

# .env 파일 직접 로드
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return anthropic.Anthropic(api_key=api_key)


def analyze(prompt: str) -> str:
    """프롬프트를 Claude에 전달하고 분석 결과 반환"""
    client = get_client()
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def analyze_stream(prompt: str):
    """스트리밍 방식으로 분석 결과 생성 (Streamlit용)"""
    client = get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


if __name__ == "__main__":
    import sys
    import argparse
    sys.path.insert(0, __file__ + "/../..")

    from crawlers.schedule import fetch_game_list
    from crawlers.pitcher import fetch_pitcher_stats
    from crawlers.lineup import fetch_lineup
    from analysis.prompt import build_prompt

    parser = argparse.ArgumentParser(description="KBO 매치업 Claude 분석")
    parser.add_argument("--date", type=str, default=None, help="조회 날짜 (YYYY-MM-DD). 기본값: 어제")
    parser.add_argument("--team", type=str, default=None, help="내 팀 이름 (예: 두산, LG)")
    parser.add_argument("--game", type=int, default=0, help="분석할 경기 번호 (0부터, 기본값: 0)")
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    if not games:
        print("경기 없음")
        sys.exit(0)

    # 선택한 경기 출력
    for i, g in enumerate(games):
        print(f"[{i}] {g['away']} vs {g['home']}")

    g = games[args.game]
    print(f"\n분석 중: {g['away']} vs {g['home']} ...\n")

    pitcher_stats = fetch_pitcher_stats(g["game_id"])
    lineup = fetch_lineup(g["away"], g["home"])
    prompt = build_prompt(g, pitcher_stats, lineup, my_team=args.team)

    print("=" * 50)
    result = analyze(prompt)
    print(result)

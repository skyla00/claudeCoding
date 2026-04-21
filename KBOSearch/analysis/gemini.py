import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from analysis.prompt import SYSTEM_PROMPT

MODEL = "gemini-2.5-flash-lite"

# .env 파일 직접 로드
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return genai.Client(api_key=api_key)


def analyze(prompt: str, retries: int = 3) -> str:
    """프롬프트를 Gemini에 전달하고 분석 결과 반환 (503 시 재시도)"""
    import time
    client = get_client()
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1024,
                    temperature=0.0,
                ),
            )
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < retries - 1:
                print(f"서버 과부하, {5}초 후 재시도... ({attempt + 1}/{retries})")
                time.sleep(5)
            else:
                raise
    return ""


def analyze_stream(prompt: str):
    """스트리밍 방식으로 분석 결과 생성 (Streamlit용)"""
    client = get_client()
    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=1024,
            temperature=0.0,
        ),
    ):
        if chunk.text:
            yield chunk.text


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from crawlers.schedule import fetch_game_list
    from crawlers.pitcher import fetch_pitcher_stats
    from crawlers.lineup import fetch_lineup
    from analysis.prompt import build_prompt

    parser = argparse.ArgumentParser(description="KBO 매치업 Gemini 분석")
    parser.add_argument("--date", type=str, default=None, help="조회 날짜 (YYYY-MM-DD). 기본값: 어제")
    parser.add_argument("--team", type=str, default=None, help="내 팀 이름 (예: 두산, LG)")
    parser.add_argument("--game", type=int, default=0, help="분석할 경기 번호 (0부터, 기본값: 0)")
    args = parser.parse_args()

    games = fetch_game_list(args.date)
    if not games:
        print("경기 없음")
        sys.exit(0)

    for i, g in enumerate(games):
        print(f"[{i}] {g['away']} vs {g['home']}")

    g = games[args.game]
    print(f"\n분석 중: {g['away']} vs {g['home']} ...\n")

    pitcher_stats = fetch_pitcher_stats(g["s_no"])
    lineup = fetch_lineup(g["s_no"])
    prompt = build_prompt(g, pitcher_stats, lineup, my_team=args.team)

    print("=" * 50)
    result = analyze(prompt)
    print(result)

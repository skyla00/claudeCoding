"""
같은 경기를 3회 반복 분석해서 결과 일관성 확인.
usage: python3 test_consistency.py --date 2026-04-21
"""
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crawlers.schedule import fetch_game_list
from crawlers.pitcher import fetch_pitcher_stats
from crawlers.lineup import fetch_lineup
from analysis.prompt import build_prompt
from analysis.provider import analyze

REPEAT = 3  # 경기당 반복 횟수


def extract_sections(text: str) -> dict:
    """분석 결과에서 4개 섹션 추출"""
    sections = {}
    for i, title in enumerate(["1. 유리한 팀", "2. 핵심 매치업 포인트", "3. 예상 경기 성격", "4. 주의 변수"]):
        # 해당 섹션 시작 위치
        start = text.find(f"## {title}")
        if start == -1:
            sections[title] = "[섹션 없음]"
            continue
        # 다음 섹션 시작 전까지 추출
        next_titles = [f"## {j+1}." for j in range(i+1, 4)]
        end = len(text)
        for nt in next_titles:
            pos = text.find(nt, start + 1)
            if pos != -1:
                end = min(end, pos)
        sections[title] = text[start:end].strip()
    return sections


def compare_runs(matchup: str, runs: list[str]):
    """3회 결과 비교 출력"""
    print(f"\n{'='*60}")
    print(f"  {matchup}")
    print(f"{'='*60}")

    section_results = [extract_sections(r) for r in runs]
    titles = ["1. 유리한 팀", "2. 핵심 매치업 포인트", "3. 예상 경기 성격", "4. 주의 변수"]

    for title in titles:
        values = [s.get(title, "") for s in section_results]
        # 모든 결과가 동일한지 확인
        all_same = all(v == values[0] for v in values)
        status = "✅ 동일" if all_same else "⚠️  다름"
        print(f"\n[{status}] {title}")
        if not all_same:
            for i, v in enumerate(values, 1):
                print(f"  --- 실행 {i} ---")
                print(f"  {v[:200]}")  # 200자까지만 출력


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="날짜 (YYYY-MM-DD), 기본값: 오늘")
    parser.add_argument("--game", type=int, default=None, help="분석할 경기 번호 (0부터). 없으면 전체 경기")
    parser.add_argument("--repeat", type=int, default=REPEAT, help=f"경기당 반복 횟수 (기본: {REPEAT})")
    args = parser.parse_args()

    from datetime import datetime
    date_str = args.date or datetime.today().strftime("%Y-%m-%d")

    print(f"\n날짜: {date_str}")
    print("경기 목록 불러오는 중...")
    games = fetch_game_list(date_str)

    if not games:
        print("경기 없음")
        sys.exit(0)

    for i, g in enumerate(games):
        print(f"  [{i}] {g['away']} vs {g['home']}")

    if args.game is not None:
        if args.game < 0 or args.game >= len(games):
            raise SystemExit(f"--game은 0부터 {len(games) - 1} 사이여야 함")
        games = [games[args.game]]

    print(f"\n총 {len(games)}경기 × {args.repeat}회 반복 분석 시작\n")

    for g in games:
        matchup = f"{g['away']} vs {g['home']}"
        print(f"\n데이터 수집: {matchup}...")
        pitcher_stats = fetch_pitcher_stats(g["game_id"])
        lineup = fetch_lineup(g["away"], g["home"])
        prompt = build_prompt(g, pitcher_stats, lineup)

        runs = []
        for i in range(args.repeat):
            print(f"  분석 {i+1}/{args.repeat}...")
            result = analyze(prompt)
            runs.append(result)

        compare_runs(matchup, runs)

    print(f"\n\n{'='*60}")
    print("테스트 완료")

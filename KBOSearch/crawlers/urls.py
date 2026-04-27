"""KBO 공식 사이트 URL 상수와 생성 함수."""

BASE_URL = "https://www.koreabaseball.com"

TEAM_RANK_URL = f"{BASE_URL}/Record/TeamRank/TeamRankDaily.aspx"
TEAM_HITTER_URL = f"{BASE_URL}/Record/Team/Hitter/Basic2.aspx"
TEAM_PITCHER_URL = f"{BASE_URL}/Record/Team/Pitcher/Basic1.aspx"
PLAYER_HITTER_URL = f"{BASE_URL}/Record/Player/HitterBasic/Basic2.aspx"
PLAYER_PITCHER_URL = f"{BASE_URL}/Record/Player/PitcherBasic/Basic1.aspx"


def schedule_url(game_date: str) -> str:
    """일정 페이지 URL 생성. game_date는 YYYYMMDD 형식."""
    return f"{BASE_URL}/Schedule/Schedule.aspx?gameDate={game_date}"


def game_center_url(game_date: str, game_id: str, section: str) -> str:
    """게임센터 섹션 URL 생성."""
    return (
        f"{BASE_URL}/Schedule/GameCenter/Main.aspx"
        f"?gameDate={game_date}&gameId={game_id}&section={section}"
    )

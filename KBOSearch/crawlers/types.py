"""크롤러 간에 주고받는 데이터 타입 정의."""

from __future__ import annotations

from typing import TypedDict


class Game(TypedDict):
    game_id: str
    date: str
    away: str
    home: str
    time: str
    away_pitcher: str
    home_pitcher: str


class PitcherStats(TypedDict, total=False):
    name: str
    record: str
    ERA: str
    WHIP: str
    WAR: str
    G: str
    innings: str
    QS: str
    history: dict[str, dict[str, str]]


class PitcherStatsResponse(TypedDict):
    away: PitcherStats
    home: PitcherStats


class HitterStats(TypedDict, total=False):
    name: str
    OPS: str
    history: dict[str, dict[str, str]]


class TeamLineupStats(TypedDict):
    season_record: str
    team_avg: str
    team_OPS: str
    team_ERA: str
    team_WHIP: str
    team_runs_allowed: str
    key_hitters: list[HitterStats]


class LineupResponse(TypedDict):
    away: TeamLineupStats
    home: TeamLineupStats


class RecentGame(TypedDict):
    date: str
    opponent: str
    result: str
    my_score: int
    opp_score: int
    home_away: str


class ScheduleResult(TypedDict):
    date: str
    away: str
    away_score: int
    home: str
    home_score: int

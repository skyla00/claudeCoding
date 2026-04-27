"""KBO 게임센터 HTML 파싱 헬퍼."""

from __future__ import annotations

from bs4 import BeautifulSoup


def parse_starting_pitcher_names(soup: BeautifulSoup) -> tuple[str, str]:
    """START_PIT 테이블 또는 종료 경기 카드에서 원정/홈 선발 이름 반환."""
    table_names = _parse_starting_pitchers_from_table(soup)
    if len(table_names) >= 2:
        return table_names[0], table_names[1]

    card_infos = parse_pitcher_infos_from_selected_card(soup)
    return (
        card_infos[0]["name"] if len(card_infos) > 0 else "미정",
        card_infos[1]["name"] if len(card_infos) > 1 else "미정",
    )


def parse_pitcher_infos_from_selected_card(soup: BeautifulSoup) -> list[dict[str, str]]:
    """종료 경기 카드의 '승 임찬규' 같은 문구에서 결과와 이름 추출."""
    selected_game = soup.select_one(".game-cont.on")
    pitcher_nodes = selected_game.select(".today-pitcher p") if selected_game else []
    return [_pitcher_info_from_card(p) for p in pitcher_nodes[:2]]


def _parse_starting_pitchers_from_table(soup: BeautifulSoup) -> list[str]:
    """예정/현재 경기 START_PIT 테이블에서 선발 이름 추출."""
    names = []
    for td in soup.find_all("td", class_="pitcher"):
        span = td.select_one("span.name")
        if span:
            names.append(span.get_text(strip=True))
    return names


def _pitcher_info_from_card(node) -> dict[str, str]:
    result_span = node.find("span")
    result = result_span.get_text(strip=True) if result_span else ""
    if result_span:
        result_span.decompose()
    name = node.get_text(strip=True) or "미정"
    return {"name": name, "record": result or "-"}

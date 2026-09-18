"""Fetch a scorers leaderboard, NOT a representative league-wide player dataset.
Missing statistics remain missing. Snapshot time is recorded; historical responses
must still be checked against the valuation snapshot before use.
"""
from datetime import datetime, timezone
import time

from config import PREMIER_LEAGUE_ID


class RateLimitError(Exception):
    pass


def _get(endpoint: str, params: dict | None = None) -> dict:
    from src.football_api import request
    return request(endpoint, params)


def get_top_scorers(season: int, limit: int = 100, competition: str = PREMIER_LEAGUE_ID) -> list[dict]:
    """
    Fetch the top `limit` scorers for one Premier League season.

    `season` is the year the season started, e.g. 2023 for the 2023/24 season.
    """
    data = _get(f"/competitions/{competition}/scorers", params={"season": season, "limit": limit})
    return scorer_rows(data, season)


def scorer_rows(data, season):
    """Normalize scorer responses without inventing missing performance data."""
    rows = []
    for entry in data.get("scorers", []):
        player = entry["player"]
        rows.append({
            "player_id": player["id"],
            "name": player["name"],
            "position": player.get("position") or "Unknown",
            "date_of_birth": player.get("dateOfBirth"),
            "nationality": player.get("nationality"),
            "team": entry["team"]["name"],
            "season": season,
            "data_kind": "scorers_api",
            "stats_source": "football-data.org/v4/scorers",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "appearances": entry.get("playedMatches"),
            "goals": entry.get("goals"),
            "assists": entry.get("assists"),
            "penalties": entry.get("penalties"),
        })
    return rows


def collect_seasons(seasons: list[int], limit: int = 100, pause: float = 6.5) -> list[dict]:
    """
    Loop over multiple seasons, respecting the free tier's 10 requests/minute cap.
    `pause` defaults to 6.5s between calls (~9 req/min) to leave headroom.
    """
    all_rows = []
    for season in seasons:
        print(f"Fetching PL top scorers for {season}/{season + 1}...")
        all_rows.extend(get_top_scorers(season, limit=limit))
        time.sleep(pause)
    return all_rows

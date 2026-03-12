# src/features/teams.py

# ── Standard Library Imports ──────────────────────────────────────────

from typing import List, Dict, Set

# ── Local Library Imports ─────────────────────────────────────────────

from features._base import apply_features, FeatureFn
from constants import DataKeys, DefaultValues

# ── Helpers ───────────────────────────────────────────────────────────

def _matches_for_team(team_id: str, matches: List[Dict]) -> List[Dict]:
    """Return all matches in which this team participated"""
    return [
        m for m in matches
        if m.get(DataKeys.Match.TEAM_1_ID) == team_id
        or m.get(DataKeys.Match.TEAM_2_ID) == team_id
    ]


def _completed_matches_for_team(
    team_id: str,
    matches: List[Dict],
) -> List[Dict]:
    """Return all completed matches in which this team participated."""
    return [
        m for m in _matches_for_team(team_id, matches)
        if m.get(DataKeys.Match.IS_PLAYED)
    ]


def _team_won(team_id: str, match: Dict) -> bool:
    """Return True if this team won the match."""
    winner = match.get(DataKeys.Match.WINNER)
    if winner == 1:
        return match.get(DataKeys.Match.TEAM_1_ID) == team_id
    if winner == 2:
        return match.get(DataKeys.Match.TEAM_2_ID) == team_id
    return False


def _team_score(team_id: str, match: Dict) -> int | None:
    """Return this team's score in a match."""
    if match.get(DataKeys.Match.TEAM_1_ID) == team_id:
        return match.get(DataKeys.Match.TEAM_1_SCORE)
    if match.get(DataKeys.Match.TEAM_2_ID) == team_id:
        return match.get(DataKeys.Match.TEAM_2_SCORE)
    return None

# ── Feature functions ─────────────────────────────────────────────────

def _match_record(record: Dict, matches: List[Dict] = [], **_) -> Dict:
    """
    Compute wins, lossed, draws, and total matches played for a team.
    """
    team_id = record[DataKeys.Team.ID]
    played  = _completed_matches_for_team(team_id, matches)
    wins    = 0
    losses  = 0
    draws   = 0

    for m in played:
        winner = m.get(DataKeys.Match.WINNER)
        if winner == 0:
            draws += 1
        elif _team_won(team_id, m):
            wins += 1
        else:
            losses += 1

    return {
        DataKeys.Team.MATCHES_PLAYED: len(played),
        DataKeys.Team.WINS:           wins,
        DataKeys.Team.LOSSES:         losses,
        DataKeys.Team.DRAWS:          draws,
    }


def _win_rate(record: Dict, **_) -> Dict:
    """
    Compute win rate as wins / matches_played.
    Requires _match_record to have run first.
    None if no matches played.
    """
    played = record.get(DataKeys.Team.MATCHES_PLAYED, 0)
    wins   = record.get(DataKeys.Team.WINS, 0)
    if not played:
        return {DataKeys.Team.WIN_RATE: None}
    return {DataKeys.Team.WIN_RATE: round(wins / played, 4)}


def _score_share(record: Dict, matches: List[Dict] = [], **_) -> Dict:
    """
    Compute the team's average share of total games scored across all
    completed matches. None if no completed matches.
    """
    team_id = record[DataKeys.Team.ID]
    played = _completed_matches_for_team(team_id, matches)

    shares = []
    for m in played:
        total = m.get(DataKeys.Match.TOTAL_GAMES)
        score = _team_score(team_id, m)
        if total and score is not None:
            shares.append(score / total)

    if not shares:
        return {DataKeys.Team.SCORE_SHARE: None}
    return {DataKeys.Team.SCORE_SHARE: round(sum(shares) / len(shares), 4)}


def _categories_played(record: Dict, matches: List[Dict] = [], **_) -> Dict:
    """
    List the distinct categories this team has competed in.
    """
    team_id = record[DataKeys.Team.ID]
    categories: Set[str] = {
        m[DataKeys.Match.CATEGORY]
        for m in _matches_for_team(team_id, matches)
        if m.get(DataKeys.Match.CATEGORY)
    }
    return {DataKeys.Team.CATEGORIES: sorted(categories)}

# ── Registry ──────────────────────────────────────────────────────────
# Order matters; _win_rate depends on fields set by _match_record.

TEAM_FEATURES: List[FeatureFn] = [
    _match_record,
    _win_rate,
    _score_share,
    _categories_played,
]

# ── Entry point ───────────────────────────────────────────────────────

def enrich_teams(
    teams: List[Dict],
    matches: List[Dict] = [],
    **context,
) -> List[Dict]:
    """
    Enrich all team records with derived features computed from match
    history. Accepts and returns the team registry as a list of dicts.

    Parameters
    ----------
    teams : List[Dict]
        Team registry from consolidated/teams.json.
    matches : List[Dict]
        Enriched match records (run enrich_matches first).
    **context
        Additional context passed through to feature functions.

    Returns
    -------
    List[Dict]
        Enriched team registry with additional derived fields per team.
    """
    return apply_features(teams, TEAM_FEATURES, matches=matches, **context)

# src/features/players.py

from typing import List, Dict, Set

from features._base import apply_features, FeatureFn
from constants import DataKeys, DefaultValues

# ── Helpers ───────────────────────────────────────────────────────────

def _team_ids_for_player(pid: str, teams: List[Dict]) -> Set[str]:
    """Return all team IDs that include this player."""
    return {
        team[DataKeys.Team.ID]
        for team in teams
        if team.get(DataKeys.Team.PLAYER_1) == pid
        or team.get(DataKeys.Team.PLAYER_2) == pid
    }


def _matches_for_player(
    pid: str,
    matches: List[Dict],
    teams: List[Dict],
) -> List[Dict]:
    """Return all completed matches in which a player participated."""
    player_team_ids = _team_ids_for_player(pid, teams)
    return [
        m for m in matches
        if m.get(DataKeys.Match.IS_PLAYED)
        and m.get(DataKeys.Match.IS_VALID)
        and (
            m.get(DataKeys.Match.TEAM_1_ID) in player_team_ids
            or m.get(DataKeys.Match.TEAM_2_ID) in player_team_ids
        )
    ]


def _player_won(pid: str, match: Dict, teams: List[Dict]) -> bool:
    """Return True if the player's team won the match."""
    winner = match.get(DataKeys.Match.WINNER)
    if winner == 1:
        winning_team_id = match.get(DataKeys.Match.TEAM_1_ID)
    elif winner == 2:
        winning_team_id = match.get(DataKeys.Match.TEAM_2_ID)
    else:
        return False
    
    return winning_team_id in _team_ids_for_player(pid, teams)

# ── Feature functions ─────────────────────────────────────────────────

def _match_record(
    record: Dict,
    matches: List[Dict] = [],
    teams: List[Dict] = [],
    **_,
) -> Dict:
    """
    Compute wins, lossed, draws, and total matches played for a player.
    """
    pid            = record[DataKeys.Player.ID]
    player_matches = _matches_for_player(pid, matches, teams)
    wins           = 0
    losses         = 0
    draws          = 0

    for m in player_matches:
        winner = m.get(DataKeys.Match.WINNER)
        if winner == 0:
            draws += 1
        elif _player_won(pid, m, teams):
            wins += 1
        else:
            losses += 1

    return {
        DataKeys.Player.MATCHES_PLAYED: len(player_matches),
        DataKeys.Player.WINS:           wins,
        DataKeys.Player.LOSSES:         losses,
        DataKeys.Player.DRAWS:          draws,
    }


def _win_rate(record: Dict, **_) -> Dict:
    """
    Compute win rate as wins / matches_played.
    Requires _match_record to have run first.
    None if no matches played.
    """
    played = record.get(DataKeys.Player.MATCHES_PLAYED, 0)
    wins   = record.get(DataKeys.Player.WINS, 0)
    if not played:
        return {DataKeys.Player.WIN_RATE: None}
    return {DataKeys.Player.WIN_RATE: round(wins / played, 4)}


def _categories_played(
    record: Dict,
    matches: List[Dict] = [],
    teams: List[Dict] = [],
    **_,
) -> Dict:
    """List the distinct categories a player has competed in."""
    pid        = record[DataKeys.Player.ID]
    categories = {
        m[DataKeys.Match.CATEGORY]
        for m in _matches_for_player(pid, matches, teams)
        if m.get(DataKeys.Match.CATEGORY)
    }

    return {DataKeys.Player.CATEGORIES: sorted(categories)}

# ── Registry ──────────────────────────────────────────────────────────
# Order matters; _win_rate depends on fields set by _match_record.

PLAYER_FEATURES: List[FeatureFn] = [
    _match_record,
    _win_rate,
    _categories_played,
]

# ── Entry point ───────────────────────────────────────────────────────

def enrich_players(
    players: List[Dict],
    matches: List[Dict],
    teams: List[Dict],
    **context,
) -> List[Dict]:
    """
    Enrich all player records with derived features.
    Accepts and returns the player registry as a list of records.

    Parameters
    ----------
    players : List[Dict]
        Player registry from consolidated.players.json.
    matches: List[Dict]
        Enriched match records (run enrich_matches first).
    teams : List[Dict]
        Team registry from consolidated/teams.json
        Required to resolve which matches a player participated in.
    **context
        Additional context passed through to feature functions.

    Returns
    -------
    List[Dict]
        Enriched player registry with additional derived fields per
        player.
    """
    return apply_features(
        players, PLAYER_FEATURES, matches=matches, teams=teams, **context
    )

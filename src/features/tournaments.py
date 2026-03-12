# src/features/tournaments.py

from typing import List, Dict, Set

from features._base import apply_features, FeatureFn
from constants import DataKeys

# ── Feature Functions ─────────────────────────────────────────────────

def _match_counts(record: Dict, matches: List[Dict] = [], **_) -> Dict:
    """Count total, completed, and pending matches per tournament."""
    tid                = record[DataKeys.Tournament.ID]
    tournament_matches = [
        m 
        for m in matches
        if m.get(DataKeys.Match.TOURNAMENT) == tid
    ]
    completed             = [
        m
        for m in tournament_matches
        if m.get(DataKeys.Match.IS_PLAYED)
    ]
    played           = [
        m
        for m in completed
        if m.get(DataKeys.Match.IS_VALID)
    ]

    return {
        DataKeys.Tournament.MATCHES:           len(tournament_matches),
        DataKeys.Tournament.MATCHES_COMPLETED: len(completed),
        DataKeys.Tournament.MATCHES_PLAYED:    len(played),
        DataKeys.Tournament.COMPLETION_RATE:   
            round(len(completed) / len(tournament_matches), 4)
            if len(tournament_matches) > 0
            else None,
        DataKeys.Tournament.IS_COMPLETED: 
            len(tournament_matches) == len(completed)
    }


def _unique_players(
    record: Dict,
    matches: List[Dict] = [],
    teams: List[Dict] = [],
    **_,
) -> Dict:
    """
    Count the number of unique players who have participated in this
    tournament. Resolves player IDs via the teams registry.
    """
    tid = record[DataKeys.Tournament.ID]
    pids = set()

    for m in matches:
        if m.get(DataKeys.Match.TOURNAMENT) != tid:
            continue
        for team_key in (DataKeys.Match.TEAM_1_ID, DataKeys.Match.TEAM_2_ID):
            team = next(
                t for t in teams 
                if t.get(DataKeys.Team.ID, "t_na") == m.get(team_key, "m_na")
            )
            if team.get(DataKeys.Team.PLAYER_1):
                pids.add(team[DataKeys.Team.PLAYER_1])
            if team.get(DataKeys.Team.PLAYER_2):
                pids.add(team[DataKeys.Team.PLAYER_2])

    return {DataKeys.Tournament.PLAYERS: len(pids)}

# ── Registry ──────────────────────────────────────────────────────────

TOURNAMENT_FEATURES: List[FeatureFn] = [
    _match_counts,
    _unique_players,
]

# ── Entry point ───────────────────────────────────────────────────────

def enrich_tournaments(
    tournaments: List[Dict],
    matches: List[Dict] = [],
    teams: List[Dict] = [],
    **context,
) -> List[Dict]:
    """
    Enrich all tournament records with derived features.

    Parameters
    ----------
    tournaments : List[Dict]
        Raw tournament records from consolidated/tournaments.json.
    matches : List[Dict]
        Enriched match records (run enrich_matches first).
    teams : List[Dict]
        Team registry from consolidated/teams.json.
        Required to resolve unique player counts.
    **context
        Additional context passed through to feature functions.

    Returns
    -------
    List[Dict]
        Enriched tournament records.
    """
    return apply_features(
        tournaments,
        TOURNAMENT_FEATURES,
        matches=matches,
        teams=teams,
        **context
    )

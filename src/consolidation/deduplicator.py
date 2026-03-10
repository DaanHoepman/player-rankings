# src/consolidation/deduplicator.py

# ── External Imports ──────────────────────────────────────────────────

from hashlib import sha256
from typing import Dict, List, Tuple

# ── Internal Imports ──────────────────────────────────────────────────

from constants import DataKeys
from consolidation.id_resolver import resolve_player

# ── Player Methods ────────────────────────────────────────────────────

def extract_players_from_match(
    match: Dict,
    id_map: Dict[str, str],
    players: Dict[str, Dict],
    input_path: str
) -> List[Dict]:
    """
    Extract the four individual player records from a raw match dict.
    Resolves each player's scraped name to a canonical ID via the 
    id_map, prompting for manual resolution via poup if any name is
    unknown.

    Parameters
    ----------
    match : Dict
        Raw match dict (before parsing). This dict should at least
        contain the following keys: 'team_1', 'team_2', both of which
        have a dictionary value 'player_1' and 'player_2' keys, both of
        which again contain a dictionary value with a 'name' key.
    id_map : Dict[str, str]
        Dict mapping player name to canonical id, updates in place.
    players : Dict[str, Dict]
        Dict mapping players to player record dicts, updated in place.
    input_path : str
        Path to input files.
    
    Returns
    -------
    List[Dict]
        List of up to 4 player dicts with ID and name.
    """
    extracted: List[Dict] = []
    for team_key in ["team_1", "team_2"]:
        for player_key in ["player_1", "player_2"]:
            raw_player   = match[team_key][player_key]
            scraped_name = raw_player["name"]

            canonical_id = resolve_player(
                scraped_name=scraped_name,
                id_map      =id_map,
                players     =players,
                input_path  =input_path,
            )

            extracted.append({
                DataKeys.Player.ID: canonical_id,
                DataKeys.Player.NAME: 
                    players[canonical_id][DataKeys.Player.NAME],
                DataKeys.Player.GENDER: 
                    players[canonical_id][DataKeys.Player.GENDER],
            })

    return extracted


def deduplicate_players(all_players: List[Dict]) -> List[Dict]:
    """
    Deduplicate a flat list of player dicts by player ID.
    Since player IDs are scraped directly, ID is the source of truth,
    no name normalization needed.

    Parameters
    ----------
    all_players : List[Dict]
        Flat list of player dicts including duplicates.
    
    Returns
    -------
    List[Dict]
        List of unique player dicts, one per player ID.
    """
    seen = {}
    for player in all_players:
        canonical_id = player[DataKeys.Player.ID]
        if canonical_id not in seen:
            seen[canonical_id] = player
    return list(seen.values())

# ── Team Methods ──────────────────────────────────────────────────────

def _generate_team_id(player_1_id: str, player_2_id: str) -> str:
    """
    Generate a stable, order-agnostic team ID from two canonical player
    IDs. The pair is sorted alphabetically before hashing so
    (PLR-A, PLR-B) and (PLR-B, PLR-A) always produce the same team ID.

    Parameters
    ----------
    player_1_id, player_2_id : str
        Canonical ID of the player.

    Returns
    -------
    str
        Team ID in the format "TEAM-XXXXXXXX"
    """
    sorted_pair = "-".join(sorted([player_1_id, player_2_id]))
    hash_ext    = sha256(sorted_pair.encode()).hexdigest()[:8].upper()
    return f"TEAM-{hash_ext}"


def _register_team(
    player_1_id: str,
    player_2_id: str,
    teams: Dict[str, Dict],
) -> str:
    """
    Register a team in the teams dict if not already present.
    Player order in the stored record is normalised (alphabetical)
    regardless of the order the players appeared in the raw match.

    Parameters
    ----------
    player_1_id, player_2_id : str
        Canonical ID of the player.
    teams : Dict[str, Dict]
        Mapping of team_id to team record, updated in place

    Returns
    -------
    str
        Canonical team ID
    """
    team_id = _generate_team_id(player_1_id, player_2_id)

    if team_id not in teams:
        p1, p2 = sorted([player_1_id, player_2_id])
        teams[team_id] = {
            DataKeys.Team.ID:       team_id,
            DataKeys.Team.PLAYER_1: p1,
            DataKeys.Team.PLAYER_2: p2,
        }

    return team_id


def extract_teams_from_match(
    match_players: List[Dict],
    teams: Dict[str, Dict],
) -> Tuple[str, str]:
    """
    Derive and register team records for both teams in a match from the
    resolved player list. Registers any new teams in the teams dict in
    place.

    Parameters
    ----------
    match_players : List[Dict]
        List of 4 player dicts as returned by
        extract_players_from_match(), ordered: [team_1_p1, team_1_p2,
        team_2_p1, team_2_p2].
    teams : Dict[str, Dict]
        Mapping of team_id to team record, updated in place.

    Returns
    -------
    Tuple[str, str]
        (team_1_id, team_2_id)
    """
    team_1_id = _register_team(
        player_1_id=match_players[0][DataKeys.Player.ID],
        player_2_id=match_players[1][DataKeys.Player.ID],
        teams      =teams,
    )
    team_2_id = _register_team(
        player_1_id=match_players[2][DataKeys.Player.ID],
        player_2_id=match_players[3][DataKeys.Player.ID],
        teams      =teams,
    )
    return team_1_id, team_2_id

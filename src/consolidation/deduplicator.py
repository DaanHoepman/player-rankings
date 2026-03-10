# src/consolidation/deduplicator.py

from typing import Dict, List

from constants import DataKeys
from consolidation.id_resolver import resolve_player

#-------------------------------------------------------------------------

def extract_players_from_match(
        match: Dict,
        id_map: Dict[str, str],
        players: Dict[str, Dict],
        input_path: str
        ) -> List[Dict]:
    """
    Extract the four individual player records from a raw match dict.
    Resolves each player's scraped name to a canonical ID via the id_map,
    prompting for manual resolution via poup if any name is unknown.

    Parameters:
    -----------
    match: Dict
        raw match dict (before parsing)
    id_map: Dict[str, str]
        dict mapping player name to canonical id, updates in place
    players: Dict[str, Dict]
        dict mapping players to player record dicts, updated in place
    input_path: str
        path to input files
    
    Returns:
    --------
    List[Dict]:
        list of up to 4 player dicts with id and name
    """
    extracted = []
    for team_key in [DataKeys.Match.TEAM_1, DataKeys.Match.TEAM_2]:
        for player_key in [DataKeys.Team.PLAYER_1, DataKeys.Team.PLAYER_2]:
            raw_player = match[team_key][player_key]
            scraped_name = raw_player[DataKeys.Player.NAME]

            canonical_id = resolve_player(
                scraped_name=scraped_name,
                id_map=id_map,
                players=players,
                input_path=input_path
            )

            extracted.append({
                DataKeys.Player.ID: canonical_id,
                DataKeys.Player.NAME: players[canonical_id][DataKeys.Player.NAME]
            })

    return extracted


def deduplicate_players(all_players: List[Dict]) -> List[Dict]:
    """
    Deduplicate a flat list of player dicts by player id.
    Since player ids are scraped directly, id is the source of truth, no name normalization needed.

    Parameters:
    -----------
    all_players: List[Dict]
        flat list of player dicts including duplicates
    
    Returns:
    --------
    List[Dict]:
        list of unique player dicts, one per player id
    """
    seen = {}
    for player in all_players:
        canonical_id = player[DataKeys.Player.ID]
        if canonical_id not in seen:
            seen[canonical_id] = player
    return list(seen.values())

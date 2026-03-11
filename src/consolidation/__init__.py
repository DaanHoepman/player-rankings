# src/consolidation/__init__.py

from consolidation.deduplicator import (
    extract_players_from_match,
    deduplicate_players,
    extract_teams_from_match,
)

from consolidation.id_resolver import (
    load_id_map,
    save_id_map,
    load_players,
    save_players,
    resolve_player,
)

from consolidation.parsers import(
    parse_tournament_metadata,
    load_tournament_metadata,
    parse_match,
)

__all__ = [
    # deduplicator
    "extract_players_from_match",
    "deduplicate_players",
    "extract_teams_from_match",
    # id_resolver
    "load_id_map",
    "save_id_map",
    "load_players",
    "save_players",
    "resolve_player",
    # parsers
    "parse_tournament_metadata",
    "load_tournament_metadata",
    "parse_match",
]

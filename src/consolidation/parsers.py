# src/consolidation/parsers.py

import json

from typing import Dict, List
from pathlib import Path
from datetime import date, time

from constants import DataKeys, FileNames

# ── Parse Tournament ──────────────────────────────────────────────────

def parse_tournament_metadata(tournament_id: str, metadata: Dict) -> Dict:
    """
    Parse a raw metadata.json dict into a clean tournament record.
    Adds the tournament_id since it is not present in the metadata file
    itself.

    Parameters
    ----------
    tournament_id : str
        Folder name used as the tournament's unique identifier.
    metadata : Dict
        Raw dict loaded from metadata.json. This dict should at least
        contain the following keys: 'tournament_name', 'start_date', 
        'end_date', 'num_categories', 'num_registrations', 'scraped_at'.

    Returns
    -------
    Dict
        Clean tournament dict conforming to DataKeys.Tournament.
    """
    return {
        DataKeys.Tournament.ID:                tournament_id,
        DataKeys.Tournament.NAME:              metadata["tournament_name"],
        DataKeys.Tournament.START_DATE:        metadata["start_date"],
        DataKeys.Tournament.END_DATE:          metadata["end_date"],
        DataKeys.Tournament.CATEGORIES:        metadata["num_categories"],
        DataKeys.Tournament.REGISTRATIONS:     metadata["num_registrations"],
        DataKeys.General.SCRAPED_AT:           metadata["scraped_at"] 
    }


def load_tournament_metadata(tournament_path: Path) -> Dict:
    """
    Load and parse metadata.json from a tournament folder.
    
    Parameters
    ----------
    tournament_path : Path
        Path to the tournament folder containing metadata.json.
        
    Returns
    -------
    Dict
        Clean tournament dict conforming to DataKeys.Tournament.

    Raises
    ------
    FileNotFoundError
        If the metadata can not be found in the tournament folder.
    """
    metadata_path = tournament_path / FileNames.Raw.METADATA
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Missing {FileNames.Raw.METADATA} in {tournament_path}.",
            "Cannot parse tournament metadata.",
        )
    with open(metadata_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return parse_tournament_metadata(tournament_path.name, raw)

# ── Parse Match ───────────────────────────────────────────────────────

def _parse_match_datetime(
    date_str: str,
    time_str: str,
) -> tuple[str | None, str | None]:
    """
    Parse and validate raw date and time strings from a match record.
    Returns them as clean ISO-format strings, or None if parsing fails.
    
    Parameters
    ----------
    date_str : str
        raw date string (e.g. '2026-01-23').
    time_str : str
        raw time string (e.g. '14:30:00').
    
    Returns
    -------
    tuple[str | None, str | None]
        tuple of (date_iso_str, time_iso_str), where each is either a
        clean ISO-format string or None if parsing failed.
    """
    parsed_date = None
    parsed_time = None

    try:
        parsed_date = date.fromisoformat(date_str).isoformat()
    except (ValueError, TypeError):
        pass

    try:
        parsed_time = time.fromisoformat(time_str).isoformat()
    except (ValueError, TypeError):
        pass

    return parsed_date, parsed_time


def parse_match(
    match: Dict,
    tournament_id: str,
    team_1_id: str,
    team_2_id: str,
) -> Dict:
    """
    Parse a single raw match dict into a clean structured match record.

    Teams are referenced by canonical team ID rather than nested
    sub-dicts. Scores are lifted to the top level as team_1_score and
    team_2_score. Team IDs are resolved by run_consolidation.py before
    parse_match is called.

    Parameters
    ----------
    match : Dict
        Raw match dict from a poule json file. Each match should at
        least contain the following keys: 'match_id', 'category', 
        'poule', 'info', 'scraped_at', and two nested dictionaries 
        called 'team_1' and 'team_2', with both having a 'score' key.
    tournament_id : str
        ID of the tournament this match belongs to.
    team_1_id, team_2_id : str
        Canonical team ID, resolved by run_consolidation.py

    Returns
    -------
    Dict
        Flat match dict conforming to DataKeys.Match   
    """
    parsed_date, parsed_time = _parse_match_datetime(
        match.get("date", ""),
        match.get("time", "")
        )
    
    return {
        DataKeys.Match.ID:           match["match_id"],
        DataKeys.Match.TOURNAMENT:   tournament_id,
        DataKeys.Match.CATEGORY:     match["category"],
        DataKeys.Match.POULE:        match["poule"],
        DataKeys.Match.DATE:         parsed_date,
        DataKeys.Match.TIME:         parsed_time,
        DataKeys.Match.INFO:         match["info"],
        DataKeys.Match.TEAM_1_ID:    team_1_id,
        DataKeys.Match.TEAM_2_ID:    team_2_id,
        DataKeys.Match.TEAM_1_SCORE: match["team_1"]["score"],
        DataKeys.Match.TEAM_2_SCORE: match["team_2"]["score"],
        DataKeys.General.SCRAPED_AT: match["scraped_at"],
    }

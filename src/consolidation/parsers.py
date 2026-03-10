# src/consolidation/parsers.py

import json

from typing import Dict, List
from pathlib import Path
from datetime import date, time

from constants import DataKeys, FileNames

#-------------------------------------------------------------------------

def parse_tournament_metadata(tournament_id: str, metadata: Dict) -> Dict:
    """
    Parse a raw metadata.json dict into a clean tournament record.
    Adds the tournament_id since it is not present in the metadata file itself.

    Parameters:
    -----------
    tournament_id: str
        folder name used as the tournament's unique identifier
    metadata: Dict:
        raw dict loaded from metadata.json

    Returns:
    --------
    Dict:
        clean tournament dict conforming to DataKeys.Tournament
    """
    return {
        DataKeys.Tournament.ID: tournament_id,
        DataKeys.Tournament.NAME: metadata[DataKeys.Tournament.NAME],
        DataKeys.Tournament.START_DATE: metadata[DataKeys.Tournament.START_DATE],
        DataKeys.Tournament.END_DATE: metadata[DataKeys.Tournament.END_DATE],
        DataKeys.Tournament.NUM_CATEGORIES: metadata[DataKeys.Tournament.NUM_CATEGORIES],
        DataKeys.Tournament.NUM_REGISTRATIONS: metadata[DataKeys.Tournament.NUM_REGISTRATIONS],
        DataKeys.General.SCRAPED_AT: metadata[DataKeys.General.SCRAPED_AT] 
    }


def load_tournament_metadata(tournament_path: Path) -> Dict:
    """
    Load and parse metadata.json from a tournament folder.
    
    Parameters:
    -----------
    tournament_path: Path
        path to the tournament folder containing metadata.json
        
    Returns:
    --------
    Dict:
        clean tournament dict conforming to DataKeys.Tournament
    """
    metadata_path = tournament_path / FileNames.Raw.METADATA
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing {FileNames.Raw.METADATA} in {tournament_path}. Cannot parse tournament metadata.")
    with open(metadata_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return parse_tournament_metadata(tournament_path.name, raw)

#-------------------------------------------------------------------------

def parse_match_datetime(date_str: str, time_str: str) -> tuple[str | None, str | None]:
    """
    Parse and validate raw date and time strings from a match record.
    Returns them as clean ISO-format strings, or None if parsing fails.
    
    Parameters:
    -----------
    date_str: str
        raw date string (e.g. '2026-01-23')
    time_str: str
        raw time string (e.g. '14:30:00')
    
    Returns:
    --------
    tuple[str | None, str | None]:
        tuple of (date_iso_str, time_iso_str) where each is either a clean ISO-format string or None if parsing failed
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


def parse_match(match: Dict, tournament_id: str) -> Dict:
    """
    Parse a single raw match dict into a clean structured match record.

    Parameters:
    -----------
    match: Dict
        raw match dict from a poule json file
    tournament_id: str
        id of the tournament this match belongs to

    Returns:
    --------
    Dict:
        clean match dict conforming to DataKeys.Match   
    """
    parsed_date, parsed_time = parse_match_datetime(
        match.get(DataKeys.Match.DATE, ""),
        match.get(DataKeys.Match.TIME, "")
        )
    
    return {
        DataKeys.Match.ID: match[DataKeys.Match.ID],
        DataKeys.Tournament.ID: tournament_id,
        DataKeys.Match.CATEGORY: match[DataKeys.Match.CATEGORY],
        DataKeys.Match.POULE: match[DataKeys.Match.POULE],
        DataKeys.Match.DATE: parsed_date,
        DataKeys.Match.TIME: parsed_time,
        DataKeys.Match.INFO: match[DataKeys.Match.INFO],
        DataKeys.General.SCRAPED_AT: match[DataKeys.General.SCRAPED_AT],
        DataKeys.Match.TEAM_1: {
            DataKeys.Team.PLAYER_1: match[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_1],
            DataKeys.Team.PLAYER_2: match[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_2],
            DataKeys.Team.SCORE: match[DataKeys.Match.TEAM_1][DataKeys.Team.SCORE],
        },
        DataKeys.Match.TEAM_2: {
            DataKeys.Team.PLAYER_1: match[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_1],
            DataKeys.Team.PLAYER_2: match[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_2],
            DataKeys.Team.SCORE: match[DataKeys.Match.TEAM_2][DataKeys.Team.SCORE],
        }
    }


def parse_poule_file(path: Path, tournament_id: str) -> List[Dict]:
    """
    Load and parse all matches from a single poule json file.

    Parameters:
    -----------
    path: Path
        path to the poule json file
    tournament_id: str
        id of the tournament this poule belongs to
    
    Returns:
    --------
    List[Dict]:
        list of clean match dicts
    """
    with open(path, encoding="utf-8") as f:
        raw_matches = json.load(f)

    return [
        parse_match(match, tournament_id)
        for match in raw_matches
    ]

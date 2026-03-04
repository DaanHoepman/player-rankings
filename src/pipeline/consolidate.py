# src/pipeline/consolidate.py

import json

from pathlib import Path
from typing import List, Dict, Tuple

from pipeline._parsers import load_tournament_metadata, parse_match
from pipeline._deduplicator import extract_players_from_match, deduplicate_players
from pipeline._id_resolver import load_id_map, load_players, save_id_map, save_players
from constants import DataKeys, FileNames

#------------------------------------------------------------

def _write_output(data: List[Dict], filename: str, output_path: Path) -> None:
    """
    Write a list of dicts to a json file in the output folder.
    Creates the output folder if it does not exist.

    Parameters:
    -----------
    data: List[Dict]
        List of dicts to serialize
    filename: str
        output filename e.g. 'matches.json'
    output_path:
        folder to write into
    """
    output_path.mkdir(parents=True, exist_ok=True)
    with open(output_path / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\tWrote {len(data)} records to {output_path / filename}")

#------------------------------------------------------------

def _walk_tournament(
        tournament_path: Path, 
        id_map: Dict[str, str], 
        players: Dict[str, Dict], 
        input_path: str
        ) -> Tuple[Dict, List[Dict], List[Dict]]:
    """
    Process a single tournament folder.
    Read metadata.json and all poule json files within all category subfolders.
    Resolved player names to canonical IDs during match processing.

    Parameters:
    -----------
    tournament_path: Path
        path to a single tournament folder (named by tournament_id)
    id_map: Dict[str, str]
        dict mapping player name to ID
    players: Dict[str, Dict]
        dict mapping player ID to player records
    input_path: str
        path to input file directory

    Returns:
    --------
    Tuple[Dict, List[Dict], List[Dict]]:
        tuple of (tournament_record, list of flat matches, list of raw player dicts)
    """
    tournament_id = tournament_path.name
    print(f"\n> Processing tournament: {tournament_id}")

    # Load tournament metadata
    tournament = load_tournament_metadata(tournament_path)

    all_matches: List[Dict] = []
    all_players: List[Dict] = []

    # Walk every category subfolder
    for category_path in sorted(tournament_path.iterdir()):
        if not category_path.is_dir():
            continue # skip metadata.json and other root-level files

        print(f"\tCategory: {category_path.name}")

        # Walk every poule json file within the category
        for poule_file in sorted(category_path.glob("*.json")):
            raw_matches = _load_raw_poule(poule_file)

            for raw_match in raw_matches:
                # Extract and resolve players, prompting for unknowns
                match_players = extract_players_from_match(
                    match=raw_match,
                    id_map=id_map,
                    players=players,
                    input_path=input_path
                )
                all_players.extend(match_players)

                # Build name to canonical ID lookup for this match's four players
                # match_players entries look like {"id": ..., "name": ...}
                name_to_canonical = {
                    p[DataKeys.Player.NAME]: p[DataKeys.Player.ID]
                    for p in match_players
                }

                # Parse match and subtitute player names for their canonical IDs
                parsed = parse_match(raw_match, tournament_id)
                parsed = _substitute_canonical_ids(parsed, raw_match, name_to_canonical)
                all_matches.append(parsed)

    return tournament, all_matches, all_players


def _load_raw_poule(path: Path) -> List[Dict]:
    """
    Load raw match dicts from a poule json file without parsing.
    Used so we can extract players before parsing the match.

    Parameters:
    -----------
    path: Path
        path to the poule json file

    Returns:
    --------
    List[Dict]:
        list of raw match dicts
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)
    

def _substitute_canonical_ids(
    parsed_match: Dict,
    raw_match: Dict,
    name_to_canonical: Dict[str, str]
) -> Dict:
    """
    Fill the player_1 and player_2 fields within each team in a parsed match dict
    with canonical IDs resolved from this match's player resolution results.

    Parameters:
    -----------
    parsed_match: Dict
        structured match dict from parse_match()
    raw_match: Dict
        original raw match dict (for name lookups)
    name_to_canonical: Dict[str, str]
        map of played names to IDs

    Returns:
    --------
    Dict:
        match dict with team player fields filled with canonical IDs
    """
    updated = parsed_match.copy()
    updated[DataKeys.Match.TEAM_1] = parsed_match[DataKeys.Match.TEAM_1].copy()
    updated[DataKeys.Match.TEAM_2] = parsed_match[DataKeys.Match.TEAM_2].copy()

    for team_key in [DataKeys.Match.TEAM_1, DataKeys.Match.TEAM_2]:
        for player_key in [DataKeys.Team.PLAYER_1, DataKeys.Team.PLAYER_2]:
            # raw_match stores a nested dict with id and name
            scraped = raw_match[team_key][player_key]
            # fall back to None if the expected sub-key is missing
            scraped_name = scraped.get(DataKeys.Player.NAME) if isinstance(scraped, dict) else None
            updated[team_key][player_key] = (
                name_to_canonical.get(scraped_name) if scraped_name is not None else None
            )

    return updated

#------------------------------------------------------------

def consolidate(raw_path: str, output_path: str, input_path: str) -> None:
    """
    Main consolidation entry point.
    Walks all tournament folders in raw_path, resolves player identities,
    and writes three flat output files to output_path:
        - tournaments.json
        - matches.json
        - players.json

    Player id_map and players registry are loaded once, updated throughout,
    and saved at the end, Immediate saves also occur on each new resolution
    so progress is never lost if consolidation is interrupted.

    Parameters:
    -----------
    raw_path: str
        path to raw data directory (contains tournament id folders)
    output_path: str
        path to output data directory (output destination)
    input_path: str
        path to input data directory (player_id_map.json and players.json)
    """

    raw = Path(raw_path)
    out = Path(output_path)

    if not raw.exists():
        raise FileNotFoundError(f"Raw data path does not exist: {raw}")
    
    print("Loading player registry...")
    id_map = load_id_map(input_path)
    players = load_players(input_path)
    print(f"\t{len(players)} known players, {len(id_map)} name mappings loaded.")

    all_tournaments: List[Dict] = []
    all_matches: List[Dict] = []
    all_players: List[Dict] = []

    tournament_folders = [p for p in sorted(raw.iterdir()) if p.is_dir()]
    print(f"\nFound {len(tournament_folders)} tournament{'' if len(tournament_folders) == 1 else 's'} to process.")

    for tournament_path in tournament_folders:
        try:
            tournament, matches, raw_players = _walk_tournament(
                tournament_path=tournament_path,
                id_map=id_map,
                players=players,
                input_path=input_path
            )
            all_tournaments.append(tournament)
            all_matches.extend(matches)
            all_players.extend(raw_players)
        except FileNotFoundError as e:
            print(f"\tSkipping {tournament_path.name}: {e}")
            continue

    # Deduplicate players across all tournaments
    unique_players = deduplicate_players(all_players)

    # save final state of id_map and players registry
    save_id_map(id_map, input_path)
    save_players(players, input_path)

    # Write flat output files
    print("\nWriting output files...")
    _write_output(all_tournaments, FileNames.Flat.TOURNAMENTS, out)
    _write_output(all_matches, FileNames.Flat.MATCHES, out)
    _write_output(unique_players, FileNames.Flat.PLAYERS, out)

    print("\nConsolidation complete.")
    print(f"\t{len(all_tournaments)} tournaments")
    print(f"\t{len(all_matches)} matches")
    print(f"\t{len(unique_players)} unique players")
    

#------------------------------------------------------------

if __name__ == "__main__":
    from settings import load_config

    config = load_config()

    try:
        raw_path = config["paths"]["raw_data"]
    except:
        raise 
    try:
        output_path = config["paths"]["consolidated_data"]
    except:
        raise
    try:
        input_path = config["paths"]["input_data"]
    except:
        raise

    consolidate(
        raw_path=raw_path,
        output_path=output_path,
        input_path=input_path
    )

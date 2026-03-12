# src/pipeline/run_consolidation.py

# ── Standard Library Imports ──────────────────────────────────────────

import json

from pathlib import Path
from typing import List, Dict, Tuple

# ── Local Library Imports ─────────────────────────────────────────────

from consolidation.parsers import load_tournament_metadata, parse_match
from consolidation.deduplicator import (
    extract_players_from_match,
    deduplicate_players,
    extract_teams_from_match,
)
from consolidation.id_resolver import (
    load_id_map, load_players, save_id_map, save_players
)
from constants import DataKeys, FileNames

# ── File Handling ─────────────────────────────────────────────────────

def _write_output(data: List[Dict], filename: str, output_path: Path) -> None:
    """
    Write a list of dicts to a json file in the output folder.
    Creates the output folder if it does not exist.

    Parameters
    ----------
    data : List[Dict]
        List of dicts to serialize.
    filename : str
        Output filename e.g. 'matches.json'.
    output_path : Path
        Folder to write into.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    with open(output_path / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\tWrote {len(data)} records to {output_path / filename}")


def _load_raw_poule(path: Path) -> List[Dict]:
    """
    Load raw match dicts from a poule json file without parsing.
    Used so we can extract players before parsing the match.

    Parameters
    ----------
    path : Path
        Path to the poule json file

    Returns
    -------
    List[Dict]
        List of raw match dicts
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ── Implementation ────────────────────────────────────────────────────

def _walk_tournament(
        tournament_path: Path, 
        id_map: Dict[str, str], 
        players: Dict[str, Dict],
        teams: Dict[str, Dict],
        input_path: str
        ) -> Tuple[Dict, List[Dict], List[Dict]]:
    """
    Process a single tournament folder. Read metadata.json and all poule
    json files within all category subfolders. Resolved player names to 
    canonical IDs during match processing.

    Parameters
    ----------
    tournament_path : Path
        Path to a single tournament folder (named by tournament_id).
    id_map : Dict[str, str]
        Dict mapping player name to ID.
    players : Dict[str, Dict]
        Dict mapping player ID to player records.
    teams : Dict[str, Dict]
        Dict mapping team ID to team records, updated in place.
    input_path : str
        Path to input file directory.

    Returns
    -------
    Tuple[Dict, List[Dict], List[Dict]]
        Tuple of (tournament_record, list of flat matches, list of raw
        player dicts).
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
                    match     =raw_match,
                    id_map    =id_map,
                    players   =players,
                    input_path=input_path
                )
                all_players.extend(match_players)

                # Derive team IDs from resolved players, 
                # registering new teams in place
                team_1_id, team_2_id = extract_teams_from_match(
                    match_players=match_players,
                    teams        =teams,
                )

                # Parse match into flat structure with canonical team
                # IDs and top-level scores
                parsed = parse_match(
                    match        =raw_match,
                    tournament_id=tournament_id,
                    team_1_id    =team_1_id,
                    team_2_id    =team_2_id
                )
                all_matches.append(parsed)

    return tournament, all_matches, all_players

# ── Entry Point ───────────────────────────────────────────────────────

def consolidate(raw_path: str, output_path: str, input_path: str) -> None:
    """
    Main consolidation entry point.
    Walks all tournament folders in raw_path, resolves player 
    identities, derives team identities, and writes four flat output
    files to output_path:
    - tournaments.json
    - matches.json
    - players.json

    Player id_map and players registry are loaded once, updated 
    throughout, and saved at the end. Immediate saves also occur on each
    new resolution so progress is never lost if consolidation is 
    interrupted.

    Parameters
    ----------
    raw_path : str
        Path to raw data directory (contains tournament id folders).
    output_path : str
        Path to output data directory (output destination).
    input_path : str
        Path to input data directory (player_id_map.json and 
        players.json)
    """
    raw = Path(raw_path)
    out = Path(output_path)

    if not raw.exists():
        raise FileNotFoundError(f"Raw data path does not exist: {raw}")
    
    print("Loading player registry...")
    id_map  = load_id_map(input_path)
    players = load_players(input_path)
    print(
        f"\t{len(players)} known players, {len(id_map)} name mappings loaded."
    )

    all_tournaments: List[Dict] = []
    all_matches: List[Dict]     = []
    all_players: List[Dict]     = []
    all_teams: Dict[str, Dict]  = {}

    tournament_folders = [p for p in sorted(raw.iterdir()) if p.is_dir()]
    print(f"\nFound {len(tournament_folders)} tournament",
          f"{'' if len(tournament_folders) == 1 else 's'} to process.")

    for tournament_path in tournament_folders:
        try:
            tournament, matches, raw_players = _walk_tournament(
                tournament_path=tournament_path,
                id_map         =id_map,
                players        =players,
                teams          =all_teams,
                input_path     =input_path
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
    _write_output(all_tournaments, FileNames.Output.TOURNAMENTS, out)
    _write_output(all_matches, FileNames.Output.MATCHES, out)
    _write_output(unique_players, FileNames.Output.PLAYERS, out)
    _write_output(list(all_teams.values()), FileNames.Output.TEAMS, out)

    print("\nConsolidation complete.")
    print(f"\t{len(all_tournaments)} tournaments")
    print(f"\t{len(all_matches)} matches")
    print(f"\t{len(unique_players)} unique players")
    print(f"\t{len(all_teams)} unique teams")
    

#------------------------------------------------------------

if __name__ == "__main__":
    from settings import load_config

    config = load_config()

    try:
        raw_path = config["paths"]["raw_data"]
    except:
        raise ValueError(
            "No raw data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.raw_data."
        )
    try:
        output_path = config["paths"]["consolidated_data"]
    except:
        raise ValueError(
            "No output data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.consolidated_data."
        )
    try:
        input_path = config["paths"]["input_data"]
    except:
        raise ValueError(
            "No input data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.input_data."
        )

    consolidate(
        raw_path   =raw_path,
        output_path=output_path,
        input_path =input_path
    )

# src/pipeline/run_features.py

# ── Standard Library Imports ──────────────────────────────────────────

import json

from pathlib import Path
from typing import Dict, List, Tuple

# ── Local Library Imports ─────────────────────────────────────────────

from features import (
    enrich_matches, 
    enrich_teams, 
    enrich_players, 
    enrich_tournaments,
)
from settings import load_config
from constants import FileNames

# ── I/O ───────────────────────────────────────────────────────────────

def _load(path: Path) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
    

def _write(data: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    count = len(data)
    print(f"\t~ {path.name} ({count} records)")

# ── Entry point ───────────────────────────────────────────────────────

def run_features() -> None:
    """
    Feature enrichment pipeline entry point.

    Reads consolidated data, applies all feature functions per entity,
    and writes enriched output to data/processed/.

    Enrichment order is fixed and must be respected; later steps
    depend on fields produced by earlier ones.
    """
    config = load_config()
    try:
        consolidated_path = Path(config["paths"]["consolidated_data"])
    except:
        raise ValueError(
            "No consolidated data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.consolidated_data."
        )
    try:
        processed_path = Path(config["paths"]["processed_data"])
    except:
        raise ValueError(
            "No processed data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.processed_data."
        )
    
    print("\n── Feature enrichment ────────────────────────────────────────")
    print(f"\tSource : {consolidated_path}")
    print(f"\tOutput : {processed_path}\n")

    # Load consolidated data
    matches     = _load(consolidated_path / FileNames.Output.MATCHES)
    tournaments = _load(consolidated_path / FileNames.Output.TOURNAMENTS)
    players     = _load(consolidated_path / FileNames.Output.PLAYERS)
    teams       = _load(consolidated_path / FileNames.Output.TEAMS)

    print(
        f"Loaded {len(matches)} matches, {len(tournaments)} tournaments, "
        f"{len(players)} players, {len(teams)} teams\n"
    )
    print("Enriching...")

    # 1. Matches; must run first, others depend on its output
    matches = enrich_matches(matches)

    # 2. Teams; standalone entity enriched from match history
    teams = enrich_teams(teams, matches=matches)

    # 3. Tournaments; depends on enriched matches and teams
    tournaments = enrich_tournaments(tournaments, matches=matches, teams=teams)

    # 4. Players; depends on enriched matches and teams
    players = enrich_players(players, matches=matches, teams=teams)

    # Write processed output
    print("\nWriting processed data...")
    _write(matches,     processed_path / FileNames.Output.MATCHES)
    _write(teams,       processed_path / FileNames.Output.TEAMS)
    _write(tournaments, processed_path / FileNames.Output.TOURNAMENTS)
    _write(players,     processed_path / FileNames.Output.PLAYERS)

    print("\n~ Feature enrichment complete.")


if __name__ == "__main__":
    run_features()

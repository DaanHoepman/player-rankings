# src/pipeline/run_models.py

import json
import argparse

from pathlib import Path
from typing import Type, Dict, List, Tuple

from models import BaseModel
from models.knltb import KnltbModel
from models.trueskill import TrueSkillModel
from settings import load_config
from constants import FileNames, DataKeys


# ── Model registry ────────────────────────────────────────────────────

MODELS: Dict[str, Type[BaseModel]] = {
    "knltb":     KnltbModel,
    "trueskill": TrueSkillModel,
}

# ── Loaders ───────────────────────────────────────────────────────────

def _load_json(path: Path) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_processed(
    processed_path: str,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Load matches, players, and teams from the processed data folder.

    Parameters
    ----------
    processed_path : str
        Path to the processed data folder.

    Returns
    -------
    Tuple[List[Dict], List[Dict], List[Dict]]
        (matches, players, teams)
    """
    base = Path(processed_path)
    return (
        _load_json(base / FileNames.Output.MATCHES),
        _load_json(base / FileNames.Output.PLAYERS),
        _load_json(base / FileNames.Output.TEAMS),
    )

# ── Splitting ─────────────────────────────────────────────────────────

def _split_matches(
    matches: List[Dict],
    tournaments: List[str] | None,
) -> Dict[str, List[Dict]]:
    """
    Split matches into groups for model runs.
    If tournaments is None or empty, all valid matches are grouped under
    a single 'all' key. Otherwise matches are grouped per tournament ID,
    keeping ratings fully isolated within each tournament.

    Only played and valid matches are included; filtering on is_played
    and is_valid here is a safety net; run() also enforces this.

    Parameters
    ----------
    matches : List[Dict]
        All match records from processed/matches.json.
    tournaments : List[str] | None
        Tournament IDs to split on, or None to run all combined.

    Returns
    -------
    Dict[str, List[Dict]]
        Mapping of tournamend_id (or 'all') to a list of matches
    """
    valid = [
        m for m in matches
        if m.get(DataKeys.Match.IS_PLAYED) 
        and m.get(DataKeys.Match.IS_VALID)
    ]

    if not tournaments:
        return {"all": valid}

    groups: Dict[str, List[Dict]] = {}
    for match in matches:
        tournament_id: str = match.get(DataKeys.Match.TOURNAMENT, "unknown")
        if tournament_id in tournaments:
            groups.setdefault(tournament_id, []).append(match)
    return groups


def _get_pending(
    matches: List[Dict],
    tournament_id: str | None,
) -> List[Dict]:
    """
    Return pending matches for prediction, optionally filtered by
    tournament. When running per-tournament, only pending matches from
    the same tournament are relevant for predictions.

    Parameters
    ----------
    matches : List[Dict]
        All match records from processed/matches.json.
    tournament_id : str | None
        Tournament to filter on, or None to return all pending matches.

    Returns
    -------
    List[Dict]
        Pending match records.
    """
    pending = [
        m for m in matches
        if not m.get(DataKeys.Match.IS_PLAYED)
    ]
    if tournament_id:
        pending = [
            m for m in pending
            if m.get(DataKeys.Match.TOURNAMENT) == tournament_id
        ]
    return pending

# ── Output ────────────────────────────────────────────────────────────

def _write_output(
    model: BaseModel,
    model_name: str,
    group_label: str,
    pending_matches: List[Dict],
    teams: List[Dict],
    output_path: str,
    fmt: str = "csv",
) -> None:
    """
    Write ratings, history, and predictions to the output folder.

    File layout:
        {output_path}/{model_name}_ratings.{fmt}
        {output_path}/{model_name}_history.{fmt}
        {output_path}/{model_name}_predictions.{fmt}

    For per-category runs, group label is inserted:
        {output_path}/{model_name}_{group_label}_ratings.{fmt}

    Parameters
    ----------
    model : BaseModel
        Fitted model instance.
    model_name : str
        Model identifier string (e.g. 'knltb', 'trueskill').
    group_label : str
        Group label: 'all' for combined runs, tournament_id otherwise.
    pending_matches : List[Dict]
        Upcoming matches to predict on.
    teams : List[Dict]
        Team registry, passed to predict_batch for player ID resolution.
    output_path : str
        Output folder path.
    fmt : str
        Output format: 'csv' or 'json'. Default is 'csv'.
    """
    suffix = "" if group_label == "all" else f"_{group_label}"
    base   = Path(output_path) / f"{model_name}{suffix}"
    base.parent.mkdir(parents=True, exist_ok=True)

    # Ratings
    model.save(str(base) + "_ratings", fmt=fmt)
    print(f"\t✔ Ratings      → {base}_ratings.{fmt}")

    # History
    history_df = model.history()
    if not history_df.empty:
        hist_path = base.parent / f"{base.name}_history"
        if fmt == "csv":
            history_df.to_csv(str(hist_path) + ".csv", index=False)
        else:
            history_df.to_json(
                str(hist_path) + ".json", orient="records", indent=2
            )
        print(f"\t✔ History      → {hist_path}.{fmt}")

    # Predictions on pending matches
    if pending_matches:
        predictions_df = model.predict_batch(pending_matches, teams)
        pred_path      = base.parent / f"{base.name}_predictions"
        if fmt == "csv":
            predictions_df.to_csv(str(pred_path) + ".csv", index=False)
        else:
            predictions_df.to_json(
                str(pred_path) + ".json", orient="records", indent=2
            )
        print(
            f"\t✔ Predictions  → {pred_path}.{fmt}",
            f"({len(pending_matches)} matches)",
        )
    else:
        print(f"\tℹ No pending matches found for predictions.")


# ── Entry point ───────────────────────────────────────────────────────

def run_model(model_name: str) -> None:
    """
    Full model pipeline entry point.
    Loads processed data, builds the model, runs it over valid matches
    in chronological order, and writes ratings, history, and 
    predictions.

    Reads processed/; features must have been run first so that
    'is_played', 'is_valid', and 'winner' are present.

    Behaviour is driven by config.yaml:
    - models.tournaments   : list of tournament IDs to isolate, 
                             or null for combined
    - models.output_format : 'csv' or 'json'
    - paths.processed_data : source data folder
    - paths.output_data    : output folder

    Parameters
    ----------
    model_name : str
        Model key, must be registered in MODELS
    """
    if model_name not in MODELS:
        raise ValueError(
            f"Unknown model '{model_name}'. "
            f"Available: {list(MODELS.keys())}"
        )

    config = load_config()
    try:
        processed_path = config["paths"]["processed_data"]
    except:
        raise ValueError(
            "No processed data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.processed_data."
        )
    try:
        output_path = config["paths"]["output_data"]
    except:
        raise ValueError(
            "No output data path configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under paths.output_data."
        )
    try:
        fmt = config["models"]["output_format"]
    except:
        raise ValueError(
            "No model output format configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under models.output_format."
        )
    try:
        trnmnts = config["models"]["tournaments"]
    except:
        raise ValueError(
            "No model tournaments configured.",
            "Add it to config/local.yaml or config/default.yaml",
            "under models.tournaments."
        )

    print(f"\n── Running model: {model_name} ─────────────────────────")
    print(f"\tProcessed   : {processed_path}")
    print(f"\tOutput      : {output_path}")
    print(f"\tFormat      : {fmt}")
    print(f"\tTournaments : {'all combined' if not trnmnts else trnmnts}\n")

    all_matches, players, teams = _load_processed(processed_path)
    model_class                 = MODELS[model_name]
    groups                      = _split_matches(all_matches, trnmnts)

    for group_label, group_matches in groups.items():
        print(f"→ Group: {group_label} ({len(group_matches)} valid matches)")

        if not group_matches:
            print(f"\t⚠ No completed matches — skipping.\n")
            continue

        model = model_class(players=players)
        model.run(group_matches, teams)

        pending = _get_pending(
            all_matches,
            tournament_id=None if group_label == "all" else group_label,
        )

        _write_output(
            model          =model,
            model_name     =model_name,
            group_label    =group_label,
            pending_matches=pending,
            teams          =teams,
            output_path    =output_path,
            fmt            =fmt,
        )
        print()

    print(f"✔ {model_name} complete.\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a ranking model over processed padel match data."
    )
    parser.add_argument(
        "model",
        choices=list(MODELS.keys()),
        help="Model to run."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_model(args.model)

# src/features/matches.py

# ── Standard Library Imports ──────────────────────────────────────────

from typing import Dict, List, Tuple

# ── Local Library Imports ─────────────────────────────────────────────

from features._base import apply_features, FeatureFn
from constants import DataKeys, DefaultValues

# ── Feature functions ─────────────────────────────────────────────────

def __get_scores(record: Dict) -> Tuple[int | None, int | None]:
    """
    Extracts the scores of both teams from a match record.

    Parameters
    ----------
    record:
        A match record dict containing 'team_1_score' and 'team_2_score'
        keys (or DataKeys equivalent).

    Returns
    -------
    Tuple[int | None, int | None]
        Tuple of scores (team_1_score, team_2_score) as integers or None
        when not present in the record.
    """
    t1_score = record.get(DataKeys.Match.TEAM_1_SCORE)
    t2_score = record.get(DataKeys.Match.TEAM_2_SCORE)

    return (t1_score, t2_score)


def _status(record: Dict, **_) -> Dict:
    """
    Derive match status from score and existing status field.
    A match is 'completed' if both scores are present and non-null,
    'pending' if scores are absent or null, and 'unknown otherwise.
    """
    t1_score, t2_score = __get_scores(record)

    if t1_score is not None and t2_score is not None:
        status    = DefaultValues.Match.Status.COMPLETED
        is_played = True
    elif t1_score is None and t2_score is None:
        status    = DefaultValues.Match.Status.COMPLETED
        is_played = False
    else:
        status    = DefaultValues.Entries.UNKNOWN
        is_played = None
    
    return {
        DataKeys.Match.STATUS:    status,
        DataKeys.Match.IS_PLAYED: is_played,
    }


def _winner(record: Dict, **_) -> Dict:
    """
    Derive the winning team from scores including the winners score and
    that of the losing team.
    Returns 1, 2, or 0 (draw). None if match is not completed.
    """
    t1_score, t2_score = __get_scores(record)

    if t1_score is None or t2_score is None:
        winner_team  = None
        winner_score = None
        loser_score  = None
    elif t1_score > t2_score:
        winner_team  = 1
        winner_score = t1_score
        loser_score  = t2_score
    elif t2_score > t1_score:
        winner_team  = 2
        winner_score = t2_score
        loser_score  = t1_score
    else:
        winner_team  = 0
        winner_score = t1_score
        loser_score  = t1_score
    
    return {
        DataKeys.Match.WINNER:       winner_team,
        DataKeys.Match.WINNER_SCORE: winner_score,
        DataKeys.Match.LOSER_SCORE:  loser_score,
    }


def _score_difference(record: Dict, **_) -> Dict:
    """
    Compute the absolute score difference between the two teams.
    None if match is not completed.
    """
    t1_score, t2_score = __get_scores(record)

    if t1_score is None or t2_score is None:
        return {DataKeys.Match.SCORE_DIFF: None}
    return {DataKeys.Match.SCORE_DIFF: abs(t1_score - t2_score)}


def _total_games(record: Dict, **_) -> Dict:
    """
    Compute the total number of games played in the match.
    None if match is not completed.
    """
    t1_score, t2_score = __get_scores(record)

    if t1_score is None or t2_score is None:
        return {DataKeys.Match.TOTAL_GAMES: None}
    return {DataKeys.Match.TOTAL_GAMES: t1_score + t2_score}


def _read_info(record: Dict, **_) -> Dict:
    """
    Derive match labels based on the recorded info.
    The field is_valid is used to determine which matches to include in
    model rating calculations.
    """
    info = record.get(DataKeys.Match.INFO)

    if info in DefaultValues.Match.WALKOVER_VALUES:
        is_walkover = True
        is_valid    = False
    elif info == DefaultValues.Match.Info.CANCELED:
        is_walkover = False
        is_valid    = False
    else:
        is_walkover = False
        is_valid    = True
    
    return {
        DataKeys.Match.IS_WALKOVER: is_walkover,
        DataKeys.Match.IS_VALID:    is_valid,
    }

# ── Registry ──────────────────────────────────────────────────────────
# Ordered list of feature functions applied to every match record.
# Add new feature functions above and register them here.

MATCH_FEATURES: List[FeatureFn] = [
    _status,
    _winner,
    _score_difference,
    _total_games,
    _read_info,
]

# ── Entry Point ───────────────────────────────────────────────────────

def enrich_matches(
    matches: List[Dict],
    **context,
) -> List[Dict]:
    """
    Enrich all match records with derived features.
    Context kwargs (players, tournaments) are passed through to feature
    functions that need cross-entity data.

    Parameters
    ----------
    matches : List[Dict]
        Raw match records from consolidated/matches.json.
    **context
        Optional cross-entity data (e.g. players=players_dict).

    Returns
    -------
    List[Dict]
        Enriched match records with additional derived fields.
    """
    return apply_features(matches, MATCH_FEATURES, **context)

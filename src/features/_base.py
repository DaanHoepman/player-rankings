# src/features/_base.py

# ── Standard Library Imports ──────────────────────────────────────────

from typing import Callable, List, Dict

# ── Type Specification ────────────────────────────────────────────────

# Type alias for a feature function.
# Each feature function takes a record dict and the full context dicts,
# and returns a dict of new fields to merge into the record.
FeatureFn = Callable[..., Dict]

# ── Main Method ───────────────────────────────────────────────────────

def apply_features(
    records: List[Dict],
    feature_fns: List[FeatureFn],
    **context,
) -> List[Dict]:
    """
    Apply a list of feature functions to a list of records.
    Each feature function receives the current record and any context
    passed as keyword arguments (e.g. matches=..., players=...).
    The returned dict is merged into the record.

    New features are added as new keysl existing keys are never 
    overwritten. This makes it safe to add new feature functions without
    risking interference with existing fields.

    Parameters
    ----------
    records : List[Dict]
        List of entity dicts to enrich (matches, players, tournaments).
    feature_fns : List[FeatureFn]
        Ordered list of feature functions to apply. Each function
        signature must be: (record: Dict, **context) -> Dict
    **context
        Shared data passed to every feature function.
        Typically: matches, players, tournaments as full List[Dict].

    Returns
    -------
    List[Dict]
        New list of enriched records. Input records are not mutated.
    """
    enriched: List[Dict] = []
    for record in records:
        result = dict(record) # shallow copy; input is never mutated
        for fn in feature_fns:
            new_fields = fn(result, **context)
            # Merge new fields; never overwrite existing keys
            for key, value in new_fields.items():
                if key not in result:
                    result[key] = value
        enriched.append(result)
    return enriched

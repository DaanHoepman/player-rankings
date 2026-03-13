# src/models/_utils.py

from constants import DefaultValues

# ── Helpers ───────────────────────────────────────────────────────────

def knltb_to_trueskill_mu(
    knltb_rating: float,
    knltb_min: float = DefaultValues.Models.Conversion.KNLTB_MIN,
    knltb_max: float = DefaultValues.Models.Conversion.KNLTB_MAX,
    mu_min: float = DefaultValues.Models.Conversion.MU_MIN,
    mu_max: float = DefaultValues.Models.Conversion.MU_MAX,
) -> float:
    """
    Convert a KNLTB rating to a TrueSkill mu value.

    The KNLTB rating runs inverted (lower = stronger, 1 = professional,
    9 = beginner) with four decimal places. TrueSkill mu runs upwars
    (higher = stronger). This function inverts and linearly rescales the
    KNLTB rating onto the target mu range.

    Parameters
    ----------
    knltb_rating : float
        KNLTB rating value (e.g. 6.2341). Typically in [1.0, 9.0].
    knltb_min : float
        Lower bound of the KNLTB scale (strongest player). Default 1.0.
    knltb_max : float
        Upper bound of the KNLTB scale (weakest player). Default 9.0.
    mu_min : float
        TrueSkill mu assigned to the weakest player (knltb_max). 
        Default 10.0
    mu_max : float
        TrueSkill mu assigned to the strongest player (knltb_min). 
        Default 40.0.

    Returns
    -------
    float
        Mu value for use in TrueSkillModel.
    """
    knltb_rating    = max(knltb_min, min(knltb_max, knltb_rating))
    normalised      = (knltb_rating - knltb_min) / (knltb_max - knltb_min)
    return mu_max - normalised * (mu_max - mu_min)
    

def trueskill_mu_to_knltb(
    mu: float,
    knltb_min: float = DefaultValues.Models.Conversion.KNLTB_MIN,
    knltb_max: float = DefaultValues.Models.Conversion.KNLTB_MAX,
    mu_min: float = DefaultValues.Models.Conversion.MU_MIN,
    mu_max: float = DefaultValues.Models.Conversion.MU_MAX,
) -> float:
    """
    Reverse mapping from TrueSkill mu back to KNLTB rating scale.
    
    Parameters
    ----------
    mu : float
        Current TrueSkill mu value
    knltb_min : float
        Lower bound of the KNLTB scale (strongest player). Default 1.0.
    knltb_max : float
        Upper bound of the KNLTB scale (weakest player). Default 9.0.
    mu_min : float
        TrueSkill mu assigned to the weakest player (knltb_max). 
        Default 10.0
    mu_max : float
        TrueSkill mu assigned to the strongest player (knltb_min). 
        Default 40.0.

    Returns
    -------
    float
        Estimated KNLTB rating corresponding to this mu.
    """
    mu          = max(mu_min, min(mu_max, mu))
    normalised  = (mu_max - mu) / (mu_max - mu_min)
    return knltb_min + normalised * (knltb_max - knltb_min)

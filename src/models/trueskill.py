# src/models/trueskill.py

import math

from typing import Tuple, Dict, List

import pandas as pd

from scipy.stats import norm

from models import BaseModel
from constants import DataKeys, DefaultValues
from models._utils import trueskill_mu_to_knltb, knltb_to_trueskill_mu

# ── TrueSkill Model Implementation ────────────────────────────────────

class TrueSkillModel(BaseModel):
    """
    TrueSkill-based ranking model for doubles padel.

    Each player is represented by a Gaussian skill distribution 
    (mu, sigma). Team performance is modelled as the sum of player 
    skills. Rating updates use factor graph message passing 
    approximations via the v and w update factors.

    Parameters
    ----------
    players : List[Dict]
        Player records from processed/players.json. Each record must
        contain canonical_id, display_name, and starting_rating.
        (or DataKeys constants equivalent)
    sigma0 : float
        Initial uncertainty (sigma) assigned to every player.
    beta : float
        Performance noise; controls how much a single match outcome
        is attrubuted to luck vs skill.
    draw_prob : float
        Prior probability of a draw; used to derive the draw margin
        (epsilon) for the factor graph update.
    r_0 : float
        Default KNLTB rating for players without an initial rating,
        used to seed the initial mu via knltb_to_trueskill_mu()
    """
    def __init__(
            self,
            players:   List[Dict],
            sigma0:    float = DefaultValues.Models.TrueSkill.SIGMA0,
            beta:      float = DefaultValues.Models.TrueSkill.BETA,
            draw_prob: float = DefaultValues.Models.TrueSkill.DRAW_PROB,
            r_0:       float = DefaultValues.Models.TrueSkill.R0,
    ) -> None:
        self.sigma0     = sigma0
        self.beta       = beta
        self.epsilon    = float(norm.ppf((draw_prob + 1) / 2) * 2 * beta)
        self._history   = []

        self.ratings = {
            p[DataKeys.Player.ID]: {
                DataKeys.Player.NAME:         p[DataKeys.Player.NAME],
                DataKeys.Rating.INITIAL_RANK: knltb_to_trueskill_mu(
                    float(p[DataKeys.Rating.INITIAL_RANK])
                    if p[DataKeys.Rating.INITIAL_RANK]
                    else r_0
                ),
                DataKeys.Rating.SKILL_MU:      knltb_to_trueskill_mu(
                    float(p[DataKeys.Rating.INITIAL_RANK])
                    if p[DataKeys.Rating.INITIAL_RANK] 
                    else r_0
                ),
                DataKeys.Rating.SKILL_SIGMA:   sigma0,
            }
            for p in players
        }

    # ── Internal Helpers ──────────────────────────────────────────────

    @staticmethod
    def _team_values(
        mu_p1: float, mu_p2: float,
        sigma_p1: float, sigma_p2: float
    ) -> Tuple[float, float]:
        """
        Compute the combined mean and variance for a two-player team.

        Parameters
        ----------
        mu_p1, mu_p2 : float
            Mu value of players 1 and 2.
        sigma_p1, sigma_p2 : float
            Sigma values of player 1 and 2.

        Returns
        -------
        Tuple[float, float]
            (team_mu, team_variance)
        """
        return mu_p1 + mu_p2, sigma_p1 ** 2 + sigma_p2 ** 2
    
    # ── Methods ───────────────────────────────────────────────────────

    def expected_result(
        self,
        mu_ta: float, var_ta: float,
        mu_tb: float, var_tb: float,
    ) -> float:
        """
        Calculate the probability of team A winning against team B.

        Parameters
        ----------
        mu_ta, var_ta : float
            Mean and variance of team A.
        mu_tb, var_tb : float
            Mean and variance of team B.

        Returns
        -------
        float
            Win probability for team A (between 0 and 1).
        """
        c = math.sqrt(var_ta + var_tb + 2 * self.beta ** 2)
        return float(norm.cdf((mu_ta - mu_tb) / c))
    

    def predict(
        self,
        ta_p1: str, ta_p2: str,
        tb_p1: str, tb_p2: str,
    ) -> Dict:
        """
        Predict the outcome of a match between two teams.

        Confidence intervals are derived from the variance of the 
        performance difference distribution: a wider combined sigma 
        means less certainty.

        Parameters
        ----------
        ta_p1, ta_p2 : str
            Canonical player IDs for team A.
        tb_p1, tb_p2 : str
            Canonical player IDs for team B.

        Returns
        -------
        Dict
            {
                "team_a_win_prob": float,
                "team_b_win_prob": float,
                "team_a_mu":       float,
                "team_b_mu":       float,
                "team_a_var":      float,
                "team_b_var":      float,
                "confidence":      float,
                "ci_lower":        float,
                "ci_upper":        float,
            }
        """
        for pid in [ta_p1, ta_p2, tb_p1, tb_p2]:
            if pid not in self.ratings:
                raise ValueError(
                    f"Player '{pid}' not found in ratings. "
                    "Ensure all players are present in players.json."
                )
            
        mu_ta, var_ta = self._team_values(
            self.ratings[ta_p1][DataKeys.Rating.SKILL_MU],
            self.ratings[ta_p2][DataKeys.Rating.SKILL_MU],
            self.ratings[ta_p1][DataKeys.Rating.SKILL_SIGMA],
            self.ratings[ta_p2][DataKeys.Rating.SKILL_SIGMA],
        )
        mu_tb, var_tb = self._team_values(
            self.ratings[tb_p1][DataKeys.Rating.SKILL_MU],
            self.ratings[tb_p2][DataKeys.Rating.SKILL_MU],
            self.ratings[tb_p1][DataKeys.Rating.SKILL_SIGMA],
            self.ratings[tb_p2][DataKeys.Rating.SKILL_SIGMA],
        )

        prob_a = self.expected_result(mu_ta, var_ta, mu_tb, var_tb)

        # Confidence interval: perturb combined sigma by 1.96 (95% CI)
        c        = math.sqrt(var_ta + var_tb + 2 * self.beta ** 2)
        t_centre = (mu_ta - mu_tb) / c
        ci_lower = float(norm.cdf(t_centre - 1.96 * (c / (c + 1))))
        ci_upper = float(norm.cdf(t_centre + 1.96 * (c / (c + 1))))

        # Confidence proxy: how tight the combined uncertainty is
        max_sigma  = self.sigma0 * 4
        confidence = max(0.0, 1.0 - (c / max_sigma))

        return {
            "team_a_win_prob":  prob_a,
            "team_b_win_prob":  1 - prob_a,
            "team_a_mu":        mu_ta,
            "team_b_mu":        mu_tb,
            "team_a_var":       var_ta,
            "team_b_var":       var_tb,
            "confidence":       confidence,
            "ci_lower":         ci_lower,
            "ci_upper":         ci_upper,
        }
    

    def update(self, match: Dict, teams: List[Dict]) -> None:
        """
        Process a single match and update player mu and sigma using
        TrueSkill factor graph update equations.

        Parameters
        ----------
        match: Dict
            Flat match entry from processed/matches.json.
        teams : List[Dict]
            Team registry from processed/teams.json. Used to resolve the
            four player IDs participating in this match.
        """
        ta_p1, ta_p2, tb_p1, tb_p2 = self._resolve_team_players(
            match, teams
        )

        pred   = self.predict(ta_p1, ta_p2, tb_p1, tb_p2)
        mu_ta  = pred["team_a_mu"]
        var_ta = pred["team_a_var"]
        mu_tb  = pred["team_b_mu"]
        var_tb = pred["team_b_var"]
        c      = math.sqrt(var_ta + var_tb + 2 * self.beta ** 2)

        winner  = match[DataKeys.Match.WINNER]
        is_draw = (winner == 0)

        if not is_draw:
            winner_mu = mu_ta if winner == 1 else mu_tb
            loser_mu  = mu_tb if winner == 1 else mu_ta
            t         = (winner_mu - loser_mu - self.epsilon) / c
            v         = norm.pdf(t) / norm.cdf(t)
            w         = v * (v + t)
        else:
            t     = (mu_ta - mu_tb) / c
            denom = norm.cdf(self.epsilon - t) - norm.cdf(-self.epsilon - t)
            v     = (
                norm.pdf(-self.epsilon - t) - norm.pdf(self.epsilon - t)
            ) / denom
            w     = v ** 2 + (
                (self.epsilon - t) * norm.pdf(self.epsilon - t)
                + (self.epsilon + t) * norm.pdf(self.epsilon + t)
            ) / denom

        for team_id, team_pids in [(1, [ta_p1, ta_p2]), (2, [tb_p1, tb_p2])]:
            sign = 1 if (is_draw or winner == team_id) else -1

            for pid in team_pids:
                sigma = self.ratings[pid][DataKeys.Rating.SKILL_SIGMA]
                var   = sigma ** 2

                self.ratings[pid][DataKeys.Rating.SKILL_MU]   += sign * (var / c) * v
                self.ratings[pid][DataKeys.Rating.SKILL_SIGMA] = math.sqrt(
                    var * (1 - (var / c ** 2) * w)
                )
                self._log_history(
                    match_id=  match[DataKeys.Match.ID],
                    date=      match[DataKeys.Match.DATE],
                    player_id= pid,
                    mu=        self.ratings[pid][DataKeys.Rating.SKILL_MU],
                    sigma=     self.ratings[pid][DataKeys.Rating.SKILL_SIGMA],
                    trueskill_rating=   trueskill_mu_to_knltb(
                        self.ratings[pid][DataKeys.Rating.SKILL_MU]
                    ),
                    adjusted_trueskill= trueskill_mu_to_knltb(
                        self.ratings[pid][DataKeys.Rating.SKILL_MU] 
                        - 3 * self.ratings[pid][DataKeys.Rating.SKILL_SIGMA]
                    ),
                )


    def export(self) -> pd.DataFrame:
        """
        Return current TrueSkill ratings as a DataFrame.

        Returns
        -------
        pd.DataFrame
            columns: canonical_id, display_name, initial_rating,
            mu, sigma, trueskill_rating, adjusted_trueskill. 
            (or DataKeys equivalent)
        """
        return pd.DataFrame([
            {
                DataKeys.Player.ID:                 pid,
                DataKeys.Player.NAME:               data[DataKeys.Player.NAME],
                DataKeys.Rating.INITIAL_RANK: 
                    data[DataKeys.Rating.INITIAL_RANK],
                DataKeys.Rating.SKILL_MU:           
                    data[DataKeys.Rating.SKILL_MU],
                DataKeys.Rating.SKILL_SIGMA:        
                    data[DataKeys.Rating.SKILL_SIGMA],
                DataKeys.Rating.TRUESKILL_RANK:     trueskill_mu_to_knltb(
                    data[DataKeys.Rating.SKILL_MU]
                ),
                DataKeys.Rating.ADJUSTED_TRUESKILL: trueskill_mu_to_knltb(
                    data[DataKeys.Rating.SKILL_MU] 
                    - (3 * data[DataKeys.Rating.SKILL_SIGMA])
                ),
            }
            for pid, data in self.ratings.items()
        ])

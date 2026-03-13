# src/models/knltb.py

import math

from typing import Dict, List

import pandas as pd

from models import BaseModel
from constants import DataKeys, DefaultValues

# ── Knltb Model Implementation ────────────────────────────────────────

class KnltbModel(BaseModel):
    """
    ELO-based ranking model following the KNLTB rating methodology for 
    padel.

    Team ratings are aggregated from individual player ratings using a 
    weighted contribution: the strongest player contributes theta, the 
    weaker (1 - theta). Rating updates follow the standard ELO formula 
    using a logistic expected score.

    Parameters
    ----------
    players : List[Dict]
        Player records from processed/players.json. Each record must
        contain canonical_id, display_name, and starting_rating.
        (according to the DataKeys constants)
    k : float
        Maximum rating change per match (ELO K-factor)
    q : float
        Logistic scaling factor controlling sensitivity of win 
        expectation to rating differences.
    theta : float
        Contribution weight of the stronger player to the team rating.
        Must be between 0.0 and 1.0.
    r_0 : float
        Default starting rating for players without an initial rating.
    """

    def __init__(
        self,
        players: List[Dict],
        k: float     = DefaultValues.Models.Knltb.K,
        q: float     = DefaultValues.Models.Knltb.Q,
        theta: float = DefaultValues.Models.Knltb.THETA,
        r_0: float   = DefaultValues.Models.Knltb.R0
    ) -> None:
        self.k        = k
        self.q        = q
        self.theta    = theta
        self._history = []

        self.ratings = {
            p[DataKeys.Player.ID]: {
                DataKeys.Player.NAME:           p[DataKeys.Player.NAME],
                DataKeys.Rating.INITIAL_RANK: 
                    float(p[DataKeys.Rating.INITIAL_RANK]),
                DataKeys.Rating.KNLTB_RANK:     
                    float(p[DataKeys.Rating.INITIAL_RANK]) 
                    if p[DataKeys.Rating.INITIAL_RANK] else r_0,
                DataKeys.Player.MATCHES_PLAYED: 0,
            }
            for p in players
        }

    # ── Methods ───────────────────────────────────────────────────────

    def expected_result(self, ra: float, rb: float) -> float:
        """
        Calculate the win probability for team A against team B
        using a logistic function.

        Parameters
        -----------
        ra : float
            Aggregated rating of team A.
        rb : float
            Aggregated rating of team B.

        Returns
        --------
        float
            Win probability for team A (between 0 and 1).
        """
        return 1 / (1 + math.e ** (self.q * (ra - rb)))
    

    def _aggregate_team_rating(self, r1: float, r2: float) -> float:
        """
        Aggregate two player ratings into a single team rating.
        The stronger player contributes theta, the weaker (1 - theta).

        Parameters
        -----------
        r1, r2 : float
            Individual player ratings

        Returns
        --------
        float
            Final team rating
        """
        return max(r1, r2) * self.theta + min(r1, r2) * (1 - self.theta)


    def predict(
        self,
        ta_p1: str, ta_p2: str,
        tb_p1: str, tb_p2: str,
    ) -> Dict[str, float]:
        """
        Predict the outcome of a match between two teams.

        Parameters
        -----------
        ta_p1, ta_p2 : str
            Canonical player IDs for team A.
        tb_p1, tb_p2 : str
            Canonical player IDs for team B.

        Returns
        --------
        dict
            {
                "team_a_win_prob": float,
                "team_b_win_prob": float,
                "team_a_rating":   float,
                "team_b_rating":   float,
                "confidence":      float,
            }
        """
        for pid in [ta_p1, ta_p2, tb_p1, tb_p2]:
            if pid not in self.ratings:
                raise ValueError(
                    f"Player '{pid}' not found in ratings. "
                    "Ensure all players are present in players.json."
                )
            
        r_ta = self._aggregate_team_rating(
            self.ratings[ta_p1][DataKeys.Rating.KNLTB_RANK],
            self.ratings[ta_p2][DataKeys.Rating.KNLTB_RANK]
        )
        r_tb = self._aggregate_team_rating(
            self.ratings[tb_p1][DataKeys.Rating.KNLTB_RANK],
            self.ratings[tb_p2][DataKeys.Rating.KNLTB_RANK]
        )

        prob_a = self.expected_result(r_ta, r_tb)

        return {
            "team_a_win_prob": prob_a,
            "team_b_win_prob": 1 - prob_a,
            "team_a_rating":   r_ta,
            "team_b_rating":   r_tb,
            "confidence":      abs(r_ta - r_tb)
        } 
        

    def update(self, match: Dict, teams: List[Dict]) -> None:
        """
        Process a single match and update player ratings.
        Winner is read from the pre-computed match field.

        Parameters
        ----------
        match : Dict
            Flat match entry from processed/matches.json.
        teams : List[Dict]
            Team registry from processed/teams.json. Used to resolve
            the four player IDs participating in this match.
        """
        ta_p1, ta_p2, tb_p1, tb_p2 = self._resolve_team_players(
            match, teams
        )

        prob_a = self.predict(ta_p1, ta_p2, tb_p1, tb_p2)["team_a_win_prob"]
        prob_b = 1 - prob_a

        winner = match[DataKeys.Match.WINNER]
        match winner:
            case 1:
                result_a, result_b = 1.0, 0.0
            case 2:
                result_a, result_b = 0.0, 1.0
            case _:
                result_a, result_b = 0.5, 0.5

        for pid in [ta_p1, ta_p2]:
            self.ratings[pid][DataKeys.Rating.KNLTB_RANK]     += (
                self.k * (prob_a - result_a)
            )
            self.ratings[pid][DataKeys.Player.MATCHES_PLAYED] += 1
            self._log_history(
                match_id=     match[DataKeys.Match.ID],
                date=         match[DataKeys.Match.DATE],
                player_id=    pid,
                knltb_rating= self.ratings[pid][DataKeys.Rating.KNLTB_RANK],
            )

        for pid in [tb_p1, tb_p2]:
            self.ratings[pid][DataKeys.Rating.KNLTB_RANK]     += (
                self.k * (prob_b - result_b)
            )
            self.ratings[pid][DataKeys.Player.MATCHES_PLAYED] += 1
            self._log_history(
                match_id=     match[DataKeys.Match.ID],
                date=         match[DataKeys.Match.DATE],
                player_id=    pid,
                knltb_rating= self.ratings[pid][DataKeys.Rating.KNLTB_RANK],
            )

    
    def export(self) -> pd.DataFrame:
        """
        Returns current KNLTB ratings as a DataFrame.

        Returns
        -------
        pd.DataFrame
            columns: canonical_id, display_name, initial_rating,
            matches_played, knltb_rating. (or DataKeys equivalent).
        """
        return pd.DataFrame([
            {
                DataKeys.Player.ID:             pid,
                DataKeys.Player.NAME:           data[DataKeys.Player.NAME],
                DataKeys.Rating.INITIAL_RANK:   
                    data[DataKeys.Rating.INITIAL_RANK],
                DataKeys.Player.MATCHES_PLAYED: 
                    data[DataKeys.Player.MATCHES_PLAYED],
                DataKeys.Rating.KNLTB_RANK:     
                    data[DataKeys.Rating.KNLTB_RANK],
            }
            for pid, data in self.ratings.items()
        ])
    
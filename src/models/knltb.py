#src/models/knltb.py

import math
import pandas as pd

from typing import Dict, List

from models import BaseModel
from constants import DataKeys, DefaultValues

#-------------------------------------------------------------------------

class KnltbModel(BaseModel):
    """
    ELO-based ranking model following the KNLTB rating methodology for padel.

    Team ratings are aggregated from individual player ratings using a weighted
    contribution: the strongest player contributes theta, the weaker (1 - theta).
    Rating updates follow the standard ELO formula using a logistic expected score.

    Parameters
    -----------
    players : Dict[str, Dict]
        Player data with columns: canonical_id, display_name, starting_rating.
        (according to the DataKeys constants)
    k : float
        Maximum rating change per match (ELO K-factor)
    q : float
        Logistic scaling factor controlling sensitivity of win expectation
        to rating differences.
    theta : float
        Contribution weight of the stronger player to the team rating.
        Must be between 0.0 and 1.0.
    r_0 : float
        Default value for players without an initial rating.
    """

    def __init__(
        self,
        players: Dict[str, Dict],
        k: float = DefaultValues.Models.Knltb.K,
        q: float = DefaultValues.Models.Knltb.Q,
        theta: float = DefaultValues.Models.Knltb.THETA,
        r_0: float = DefaultValues.Models.Knltb.R0
    ) -> None:
        self.k =        k
        self.q =        q
        self.theta =    theta
        self._history = []

        self.ratings = {
            key: {
                DataKeys.Player.NAME: value[DataKeys.Player.NAME],
                DataKeys.Rating.INITIAL_RANK: float(value[DataKeys.Rating.INITIAL_RANK]),
                DataKeys.Rating.KNLTB_RANK: float(value[DataKeys.Rating.INITIAL_RANK]) if value[DataKeys.Rating.INITIAL_RANK] else r_0,
                DataKeys.Player.NUM_MATCHES_PLAYED: 0,
            }
            for key, value in players.items()
        }

    #-------------------------------------------------------------------------

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
    

    def predict(
        self,
        ta_p1: str,
        ta_p2: str,
        tb_p1: str,
        tb_p2: str,
    ) -> Dict[str, float]:
        """
        Predict the outcome of a match between two teams.
        Works for any combination of players - they do not need to have
        played each other before or be in the same poule.

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
                "team_a_win_prob":  float,  # probability team A wins
                "team_b_win_prob":  float,  # probability team B wins
                "team_a_rating":    float,  # aggregated team A rating
                "team_b_rating":    float,  # aggregated team B rating
                "confidence":       float,  # absolute rating difference (higher = more confident)
            }
        """
        for pid in [ta_p1, ta_p2, tb_p1, tb_p2]:
            if pid not in self.ratings:
                raise ValueError(
                    f"Player '{pid}' not found in ratings."
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
            "team_a_win_prob":  prob_a,
            "team_b_win_prob":  1 - prob_a,
            "team_a_rating":    r_ta,
            "team_b_rating":    r_tb,
            "confidence":       abs(r_ta - r_tb)
        }


    def predict_batch(self, matches: List[Dict]) -> pd.DataFrame:
        """
        Predict outcomes for a batch of matches using current ratings.
        Useful for evaluating upcoming scheduled matches.

        Parameters
        -----------
        matches : List[Dict]
            List of match dicts with keys: match_id, team_1, team_2
            (or similar as defined in DataKeys constants).

        Returns
        --------
        pd.DataFrame
            DataFrame containing important match data including prediction values
        """
        results = []
        for match in matches:
            tap1: str = match[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_1]
            tap2: str = match[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_2]
            tbp1: str = match[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_1]
            tbp2: str = match[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_2]

            pred = self.predict(tap1, tap2, tbp1, tbp2)
            results.append({
                DataKeys.Match.ID:                                      match[DataKeys.Match.ID],
                DataKeys.Match.DATE:                                    match[DataKeys.Match.DATE],
                DataKeys.Match.TIME:                                    match[DataKeys.Match.TIME],
                f"{DataKeys.Match.TEAM_1}_{DataKeys.Team.PLAYER_1}":    self.ratings[tap1][DataKeys.Player.NAME],
                f"{DataKeys.Match.TEAM_1}_{DataKeys.Team.PLAYER_2}":    self.ratings[tap2][DataKeys.Player.NAME],
                f"{DataKeys.Match.TEAM_2}_{DataKeys.Team.PLAYER_1}":    self.ratings[tbp1][DataKeys.Player.NAME],
                f"{DataKeys.Match.TEAM_2}_{DataKeys.Team.PLAYER_2}":    self.ratings[tbp2][DataKeys.Player.NAME],
                **pred
            })
        return pd.DataFrame(results)
        

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
    

    def update(self, match: Dict) -> None:
        """
        Process a single match and update player ratings.
        Winner is derived from team scores.

        Parameters
        -----------
        match : Dict
            dict match entry from matches.json.
        """
        ta_p1: str = match[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_1]
        ta_p2: str = match[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_2]
        tb_p1: str = match[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_1]
        tb_p2: str = match[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_2]

        prob_a = self.predict(ta_p1, ta_p2, tb_p1, tb_p2)["team_a_win_prob"]
        prob_b = 1 - prob_a

        winner = self.derive_winner(match[DataKeys.Match.TEAM_1][DataKeys.Team.SCORE], match[DataKeys.Match.TEAM_2][DataKeys.Team.SCORE])
        match winner:
            case 1:
                result_a, result_b = 1.0, 0.0
            case 2:
                result_a, result_b = 0.0, 1.0
            case _:
                result_a, result_b = 0.5, 0.5

        for pid in [ta_p1, ta_p2]:
            self.ratings[pid][DataKeys.Rating.KNLTB_RANK]           += self.k * (prob_a - result_a)
            self.ratings[pid][DataKeys.Player.NUM_MATCHES_PLAYED]   += 1
            self._log_history(
                match_id=       match[DataKeys.Match.ID],
                date=           match[DataKeys.Match.DATE],
                player_id=      pid,
                knltb_rating=   self.ratings[pid][DataKeys.Rating.KNLTB_RANK]
            )

        for pid in [tb_p1, tb_p2]:
            self.ratings[pid][DataKeys.Rating.KNLTB_RANK]           += self.k * (prob_b - result_b)
            self.ratings[pid][DataKeys.Player.NUM_MATCHES_PLAYED]   += 1
            self._log_history(
                match_id=       match[DataKeys.Match.ID],
                date=           match[DataKeys.Match.DATE],
                player_id=      pid,
                knltb_rating=   self.ratings[pid][DataKeys.Rating.KNLTB_RANK]
            )

    #-------------------------------------------------------------------------
    
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
                DataKeys.Player.ID:                 pid,
                DataKeys.Player.NAME:               data[DataKeys.Player.NAME],
                DataKeys.Rating.INITIAL_RANK:       data[DataKeys.Rating.INITIAL_RANK],
                DataKeys.Player.NUM_MATCHES_PLAYED: data[DataKeys.Player.NUM_MATCHES_PLAYED],
                DataKeys.Rating.KNLTB_RANK:         data[DataKeys.Rating.KNLTB_RANK],
            }
            for pid, data in self.ratings.items()
        ])
    
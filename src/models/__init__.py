# src/models/__init__.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, final, List, Tuple

import pandas as pd

from constants import DataKeys

# ── Base Model Implementation ─────────────────────────────────────────

class BaseModel(ABC):
    """
    Abstract base class for all ranking models.

    Subclasses must implement:
    - __init__        : initialise ratings from a players dict
    - expected_result : calculate win probability between two teams
    - update          : process a single match, update internal ratings
    - export          : return ratings as a DataFrame
    - predict         : predict the outcome of a match by player IDs

    Final methods (do not override):
    - run              : iterate over all matches and call update()
    - save             : export ratings to disk in configured format
    - history          : return rating progression log as DataFrame
    - predict_batch    : predict outcomes for a list of match dicts
    - _resolve_players : look up player IDs from the teams registry
    """
    ratings: Dict[str, Dict]
    _history: List[Dict]

    # ── Abstract interface ────────────────────────────────────────────

    @abstractmethod
    def __init__(self, players: List[Dict]) -> None:
        raise NotImplementedError
    

    @abstractmethod
    def expected_result(self, *args, **kwargs) -> float:
        """
        Calculate the expected win probability for one team against 
        another. Signature varies per model implementation.

        Returns
        -------
        float
            The expected chance of Team A winning against Team B.
        """
        raise NotImplementedError
    

    @abstractmethod
    def update(self, match: Dict, teams: List[Dict]) -> None:
        """
        Process a single match dict and update internal ratings in 
        place. Implementation should call _log_history() after updating 
        ratings.

        The teams registry is required to resolve the player IDs that
        participated in this match.

        Parameters
        ----------
        match : Dict
            Flat match entry from processed/matches.json. Contains
            team_1_id, team_2_id, winner, is_valid, is_played, etc.
        teams : List[Dict]
            Team registry from processed/teams.json. Required to
            resolve player IDs for each team in the match.
        """
        raise NotImplementedError
    

    @abstractmethod
    def export(self) -> pd.DataFrame:
        """
        Return current ratings as a DataFrame.
        File output is handled seperately by save().

        Returns
        -------
        pd.DataFrame
            DataFrame containing the current ratings in a table.
        """
        raise NotImplementedError
    

    @abstractmethod
    def predict(
        self,
        ta_p1: str, ta_p2: str,
        tb_p1: str, tb_p2: str,
    ) -> Dict:
        """
        Predict the outcome of a match between two teams by player ID.
        Works for any combination of players; they do not need to have
        played each other before or be in the same poule.

        Parameters
        ----------
        ta_p1, ta_p2 : str
            Caonical player IDs for team A.
        tb_p1, tb_p2 : str
            Caonical player IDs for team B.

        Returns
        -------
        Dict
            Prediction dict containing at minimum:
            - team_a_win_prob : float
            - team_b_win_prob : float
            - confidence      : float
        """
        raise NotImplementedError
    
    # ── Final methods ─────────────────────────────────────────────────

    @final
    @staticmethod
    def _resolve_team_players(
        match: Dict,
        teams: List[Dict],
    ) -> Tuple[str, str, str, str]:
        """
        Resolve the four player IDs for a match from the teams registry.

        Parameters
        ----------
        match : Dict
            Flat match dict. Must contain team_1_id and team_2_id
            (or DataKeys equivalent).
        teams : List[Dict]
            Team registry from processed/teams.json.

        Returns
        -------
        Tuple[str, str, str, str]
            (ta_p1, ta_p2, tb_p1, tb_p2); canonical player IDs

        Raises
        ------
        KeyError
            If either team_id is not found in the teams registry
        """
        team_1_id = match[DataKeys.Match.TEAM_1_ID]
        team_2_id = match[DataKeys.Match.TEAM_2_ID]

        team_lookup = {t[DataKeys.Team.ID]: t for t in teams}

        if team_1_id not in team_lookup:
            raise KeyError(
                f"Team '{team_1_id} not found in teams registry."
            )
        if team_2_id not in team_lookup:
            raise KeyError(
                f"Team '{team_2_id} not found in teams registry"
            )
        
        team_1 = team_lookup[team_1_id]
        team_2 = team_lookup[team_2_id]

        return (
            team_1[DataKeys.Team.PLAYER_1],
            team_1[DataKeys.Team.PLAYER_2],
            team_2[DataKeys.Team.PLAYER_1],
            team_2[DataKeys.Team.PLAYER_2],
        )


    @final
    def run(self, matches: List[Dict], teams: List[Dict]) -> None:
        """
        Run the model over all matches in chronological order.
        Only processes matches that are played and valid.
        Matches are sorted by match date and time before feeding them 
        into self.update()

        Parameters
        -----------
        matches : List[Dict]
            Flat match records from processed/matches.json.
        teams : List[Dict]
            Team registry from processed/teams.json. Padded through to
            update() for player ID resolution.
        """
        valid_matches = [
            m for m in matches
            if m.get(DataKeys.Match.IS_PLAYED)
            and m.get(DataKeys.Match.IS_VALID)
        ]
        valid_matches.sort(key=lambda m: (
            m.get(DataKeys.Match.DATE) or "1111-11-11",
            m.get(DataKeys.Match.TIME) or "99:99:99",
        ))

        for match in valid_matches:
            self.update(match, teams)


    @final
    def predict_batch(
        self,
        matches: List[Dict],
        teams: List[Dict],
    ) -> pd.DataFrame:
        """
        Predict outcomes for a batch of matches using current ratings.
        Player IDs are resolved via the teams registry.
        Useful for evaluating upcoming scheduled (pending) matches.

        Parameters
        ----------
        matches : List[Dict]
            List of flat match dicts (e.g. pending matches).
        teams : List[Dict]
            Team registry from processed/teams.json. Reuired to 
            resolve player IDs.

        Returns
        -------
        pd.DataFrame
            One row per match with match metadata and prediction fields
            from self.predict()
        """
        results = []
        for match in matches:
            ta_p1, ta_p2, tb_p1, tb_p2 = self._resolve_team_players(
                match, teams
            )
            pred = self.predict(ta_p1, ta_p2, tb_p1, tb_p2)
            results.append({
                DataKeys.Match.ID: match.get(DataKeys.Match.ID),
                DataKeys.Match.DATE: match.get(DataKeys.Match.DATE),
                DataKeys.Match.TIME: match.get(DataKeys.Match.TIME),
                f"{DataKeys.Match.TEAM_1_ID}_{DataKeys.Team.PLAYER_1}":
                    self.ratings[ta_p1][DataKeys.Player.NAME],
                f"{DataKeys.Match.TEAM_1_ID}_{DataKeys.Team.PLAYER_2}":
                    self.ratings[ta_p2][DataKeys.Player.NAME],
                f"{DataKeys.Match.TEAM_2_ID}_{DataKeys.Team.PLAYER_1}":
                    self.ratings[tb_p1][DataKeys.Player.NAME],
                f"{DataKeys.Match.TEAM_2_ID}_{DataKeys.Team.PLAYER_2}":
                    self.ratings[tb_p2][DataKeys.Player.NAME],
                **pred,
            })
        return pd.DataFrame(results)


    @final
    def save(self, output_path: str, fmt: str = "csv") -> None:
        """
        Export ratings and write to disk in the configured format.

        Parameters
        -----------
        output_path : str
            Full path to the output file without extension.
        fmt : str
            Output format; 'csv' or 'json'. Configured via config.yaml
            under models.output_format.
        """
        df   = self.export()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        match fmt:
            case "csv":
                df.to_csv(path.with_suffix(".csv"), index=False)
            case "json":
                df.to_json(
                    path.with_suffix(".json"),
                    orient     ="records",
                    indent     =2,
                    force_ascii=False
                )
            case _:
                raise ValueError(
                    f"Unsupported export format '{fmt}'",
                    ". Use 'csv' or 'json'."
                )

    
    @final
    def history(self) -> pd.DataFrame:
        """
        Return the full rating progression log as a DataFrame. Each row 
        represents a player's rating state after a single match.
        Only populated if _log_history() is called inside update()

        Returns
        --------
        pd.DataFrame
            Rating history with columns: match_id, date, player_id,
            and model-specific rating columns.
        """
        if not hasattr(self, "_history") or not self._history:
            return pd.DataFrame()
        return pd.DataFrame(self._history)


    @final
    def _log_history(
        self,
        match_id: str,
        date: str,
        player_id: str,
        **rating_fields,
    ) -> None:
        """
        Append a single rating snapshot to the history log.
        Called inside update() after ratings are update for each player.

        Parameters
        ----------
        match_id : str
            ID of the match just processed.
        date : str
            Date of the match.
        player_id : str
            Canonical player ID.
        **rating_fields
            Model-specific rating values to log (e.g. elo_rating=1050.0)
        """
        if not hasattr(self, "_history"):
            self._history = []
        self._history.append({
            f"match_{DataKeys.Match.ID}":   match_id,
            DataKeys.Match.DATE:            date,
            f"player_{DataKeys.Player.ID}": player_id,
            **rating_fields
        })

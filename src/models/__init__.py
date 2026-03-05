# src/models/__init__.py

import pandas as pd

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, final, List

from constants import DataKeys

#-------------------------------------------------------------------------

class BaseModel(ABC):
    """
    Abstract base class for all ranking models.

    Subclasses must implement:
        - __init__          : initialise ratings from a players dict
        - expected_result   : calculate win probability between two teams
        - update            : process a single match and update internal ratings
        - export            : return ratings as a DataFrame

    Final methods (do not override):
        - run               : iterate over all matches and call update()
        - save              : export ratings to disk in configured format
        - derive_winner     : derive winner from team scores
        - history           : return rating progression log as DataFrame
    """

    ratings: Dict[str, Dict]
    _history: List[Dict]

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def __init__(self, players: Dict[str, Dict]) -> None:
        raise NotImplementedError
    

    @abstractmethod
    def expected_result(self, *args, **kwargs) -> float:
        """
        Calculate the expected win probability for one team against another.
        Signature varies per model implementation.
        """
        raise NotImplementedError
    

    @abstractmethod
    def update(self, match: Dict) -> None:
        """
        Process a single match dict and update internal ratings in place.
        Implementation should call _log_history() after updating ratings.

        Parameters
        -----------
        match : Dict
            dict match entry from matches.json.
        """
        raise NotImplementedError
    

    @abstractmethod
    def export(self) -> pd.DataFrame:
        """
        Return current ratings as a DataFrame.
        File output is handled seperately by save().
        """
        raise NotImplementedError
    
    # ── Final methods ──────────────────────────────────────────────────────────

    @staticmethod
    def _sort_matches(matches: List[Dict]) -> None:
        """
        Sort a list of match dicts in place into chronological order.
        Matches with no date are placed at the front.
        Matches with a date but no time are placed before timed matches on the same date.

        Parameters
        -----------
        matches : List[Dict]
            List of match dicts from matches.json. Sorted in place, no copy is made.
        """
        matches.sort(key=lambda m: (
            m.get(DataKeys.Match.DATE) or "1111-11-11",
            m.get(DataKeys.Match.TIME) or "99:99:99"
        ))


    @final
    def run(self, matches: List[Dict]) -> None:
        """
        Run the model over all matches in chronological order.
        Matches are sorted by match date and time before feeding them into self.update()

        Parameters
        -----------
        matches : List[Dict]
            Dict of completed matches with team/player entries.
        """
        self._sort_matches(matches)

        for match in matches:
            self.update(match)


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
        df = self.export()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        match fmt:
            case "csv":
                df.to_csv(path.with_suffix(".csv"), index=False)
            case "json":
                df.to_json(
                    path.with_suffix(".json"),
                    orient="records",
                    indent=2,
                    force_ascii=False
                )
            case _:
                raise ValueError(f"Unsupported export format '{fmt}'. Use 'csv' or 'json'.")
            
    
    @final
    @staticmethod
    def derive_winner(team_1_score: int, team_2_score: int) -> int:
        """
        Derive the winning team from game scores.

        Returns
        --------
        int
            1 if team 1 wins, 2 if team 2 wins, 0 for draw.        
        """
        if team_1_score > team_2_score:
            return 1
        elif team_2_score > team_1_score:
            return 2
        return 0

    
    @final
    def history(self) -> pd.DataFrame:
        """
        Return the full rating progression log as a DataFrame.
        Each row represents a player's rating state after a single match.
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
    def _log_history(self, match_id: str, date: str, player_id: str, **rating_fields) -> None:
        """
        Append a single rating snapshot to the history log.
        Called inside update() after ratings are update for each player.

        Parameters
        -----------
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
            DataKeys.Match.ID:      match_id,
            DataKeys.Match.DATE:    date,
            DataKeys.Player.ID:     player_id,
            **rating_fields
        })

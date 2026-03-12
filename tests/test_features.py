# tests/test_features.py

import pytest

from features._base import apply_features
from features.matches import (
    enrich_matches,
    _status,
    _winner,
    _score_difference,
    _total_games,
    _read_info,
)
from features.teams import (
    enrich_teams,
    _matches_for_team,
    _completed_matches_for_team,
    _team_won,
    _team_score,
)
from features.players import (
    enrich_players,
    _team_ids_for_player,
    _matches_for_player,
    _player_won,
)
from features.tournaments import (
    enrich_tournaments,
)
from constants import DataKeys, DefaultValues


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_teams():
    """
    Sample teams list.
    Team Alpha: Alice + Bob
    Team Beta:  Charlie + Diana
    Team Gamma: Eve + Frank
    """
    return [
        {
            DataKeys.Team.ID:       "TM-ALPHA",
            DataKeys.Team.PLAYER_1: "PLR-001",
            DataKeys.Team.PLAYER_2: "PLR-002",
        },
        {
            DataKeys.Team.ID:       "TM-BETA",
            DataKeys.Team.PLAYER_1: "PLR-003",
            DataKeys.Team.PLAYER_2: "PLR-004",
        },
        {
            DataKeys.Team.ID:       "TM-GAMMA",
            DataKeys.Team.PLAYER_1: "PLR-005",
            DataKeys.Team.PLAYER_2: "PLR-006",
        },
    ]


@pytest.fixture
def sample_players():
    """Sample players list — one per player ID used in sample_teams."""
    return [
        {DataKeys.Player.ID: "PLR-001", DataKeys.Player.NAME: "Alice Johnson"},
        {DataKeys.Player.ID: "PLR-002", DataKeys.Player.NAME: "Bob Smith"},
        {DataKeys.Player.ID: "PLR-003", DataKeys.Player.NAME: "Charlie Brown"},
        {DataKeys.Player.ID: "PLR-004", DataKeys.Player.NAME: "Diana Prince"},
        {DataKeys.Player.ID: "PLR-005", DataKeys.Player.NAME: "Eve Adams"},
        {DataKeys.Player.ID: "PLR-006", DataKeys.Player.NAME: "Frank Castle"},
    ]


@pytest.fixture
def completed_match():
    """A completed, valid match between Team Alpha and Team Beta."""
    return {
        DataKeys.Match.ID:         "MATCH-001",
        DataKeys.Match.TOURNAMENT: "TOURN-001",
        DataKeys.Match.CATEGORY:   "7/6 sterk",
        DataKeys.Match.TEAM_1_ID:  "TM-ALPHA",
        DataKeys.Match.TEAM_2_ID:  "TM-BETA",
        DataKeys.Match.TEAM_1_SCORE: 14,
        DataKeys.Match.TEAM_2_SCORE: 8,
        DataKeys.Match.INFO:       None,
        DataKeys.Match.IS_PLAYED:  True,
        DataKeys.Match.IS_VALID:   True,
        DataKeys.Match.WINNER:     1,
        DataKeys.Match.TOTAL_GAMES: 22,
        DataKeys.Match.STATUS:     DefaultValues.Match.Status.COMPLETED,
    }


@pytest.fixture
def pending_match():
    """A pending match between Team Alpha and Team Gamma."""
    return {
        DataKeys.Match.ID:          "MATCH-002",
        DataKeys.Match.TOURNAMENT:  "TOURN-001",
        DataKeys.Match.CATEGORY:    "7/6 sterk",
        DataKeys.Match.TEAM_1_ID:   "TM-ALPHA",
        DataKeys.Match.TEAM_2_ID:   "TM-GAMMA",
        DataKeys.Match.TEAM_1_SCORE: None,
        DataKeys.Match.TEAM_2_SCORE: None,
        DataKeys.Match.INFO:        None,
        DataKeys.Match.IS_PLAYED:   False,
        DataKeys.Match.IS_VALID:    True,
        DataKeys.Match.WINNER:      None,
        DataKeys.Match.TOTAL_GAMES: None,
        DataKeys.Match.STATUS:      DefaultValues.Match.Status.PENDING,
    }


@pytest.fixture
def walkover_match():
    """A completed but invalid (walkover) match."""
    return {
        DataKeys.Match.ID:          "MATCH-003",
        DataKeys.Match.TOURNAMENT:  "TOURN-001",
        DataKeys.Match.CATEGORY:    "7/6 sterk",
        DataKeys.Match.TEAM_1_ID:   "TM-BETA",
        DataKeys.Match.TEAM_2_ID:   "TM-GAMMA",
        DataKeys.Match.TEAM_1_SCORE: 14,
        DataKeys.Match.TEAM_2_SCORE: 0,
        DataKeys.Match.INFO:        DefaultValues.Match.WALKOVER_VALUES[0],
        DataKeys.Match.IS_PLAYED:   True,
        DataKeys.Match.IS_VALID:    False,
        DataKeys.Match.WINNER:      1,
        DataKeys.Match.TOTAL_GAMES: 14,
        DataKeys.Match.STATUS:      DefaultValues.Match.Status.COMPLETED,
    }


@pytest.fixture
def sample_tournament():
    """Sample tournament record."""
    return {
        DataKeys.Tournament.ID:   "TOURN-001",
        DataKeys.Tournament.NAME: "Winter Open 2026",
    }


# ── Test apply_features (_base.py) ────────────────────────────────────

class TestApplyFeatures:
    def test_apply_features_basic(self):
        """Test that feature functions are applied and fields are merged."""
        records = [{"id": "R-001", "value": 10}]
        fn = lambda record, **_: {"doubled": record["value"] * 2}

        result = apply_features(records, [fn])

        assert len(result) == 1
        assert result[0]["doubled"] == 20
        assert result[0]["id"] == "R-001"

    def test_apply_features_does_not_mutate_input(self):
        """Input records must not be mutated."""
        records = [{"id": "R-001"}]
        fn = lambda record, **_: {"new_field": True}

        apply_features(records, [fn])

        assert "new_field" not in records[0]

    def test_apply_features_does_not_overwrite_existing_keys(self):
        """Existing keys must not be overwritten by feature functions."""
        records = [{"id": "R-001", "status": "original"}]
        fn = lambda record, **_: {"status": "overwritten"}

        result = apply_features(records, [fn])

        assert result[0]["status"] == "original"

    def test_apply_features_multiple_functions(self):
        """Test that multiple feature functions are all applied."""
        records = [{"value": 5}]
        fn1 = lambda record, **_: {"doubled": record["value"] * 2}
        fn2 = lambda record, **_: {"tripled": record["value"] * 3}

        result = apply_features(records, [fn1, fn2])

        assert result[0]["doubled"] == 10
        assert result[0]["tripled"] == 15

    def test_apply_features_later_fn_sees_earlier_fields(self):
        """Later feature functions should see fields added by earlier ones."""
        records = [{"value": 4}]
        fn1 = lambda record, **_: {"doubled": record["value"] * 2}
        fn2 = lambda record, **_: {"quadrupled": record.get("doubled", 0) * 2}

        result = apply_features(records, [fn1, fn2])

        assert result[0]["quadrupled"] == 16

    def test_apply_features_context_passed_through(self):
        """Context kwargs must be passed through to feature functions."""
        records = [{"id": "R-001"}]
        received = {}
        def fn(record, teams=None, **_):
            received["teams"] = teams
            return {}

        apply_features(records, [fn], teams=["team_a"])

        assert received["teams"] == ["team_a"]

    def test_apply_features_empty_records(self):
        """Empty input should return empty output."""
        result = apply_features([], [lambda r, **_: {"x": 1}])
        assert result == []


# ── Test matches.py ───────────────────────────────────────────────────

class TestMatchStatus:
    def test_status_completed(self):
        """Both scores present → completed."""
        record = {DataKeys.Match.TEAM_1_SCORE: 14, DataKeys.Match.TEAM_2_SCORE: 8}
        result = _status(record)
        assert result[DataKeys.Match.STATUS] == DefaultValues.Match.Status.COMPLETED
        assert result[DataKeys.Match.IS_PLAYED] is True

    def test_status_pending(self):
        """Both scores absent → pending."""
        record = {DataKeys.Match.TEAM_1_SCORE: None, DataKeys.Match.TEAM_2_SCORE: None}
        result = _status(record)
        assert result[DataKeys.Match.STATUS] == DefaultValues.Match.Status.PENDING
        assert result[DataKeys.Match.IS_PLAYED] is False

    def test_status_unknown(self):
        """Only one score present → unknown."""
        record = {DataKeys.Match.TEAM_1_SCORE: 14, DataKeys.Match.TEAM_2_SCORE: None}
        result = _status(record)
        assert result[DataKeys.Match.STATUS] == DefaultValues.Entries.UNKNOWN
        assert result[DataKeys.Match.IS_PLAYED] is None

    def test_status_missing_score_keys(self):
        """Missing score keys should be treated as None → pending."""
        result = _status({})
        assert result[DataKeys.Match.STATUS] == DefaultValues.Match.Status.PENDING


class TestMatchWinner:
    def test_winner_team_1(self):
        """Team 1 higher score → winner is 1."""
        record = {DataKeys.Match.TEAM_1_SCORE: 14, DataKeys.Match.TEAM_2_SCORE: 8}
        result = _winner(record)
        assert result[DataKeys.Match.WINNER] == 1
        assert result[DataKeys.Match.WINNER_SCORE] == 14
        assert result[DataKeys.Match.LOSER_SCORE] == 8

    def test_winner_team_2(self):
        """Team 2 higher score → winner is 2."""
        record = {DataKeys.Match.TEAM_1_SCORE: 6, DataKeys.Match.TEAM_2_SCORE: 14}
        result = _winner(record)
        assert result[DataKeys.Match.WINNER] == 2
        assert result[DataKeys.Match.WINNER_SCORE] == 14
        assert result[DataKeys.Match.LOSER_SCORE] == 6

    def test_winner_draw(self):
        """Equal scores → draw (0)."""
        record = {DataKeys.Match.TEAM_1_SCORE: 10, DataKeys.Match.TEAM_2_SCORE: 10}
        result = _winner(record)
        assert result[DataKeys.Match.WINNER] == 0

    def test_winner_pending_match(self):
        """Missing scores → all None."""
        record = {DataKeys.Match.TEAM_1_SCORE: None, DataKeys.Match.TEAM_2_SCORE: None}
        result = _winner(record)
        assert result[DataKeys.Match.WINNER] is None
        assert result[DataKeys.Match.WINNER_SCORE] is None
        assert result[DataKeys.Match.LOSER_SCORE] is None


class TestMatchScoreDifference:
    def test_score_difference_completed(self):
        """Score difference computed correctly."""
        record = {DataKeys.Match.TEAM_1_SCORE: 14, DataKeys.Match.TEAM_2_SCORE: 8}
        result = _score_difference(record)
        assert result[DataKeys.Match.SCORE_DIFF] == 6

    def test_score_difference_pending(self):
        """None scores → None difference."""
        record = {DataKeys.Match.TEAM_1_SCORE: None, DataKeys.Match.TEAM_2_SCORE: None}
        result = _score_difference(record)
        assert result[DataKeys.Match.SCORE_DIFF] is None

    def test_score_difference_is_absolute(self):
        """Score difference is always non-negative."""
        record = {DataKeys.Match.TEAM_1_SCORE: 5, DataKeys.Match.TEAM_2_SCORE: 12}
        result = _score_difference(record)
        assert result[DataKeys.Match.SCORE_DIFF] == 7


class TestMatchTotalGames:
    def test_total_games_completed(self):
        """Total games is sum of both scores."""
        record = {DataKeys.Match.TEAM_1_SCORE: 14, DataKeys.Match.TEAM_2_SCORE: 8}
        result = _total_games(record)
        assert result[DataKeys.Match.TOTAL_GAMES] == 22

    def test_total_games_pending(self):
        """None scores → None total."""
        record = {DataKeys.Match.TEAM_1_SCORE: None, DataKeys.Match.TEAM_2_SCORE: None}
        result = _total_games(record)
        assert result[DataKeys.Match.TOTAL_GAMES] is None


class TestMatchReadInfo:
    def test_read_info_regular(self):
        """Non-special info → valid, not walkover."""
        record = {DataKeys.Match.INFO: None}
        result = _read_info(record)
        assert result[DataKeys.Match.IS_VALID] is True
        assert result[DataKeys.Match.IS_WALKOVER] is False

    def test_read_info_walkover(self):
        """Walkover info value → invalid, is walkover."""
        record = {DataKeys.Match.INFO: DefaultValues.Match.WALKOVER_VALUES[0]}
        result = _read_info(record)
        assert result[DataKeys.Match.IS_VALID] is False
        assert result[DataKeys.Match.IS_WALKOVER] is True

    def test_read_info_canceled(self):
        """Canceled info → invalid, not walkover."""
        record = {DataKeys.Match.INFO: DefaultValues.Match.Info.CANCELED}
        result = _read_info(record)
        assert result[DataKeys.Match.IS_VALID] is False
        assert result[DataKeys.Match.IS_WALKOVER] is False


class TestEnrichMatches:
    def test_enrich_matches_completed(self):
        """Full enrichment of a completed match."""
        matches = [{
            DataKeys.Match.ID:          "MATCH-001",
            DataKeys.Match.TEAM_1_SCORE: 14,
            DataKeys.Match.TEAM_2_SCORE: 8,
            DataKeys.Match.INFO:        None,
        }]

        result = enrich_matches(matches)

        assert len(result) == 1
        m = result[0]
        assert m[DataKeys.Match.STATUS] == DefaultValues.Match.Status.COMPLETED
        assert m[DataKeys.Match.IS_PLAYED] is True
        assert m[DataKeys.Match.WINNER] == 1
        assert m[DataKeys.Match.SCORE_DIFF] == 6
        assert m[DataKeys.Match.TOTAL_GAMES] == 22
        assert m[DataKeys.Match.IS_VALID] is True

    def test_enrich_matches_pending(self):
        """Full enrichment of a pending match."""
        matches = [{
            DataKeys.Match.ID:          "MATCH-002",
            DataKeys.Match.TEAM_1_SCORE: None,
            DataKeys.Match.TEAM_2_SCORE: None,
            DataKeys.Match.INFO:        None,
        }]

        result = enrich_matches(matches)

        m = result[0]
        assert m[DataKeys.Match.STATUS] == DefaultValues.Match.Status.PENDING
        assert m[DataKeys.Match.IS_PLAYED] is False
        assert m[DataKeys.Match.WINNER] is None
        assert m[DataKeys.Match.TOTAL_GAMES] is None

    def test_enrich_matches_does_not_mutate_input(self):
        """Input list must not be mutated."""
        matches = [{
            DataKeys.Match.ID:          "MATCH-001",
            DataKeys.Match.TEAM_1_SCORE: 14,
            DataKeys.Match.TEAM_2_SCORE: 8,
            DataKeys.Match.INFO:        None,
        }]
        original_keys = set(matches[0].keys())

        enrich_matches(matches)

        assert set(matches[0].keys()) == original_keys


# ── Test teams.py ─────────────────────────────────────────────────────

class TestMatchesForTeam:
    def test_matches_for_team_as_team_1(self, completed_match):
        """Returns matches where team appears as team_1."""
        result = _matches_for_team("TM-ALPHA", [completed_match])
        assert len(result) == 1

    def test_matches_for_team_as_team_2(self, completed_match):
        """Returns matches where team appears as team_2."""
        result = _matches_for_team("TM-BETA", [completed_match])
        assert len(result) == 1

    def test_matches_for_team_not_in_match(self, completed_match):
        """Returns empty list when team not in match."""
        result = _matches_for_team("TM-GAMMA", [completed_match])
        assert result == []

    def test_matches_for_team_empty_match_list(self):
        """Returns empty list when no matches."""
        result = _matches_for_team("TM-ALPHA", [])
        assert result == []


class TestCompletedMatchesForTeam:
    def test_excludes_pending_matches(self, completed_match, pending_match):
        """Only completed, valid matches are returned."""
        result = _completed_matches_for_team("TM-ALPHA", [completed_match, pending_match])
        assert len(result) == 1
        assert result[0][DataKeys.Match.ID] == "MATCH-001"

    def test_excludes_invalid_matches(self, walkover_match):
        """Walkover matches (is_valid=False) are excluded."""
        result = _completed_matches_for_team("TM-BETA", [walkover_match])
        assert result == []


class TestTeamWon:
    def test_team_won_as_team_1(self, completed_match):
        """Team 1 with winner=1 → won."""
        assert _team_won("TM-ALPHA", completed_match) is True

    def test_team_lost_as_team_2(self, completed_match):
        """Team 2 with winner=1 → lost."""
        assert _team_won("TM-BETA", completed_match) is False

    def test_team_won_as_team_2(self):
        """Team 2 with winner=2 → won."""
        match = {
            DataKeys.Match.WINNER: 2,
            DataKeys.Match.TEAM_1_ID: "TM-ALPHA",
            DataKeys.Match.TEAM_2_ID: "TM-BETA",
        }
        assert _team_won("TM-BETA", match) is True

    def test_draw_returns_false(self):
        """Draw (winner=0) → neither team won."""
        match = {
            DataKeys.Match.WINNER: 0,
            DataKeys.Match.TEAM_1_ID: "TM-ALPHA",
            DataKeys.Match.TEAM_2_ID: "TM-BETA",
        }
        assert _team_won("TM-ALPHA", match) is False
        assert _team_won("TM-BETA", match) is False


class TestTeamScore:
    def test_score_for_team_1(self, completed_match):
        """Returns team_1_score for team 1."""
        result = _team_score("TM-ALPHA", completed_match)
        assert result == 14

    def test_score_for_team_2(self, completed_match):
        """Returns team_2_score for team 2."""
        result = _team_score("TM-BETA", completed_match)
        assert result == 8

    def test_score_for_uninvolved_team(self, completed_match):
        """Returns None for team not in match."""
        result = _team_score("TM-GAMMA", completed_match)
        assert result is None


class TestEnrichTeams:
    def test_match_record_wins_losses(self, sample_teams, completed_match):
        """Wins and losses correctly computed for each team."""
        result = enrich_teams(sample_teams, matches=[completed_match])

        alpha = next(t for t in result if t[DataKeys.Team.ID] == "TM-ALPHA")
        beta  = next(t for t in result if t[DataKeys.Team.ID] == "TM-BETA")

        assert alpha[DataKeys.Team.WINS]   == 1
        assert alpha[DataKeys.Team.LOSSES] == 0
        assert beta[DataKeys.Team.WINS]    == 0
        assert beta[DataKeys.Team.LOSSES]  == 1

    def test_match_record_excludes_walkover(self, sample_teams, walkover_match):
        """Walkover matches do not count toward wins/losses."""
        result = enrich_teams(sample_teams, matches=[walkover_match])

        beta = next(t for t in result if t[DataKeys.Team.ID] == "TM-BETA")
        assert beta[DataKeys.Team.MATCHES_PLAYED] == 0

    def test_win_rate_calculated(self, sample_teams, completed_match):
        """Win rate is wins / matches_played."""
        result = enrich_teams(sample_teams, matches=[completed_match])

        alpha = next(t for t in result if t[DataKeys.Team.ID] == "TM-ALPHA")
        assert alpha[DataKeys.Team.WIN_RATE] == 1.0

    def test_win_rate_none_for_no_matches(self, sample_teams):
        """Win rate is None when no matches played."""
        result = enrich_teams(sample_teams, matches=[])

        gamma = next(t for t in result if t[DataKeys.Team.ID] == "TM-GAMMA")
        assert gamma[DataKeys.Team.WIN_RATE] is None

    def test_score_share_calculated(self, sample_teams, completed_match):
        """Average score share is computed correctly."""
        result = enrich_teams(sample_teams, matches=[completed_match])

        alpha = next(t for t in result if t[DataKeys.Team.ID] == "TM-ALPHA")
        # 14 / 22 = 0.6364
        assert alpha[DataKeys.Team.SCORE_SHARE] == pytest.approx(14 / 22, abs=1e-4)

    def test_categories_played(self, sample_teams, completed_match):
        """Categories played list is populated."""
        result = enrich_teams(sample_teams, matches=[completed_match])

        alpha = next(t for t in result if t[DataKeys.Team.ID] == "TM-ALPHA")
        assert "7/6 sterk" in alpha[DataKeys.Team.CATEGORIES]

    def test_enrich_teams_no_matches(self, sample_teams):
        """Enrichment with no matches produces zero stats."""
        result = enrich_teams(sample_teams, matches=[])

        for team in result:
            assert team[DataKeys.Team.MATCHES_PLAYED] == 0
            assert team[DataKeys.Team.WIN_RATE] is None

    def test_enrich_teams_preserves_original_fields(self, sample_teams):
        """Existing fields (team_id, player_1, player_2) are not overwritten."""
        result = enrich_teams(sample_teams, matches=[])

        for original, enriched in zip(sample_teams, result):
            assert enriched[DataKeys.Team.ID]       == original[DataKeys.Team.ID]
            assert enriched[DataKeys.Team.PLAYER_1] == original[DataKeys.Team.PLAYER_1]
            assert enriched[DataKeys.Team.PLAYER_2] == original[DataKeys.Team.PLAYER_2]


# ── Test players.py ───────────────────────────────────────────────────

class TestTeamIdsForPlayer:
    def test_finds_player_as_player_1(self, sample_teams):
        """Returns team IDs where player is player_1."""
        result = _team_ids_for_player("PLR-001", sample_teams)
        assert "TM-ALPHA" in result

    def test_finds_player_as_player_2(self, sample_teams):
        """Returns team IDs where player is player_2."""
        result = _team_ids_for_player("PLR-002", sample_teams)
        assert "TM-ALPHA" in result

    def test_player_not_in_any_team(self, sample_teams):
        """Returns empty set for unknown player."""
        result = _team_ids_for_player("PLR-999", sample_teams)
        assert result == set()


class TestMatchesForPlayer:
    def test_returns_matches_for_player(self, sample_teams, completed_match):
        """Returns completed, valid matches the player participated in."""
        result = _matches_for_player("PLR-001", [completed_match], sample_teams)
        assert len(result) == 1

    def test_excludes_pending_matches(self, sample_teams, pending_match):
        """Pending matches are excluded."""
        result = _matches_for_player("PLR-001", [pending_match], sample_teams)
        assert result == []

    def test_excludes_invalid_matches(self, sample_teams, walkover_match):
        """Walkover/invalid matches are excluded."""
        result = _matches_for_player("PLR-003", [walkover_match], sample_teams)
        assert result == []

    def test_player_not_in_match(self, sample_teams, completed_match):
        """Returns empty list when player did not participate."""
        result = _matches_for_player("PLR-005", [completed_match], sample_teams)
        assert result == []


class TestPlayerWon:
    def test_player_on_winning_team(self, sample_teams, completed_match):
        """Player on team 1 with winner=1 → won."""
        assert _player_won("PLR-001", completed_match, sample_teams) is True

    def test_player_on_losing_team(self, sample_teams, completed_match):
        """Player on team 2 with winner=1 → lost."""
        assert _player_won("PLR-003", completed_match, sample_teams) is False

    def test_player_not_in_match(self, sample_teams, completed_match):
        """Player not in match → False."""
        assert _player_won("PLR-005", completed_match, sample_teams) is False


class TestEnrichPlayers:
    def test_match_record_wins_losses(self, sample_players, sample_teams, completed_match):
        """Wins and losses correctly attributed to players."""
        result = enrich_players(
            sample_players, matches=[completed_match], teams=sample_teams
        )

        alice = next(p for p in result if p[DataKeys.Player.ID] == "PLR-001")
        charlie = next(p for p in result if p[DataKeys.Player.ID] == "PLR-003")

        assert alice[DataKeys.Player.WINS]   == 1
        assert alice[DataKeys.Player.LOSSES] == 0
        assert charlie[DataKeys.Player.WINS]   == 0
        assert charlie[DataKeys.Player.LOSSES] == 1

    def test_win_rate_calculated(self, sample_players, sample_teams, completed_match):
        """Win rate is computed from wins / matches_played."""
        result = enrich_players(
            sample_players, matches=[completed_match], teams=sample_teams
        )

        alice = next(p for p in result if p[DataKeys.Player.ID] == "PLR-001")
        assert alice[DataKeys.Player.WIN_RATE] == 1.0

    def test_win_rate_none_for_no_matches(self, sample_players, sample_teams):
        """Win rate is None for players with no matches."""
        result = enrich_players(sample_players, matches=[], teams=sample_teams)

        for player in result:
            assert player[DataKeys.Player.WIN_RATE] is None

    def test_categories_played(self, sample_players, sample_teams, completed_match):
        """Categories played correctly populated."""
        result = enrich_players(
            sample_players, matches=[completed_match], teams=sample_teams
        )

        alice = next(p for p in result if p[DataKeys.Player.ID] == "PLR-001")
        assert "7/6 sterk" in alice[DataKeys.Player.CATEGORIES]

    def test_walkover_match_excluded(self, sample_players, sample_teams, walkover_match):
        """Walkover matches do not count toward player stats."""
        result = enrich_players(
            sample_players, matches=[walkover_match], teams=sample_teams
        )

        charlie = next(p for p in result if p[DataKeys.Player.ID] == "PLR-003")
        assert charlie[DataKeys.Player.MATCHES_PLAYED] == 0

    def test_enrich_players_preserves_original_fields(self, sample_players, sample_teams):
        """Original fields (player ID, name) are not overwritten."""
        result = enrich_players(sample_players, matches=[], teams=sample_teams)

        for original, enriched in zip(sample_players, result):
            assert enriched[DataKeys.Player.ID]   == original[DataKeys.Player.ID]
            assert enriched[DataKeys.Player.NAME] == original[DataKeys.Player.NAME]


# ── Test tournaments.py ───────────────────────────────────────────────

class TestEnrichTournaments:
    def test_match_counts(self, sample_tournament, sample_teams, completed_match, pending_match):
        """Match counts split correctly by status."""
        result = enrich_tournaments(
            [sample_tournament],
            matches=[completed_match, pending_match],
            teams=sample_teams,
        )

        t = result[0]
        assert t[DataKeys.Tournament.MATCHES]           == 2
        assert t[DataKeys.Tournament.MATCHES_COMPLETED] == 1  # only completed match is played
        assert t[DataKeys.Tournament.MATCHES_PLAYED]    == 1  # only completed match is played and valid

    def test_completion_rate(self, sample_tournament, sample_teams, completed_match, pending_match):
        """Completion rate is completed / total."""
        result = enrich_tournaments(
            [sample_tournament],
            matches=[completed_match, pending_match],
            teams=sample_teams,
        )

        t = result[0]
        assert t[DataKeys.Tournament.COMPLETION_RATE] == pytest.approx(0.5, abs=1e-4)

    def test_is_completed_false(self, sample_tournament, sample_teams, completed_match, pending_match):
        """is_completed is False when pending matches remain."""
        result = enrich_tournaments(
            [sample_tournament],
            matches=[completed_match, pending_match],
            teams=sample_teams,
        )
        assert result[0][DataKeys.Tournament.IS_COMPLETED] is False

    def test_is_completed_true(self, sample_tournament, sample_teams, completed_match):
        """is_completed is True when all matches are completed."""
        result = enrich_tournaments(
            [sample_tournament],
            matches=[completed_match],
            teams=sample_teams,
        )
        assert result[0][DataKeys.Tournament.IS_COMPLETED] is True

    def test_unique_players(self, sample_tournament, sample_teams, completed_match):
        """Unique player count resolved through teams registry."""
        result = enrich_tournaments(
            [sample_tournament],
            matches=[completed_match],
            teams=sample_teams,
        )
        # completed_match involves TM-ALPHA (PLR-001, PLR-002) and TM-BETA (PLR-003, PLR-004)
        assert result[0][DataKeys.Tournament.PLAYERS] == 4

    def test_unique_players_no_double_count(self, sample_tournament, sample_teams, completed_match):
        """Players appearing in multiple matches are not double-counted."""
        # Two matches both featuring TM-ALPHA
        second_match = {
            **completed_match,
            DataKeys.Match.ID:        "MATCH-004",
            DataKeys.Match.TEAM_1_ID: "TM-ALPHA",
            DataKeys.Match.TEAM_2_ID: "TM-GAMMA",
        }
        result = enrich_tournaments(
            [sample_tournament],
            matches=[completed_match, second_match],
            teams=sample_teams,
        )
        # TM-ALPHA (PLR-001, PLR-002), TM-BETA (PLR-003, PLR-004), TM-GAMMA (PLR-005, PLR-006)
        assert result[0][DataKeys.Tournament.PLAYERS] == 6

    def test_other_tournament_matches_excluded(self, sample_teams, completed_match):
        """Matches from other tournaments don't affect counts."""
        other_tournament = {
            DataKeys.Tournament.ID:   "TOURN-999",
            DataKeys.Tournament.NAME: "Other Tournament",
        }
        result = enrich_tournaments(
            [other_tournament],
            matches=[completed_match],
            teams=sample_teams,
        )
        assert result[0][DataKeys.Tournament.MATCHES] == 0
        assert result[0][DataKeys.Tournament.PLAYERS] == 0

    def test_completion_rate_none_for_empty_tournament(self, sample_teams):
        """Completion rate is None when tournament has no matches."""
        empty_tournament = {
            DataKeys.Tournament.ID:   "TOURN-EMPTY",
            DataKeys.Tournament.NAME: "Empty Tournament",
        }
        result = enrich_tournaments([empty_tournament], matches=[], teams=sample_teams)
        assert result[0][DataKeys.Tournament.COMPLETION_RATE] is None

    def test_enrich_tournaments_preserves_original_fields(self, sample_tournament, sample_teams):
        """Original tournament fields are not overwritten."""
        result = enrich_tournaments([sample_tournament], matches=[], teams=sample_teams)
        assert result[0][DataKeys.Tournament.ID]   == "TOURN-001"
        assert result[0][DataKeys.Tournament.NAME] == "Winter Open 2026"

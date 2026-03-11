# tests/test_consolidate.py

import json
import pytest

from pathlib import Path
from unittest.mock import patch

from consolidation.parsers import (
    parse_tournament_metadata,
    load_tournament_metadata,
    _parse_match_datetime,
    parse_match,
)
from consolidation.id_resolver import (
    load_id_map,
    save_id_map,
    load_players,
    save_players,
    _generate_canonical_id,
    resolve_player,
)
from consolidation.deduplicator import (
    extract_players_from_match,
    deduplicate_players,
    _generate_team_id,
    _register_team,
    extract_teams_from_match,
)
from pipeline.run_consolidation import (
    _write_output,
    _load_raw_poule,
    _walk_tournament,
    consolidate,
)
from constants import DataKeys, FileNames


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def temp_dirs(tmp_path):
    """
    Provide isolated temporary input, output, and raw directories.
    Uses pytest's built-in tmp_path fixture — no manual cleanup needed.
    """
    input_path  = tmp_path / "input"
    output_path = tmp_path / "output"
    raw_path    = tmp_path / "raw"

    input_path.mkdir()
    output_path.mkdir()
    raw_path.mkdir()

    return {
        "base":   tmp_path,
        "input":  str(input_path),
        "output": str(output_path),
        "raw":    str(raw_path),
    }


@pytest.fixture
def sample_metadata():
    return {
        "tournament_name":    "Test Tournament",
        "start_date":         "2026-01-15",
        "end_date":           "2026-01-17",
        "num_categories":     3,
        "num_registrations":  24,
        "scraped_at":         "2026-01-10T10:00:00Z",
    }


@pytest.fixture
def sample_raw_match():
    """
    Raw match dict as it comes from the scraper — with nested team dicts
    containing player sub-dicts with 'name' keys and integer scores.
    """
    return {
        "match_id":   "match_001",
        "category":   "7/6 sterk",
        "poule":      "Groep A",
        "date":       "2026-01-15",
        "time":       "14:30:00",
        "info":       "Regular match",
        "scraped_at": "2026-01-10T10:00:00Z",
        "team_1": {
            "player_1": {"name": "Alice Johnson"},
            "player_2": {"name": "Bob Smith"},
            "score":    14,
        },
        "team_2": {
            "player_1": {"name": "Charlie Brown"},
            "player_2": {"name": "Diana Prince"},
            "score":    8,
        },
    }


@pytest.fixture
def sample_players():
    return {
        "PLR-001-ABC123": {
            DataKeys.Player.ID:           "PLR-001-ABC123",
            DataKeys.Player.NAME:         "Alice Johnson",
            DataKeys.Player.GENDER:       "female",
            DataKeys.Rating.INITIAL_RANK: 1500.0,
        },
        "PLR-002-DEF456": {
            DataKeys.Player.ID:           "PLR-002-DEF456",
            DataKeys.Player.NAME:         "Bob Smith",
            DataKeys.Player.GENDER:       "male",
            DataKeys.Rating.INITIAL_RANK: 1450.0,
        },
    }


@pytest.fixture
def sample_id_map():
    return {
        "Alice Johnson": "PLR-001-ABC123",
        "Bob Smith":     "PLR-002-DEF456",
    }


@pytest.fixture
def four_players():
    """
    Four fully resolved player dicts as returned by 
    extract_players_from_match.
    """
    return [
        {
            DataKeys.Player.ID: "PLR-001-ABC123",
            DataKeys.Player.NAME: "Alice Johnson", 
            DataKeys.Player.GENDER: "female"
        },
        {
            DataKeys.Player.ID: "PLR-002-DEF456", 
            DataKeys.Player.NAME: "Bob Smith",      
            DataKeys.Player.GENDER: "male"
        },
        {
            DataKeys.Player.ID: "PLR-003-GHI789", 
            DataKeys.Player.NAME: "Charlie Brown",  
            DataKeys.Player.GENDER: "male"
        },
        {
            DataKeys.Player.ID: "PLR-004-JKL012", 
            DataKeys.Player.NAME: "Diana Prince",   
            DataKeys.Player.GENDER: "female"
        },
    ]


# ── Parsers ───────────────────────────────────────────────────────────────────

class TestParseTournamentMetadata:
    def test_basic(self, sample_metadata):
        result = parse_tournament_metadata("TOURN-001", sample_metadata)

        assert result[DataKeys.Tournament.ID]                == "TOURN-001"
        assert result[DataKeys.Tournament.NAME]              == "Test Tournament"
        assert result[DataKeys.Tournament.START_DATE]        == "2026-01-15"
        assert result[DataKeys.Tournament.END_DATE]          == "2026-01-17"
        assert result[DataKeys.Tournament.NUM_CATEGORIES]    == 3
        assert result[DataKeys.Tournament.NUM_REGISTRATIONS] == 24
        assert result[DataKeys.General.SCRAPED_AT]           == "2026-01-10T10:00:00Z"

    def test_missing_keys_raises(self):
        with pytest.raises(KeyError):
            parse_tournament_metadata("TOURN-001", {"tournament_name": "Only name"})


class TestLoadTournamentMetadata:
    def test_success(self, temp_dirs, sample_metadata):
        path = Path(temp_dirs["raw"]) / "TOURN-001"
        path.mkdir()
        (path / FileNames.Raw.METADATA).write_text(
            json.dumps(sample_metadata), encoding="utf-8"
        )

        result = load_tournament_metadata(path)
        assert result[DataKeys.Tournament.ID]   == "TOURN-001"
        assert result[DataKeys.Tournament.NAME] == "Test Tournament"

    def test_missing_metadata_raises(self, temp_dirs):
        path = Path(temp_dirs["raw"]) / "TOURN-001"
        path.mkdir()

        with pytest.raises(FileNotFoundError):
            load_tournament_metadata(path)


class TestParseMatchDatetime:
    def test_valid(self):
        d, t = _parse_match_datetime("2026-01-15", "14:30:00")
        assert d == "2026-01-15"
        assert t == "14:30:00"

    def test_invalid_date(self):
        d, t = _parse_match_datetime("not-a-date", "14:30:00")
        assert d is None
        assert t == "14:30:00"

    def test_invalid_time(self):
        d, t = _parse_match_datetime("2026-01-15", "not-a-time")
        assert d == "2026-01-15"
        assert t is None

    def test_both_invalid(self):
        d, t = _parse_match_datetime("bad", "bad")
        assert d is None
        assert t is None

    def test_empty_strings(self):
        d, t = _parse_match_datetime("", "")
        assert d is None
        assert t is None

    def test_none_inputs(self):
        # .get() on a match dict with missing keys returns None
        d, t = _parse_match_datetime(None, None) # type: ignore
        assert d is None
        assert t is None


class TestParseMatch:
    def test_basic(self, sample_raw_match):
        result = parse_match(
            match         =sample_raw_match,
            tournament_id ="TOURN-001",
            team_1_id     ="TEAM-AABBCC",
            team_2_id     ="TEAM-DDEEFF",
        )

        assert result[DataKeys.Match.ID]           == "match_001"
        assert result[DataKeys.Match.TOURNAMENT]   == "TOURN-001"
        assert result[DataKeys.Match.CATEGORY]     == "7/6 sterk"
        assert result[DataKeys.Match.POULE]        == "Groep A"
        assert result[DataKeys.Match.DATE]         == "2026-01-15"
        assert result[DataKeys.Match.TIME]         == "14:30:00"
        assert result[DataKeys.Match.INFO]         == "Regular match"
        assert result[DataKeys.Match.TEAM_1_ID]    == "TEAM-AABBCC"
        assert result[DataKeys.Match.TEAM_2_ID]    == "TEAM-DDEEFF"
        assert result[DataKeys.Match.TEAM_1_SCORE] == 14
        assert result[DataKeys.Match.TEAM_2_SCORE] == 8
        assert result[DataKeys.General.SCRAPED_AT] == "2026-01-10T10:00:00Z"

    def test_no_nested_team_dicts_in_output(self, sample_raw_match):
        """Parsed match must not contain nested team_1/team_2 sub-dicts."""
        result = parse_match(sample_raw_match, "TOURN-001", "TEAM-AA", "TEAM-BB")
        assert "team_1" not in result
        assert "team_2" not in result

    def test_missing_date_time_produces_none(self):
        match = {
            "match_id":   "match_001",
            "category":   "7/6 sterk",
            "poule":      "Groep A",
            "info":       "",
            "scraped_at": "2026-01-10T10:00:00Z",
            "team_1":     {"score": 10},
            "team_2":     {"score": 5},
        }
        result = parse_match(match, "TOURN-001", "TEAM-AA", "TEAM-BB")
        assert result[DataKeys.Match.DATE] is None
        assert result[DataKeys.Match.TIME] is None

    def test_invalid_date_time_produces_none(self):
        match = {
            "match_id":   "match_001",
            "category":   "7/6 sterk",
            "poule":      "Groep A",
            "date":       "not-a-date",
            "time":       "not-a-time",
            "info":       "",
            "scraped_at": "2026-01-10T10:00:00Z",
            "team_1":     {"score": 10},
            "team_2":     {"score": 5},
        }
        result = parse_match(match, "TOURN-001", "TEAM-AA", "TEAM-BB")
        assert result[DataKeys.Match.DATE] is None
        assert result[DataKeys.Match.TIME] is None


# ── ID Resolver ───────────────────────────────────────────────────────────────

class TestLoadSaveIdMap:
    def test_load_existing(self, temp_dirs, sample_id_map):
        path = Path(temp_dirs["input"]) / FileNames.Input.PLAYER_ID_MAP
        path.write_text(json.dumps(sample_id_map), encoding="utf-8")

        assert load_id_map(temp_dirs["input"]) == sample_id_map

    def test_load_missing_returns_empty(self, temp_dirs):
        assert load_id_map(temp_dirs["input"]) == {}

    def test_save_roundtrip(self, temp_dirs, sample_id_map):
        save_id_map(sample_id_map, temp_dirs["input"])
        assert load_id_map(temp_dirs["input"]) == sample_id_map


class TestLoadSavePlayers:
    def test_load_existing(self, temp_dirs, sample_players):
        path = Path(temp_dirs["input"]) / FileNames.Input.PLAYERS
        path.write_text(json.dumps(sample_players), encoding="utf-8")

        assert load_players(temp_dirs["input"]) == sample_players

    def test_load_missing_returns_empty(self, temp_dirs):
        assert load_players(temp_dirs["input"]) == {}

    def test_save_roundtrip(self, temp_dirs, sample_players):
        save_players(sample_players, temp_dirs["input"])
        assert load_players(temp_dirs["input"]) == sample_players


class TestGenerateCanonicalId:
    def test_first_player_is_001(self):
        result = _generate_canonical_id("New Player", {})
        assert result.startswith("PLR-001-")

    def test_increments_from_existing(self, sample_players):
        # sample_players has PLR-001 and PLR-002
        result = _generate_canonical_id("New Player", sample_players)
        assert result.startswith("PLR-003-")

    def test_hash_extension_length(self):
        result = _generate_canonical_id("Test Player", {})
        parts = result.split("-")
        # format: PLR-XXX-HHHHHH
        assert len(parts) == 3
        assert len(parts[2]) == 6

    def test_deterministic_for_same_name(self, sample_players):
        r1 = _generate_canonical_id("Test Player", sample_players)
        r2 = _generate_canonical_id("Test Player", sample_players)
        assert r1 == r2

    def test_different_names_produce_different_ids(self, sample_players):
        r1 = _generate_canonical_id("Player A", sample_players)
        r2 = _generate_canonical_id("Player B", sample_players)
        # Sequential number will be the same, but hash extension must differ
        assert r1 != r2


class TestResolvePlayer:
    def test_known_name_returns_immediately(self, temp_dirs, sample_id_map, sample_players):
        result = resolve_player("Alice Johnson", sample_id_map, sample_players, temp_dirs["input"])
        assert result == "PLR-001-ABC123"

    @patch("consolidation.id_resolver._open_resolution_popup")
    def test_unknown_name_opens_popup(self, mock_popup, temp_dirs, sample_id_map, sample_players):
        mock_popup.return_value = "PLR-003-NEW123"

        result = resolve_player("Unknown Player", sample_id_map, sample_players, temp_dirs["input"])

        assert result == "PLR-003-NEW123"
        mock_popup.assert_called_once_with("Unknown Player", sample_id_map, sample_players)

    @patch("consolidation.id_resolver._open_resolution_popup")
    def test_resolution_persisted_to_id_map(self, mock_popup, temp_dirs, sample_id_map, sample_players):
        mock_popup.return_value = "PLR-003-NEW123"

        resolve_player("Unknown Player", sample_id_map, sample_players, temp_dirs["input"])

        assert sample_id_map["Unknown Player"] == "PLR-003-NEW123"
        # Verify persisted to disk
        saved = load_id_map(temp_dirs["input"])
        assert saved["Unknown Player"] == "PLR-003-NEW123"

    @patch("consolidation.id_resolver._open_resolution_popup")
    def test_popup_returns_unknown_raises(self, mock_popup, temp_dirs, sample_id_map, sample_players):
        mock_popup.return_value = "unknown"

        with pytest.raises(ValueError, match="could not be resolved"):
            resolve_player("Ghost Player", sample_id_map, sample_players, temp_dirs["input"])


# ── Deduplicator ──────────────────────────────────────────────────────────────

class TestExtractPlayersFromMatch:
    @patch("consolidation.deduplicator.resolve_player")
    def test_returns_four_players_in_order(self, mock_resolve, sample_raw_match, sample_players):
        all_players = {
            "PLR-001-ABC123": sample_players["PLR-001-ABC123"],
            "PLR-002-DEF456": sample_players["PLR-002-DEF456"],
            "PLR-003-GHI789": {DataKeys.Player.ID: "PLR-003-GHI789", DataKeys.Player.NAME: "Charlie Brown", DataKeys.Player.GENDER: "male"},
            "PLR-004-JKL012": {DataKeys.Player.ID: "PLR-004-JKL012", DataKeys.Player.NAME: "Diana Prince",  DataKeys.Player.GENDER: "female"},
        }
        mock_resolve.side_effect = ["PLR-001-ABC123", "PLR-002-DEF456", "PLR-003-GHI789", "PLR-004-JKL012"]

        result = extract_players_from_match(sample_raw_match, {}, all_players, "/fake/path")

        assert len(result) == 4
        assert mock_resolve.call_count == 4
        # Order: team_1/p1, team_1/p2, team_2/p1, team_2/p2
        assert result[0][DataKeys.Player.NAME] == "Alice Johnson"
        assert result[1][DataKeys.Player.NAME] == "Bob Smith"
        assert result[2][DataKeys.Player.NAME] == "Charlie Brown"
        assert result[3][DataKeys.Player.NAME] == "Diana Prince"

    @patch("consolidation.deduplicator.resolve_player")
    def test_each_player_dict_contains_id_name_gender(self, mock_resolve, sample_raw_match, sample_players):
        all_players = {
            "PLR-001-ABC123": sample_players["PLR-001-ABC123"],
            "PLR-002-DEF456": sample_players["PLR-002-DEF456"],
            "PLR-003-GHI789": {DataKeys.Player.ID: "PLR-003-GHI789", DataKeys.Player.NAME: "Charlie Brown", DataKeys.Player.GENDER: "male"},
            "PLR-004-JKL012": {DataKeys.Player.ID: "PLR-004-JKL012", DataKeys.Player.NAME: "Diana Prince",  DataKeys.Player.GENDER: "female"},
        }
        mock_resolve.side_effect = ["PLR-001-ABC123", "PLR-002-DEF456", "PLR-003-GHI789", "PLR-004-JKL012"]

        result = extract_players_from_match(sample_raw_match, {}, all_players, "/fake/path")

        for player in result:
            assert DataKeys.Player.ID     in player
            assert DataKeys.Player.NAME   in player
            assert DataKeys.Player.GENDER in player


class TestDeduplicatePlayers:
    def test_no_duplicates_unchanged(self):
        players = [
            {DataKeys.Player.ID: "PLR-001", DataKeys.Player.NAME: "Alice"},
            {DataKeys.Player.ID: "PLR-002", DataKeys.Player.NAME: "Bob"},
        ]
        assert deduplicate_players(players) == players

    def test_removes_duplicates_keeps_first(self):
        players = [
            {DataKeys.Player.ID: "PLR-001", DataKeys.Player.NAME: "Alice"},
            {DataKeys.Player.ID: "PLR-002", DataKeys.Player.NAME: "Bob"},
            {DataKeys.Player.ID: "PLR-001", DataKeys.Player.NAME: "Alice (dupe)"},
        ]
        result = deduplicate_players(players)
        assert len(result) == 2
        # First occurrence kept
        assert result[0][DataKeys.Player.NAME] == "Alice"

    def test_empty_list(self):
        assert deduplicate_players([]) == []


class TestGenerateTeamId:
    def test_format(self):
        result = _generate_team_id("PLR-001-ABC123", "PLR-002-DEF456")
        assert result.startswith("TEAM-")
        # TEAM- + 8 hex chars
        assert len(result) == 13

    def test_order_agnostic(self):
        r1 = _generate_team_id("PLR-001-ABC123", "PLR-002-DEF456")
        r2 = _generate_team_id("PLR-002-DEF456", "PLR-001-ABC123")
        assert r1 == r2

    def test_deterministic(self):
        r1 = _generate_team_id("PLR-001-ABC123", "PLR-002-DEF456")
        r2 = _generate_team_id("PLR-001-ABC123", "PLR-002-DEF456")
        assert r1 == r2

    def test_different_pairs_produce_different_ids(self):
        r1 = _generate_team_id("PLR-001-ABC123", "PLR-002-DEF456")
        r2 = _generate_team_id("PLR-001-ABC123", "PLR-003-GHI789")
        assert r1 != r2


class TestRegisterTeam:
    def test_new_team_added_to_dict(self):
        teams = {}
        team_id = _register_team("PLR-001-ABC123", "PLR-002-DEF456", teams)

        assert team_id in teams
        assert teams[team_id][DataKeys.Team.ID]       == team_id
        assert teams[team_id][DataKeys.Team.PLAYER_1] in {"PLR-001-ABC123", "PLR-002-DEF456"}
        assert teams[team_id][DataKeys.Team.PLAYER_2] in {"PLR-001-ABC123", "PLR-002-DEF456"}

    def test_players_stored_in_sorted_order(self):
        """Player order in the stored record must always be alphabetical."""
        teams = {}
        _register_team("PLR-002-DEF456", "PLR-001-ABC123", teams)
        record = next(iter(teams.values()))
        assert record[DataKeys.Team.PLAYER_1] == "PLR-001-ABC123"
        assert record[DataKeys.Team.PLAYER_2] == "PLR-002-DEF456"

    def test_existing_team_not_duplicated(self):
        teams = {}
        id1 = _register_team("PLR-001-ABC123", "PLR-002-DEF456", teams)
        id2 = _register_team("PLR-001-ABC123", "PLR-002-DEF456", teams)

        assert id1 == id2
        assert len(teams) == 1

    def test_reversed_order_not_duplicated(self):
        """Same pair in reversed order must not create a second record."""
        teams = {}
        id1 = _register_team("PLR-001-ABC123", "PLR-002-DEF456", teams)
        id2 = _register_team("PLR-002-DEF456", "PLR-001-ABC123", teams)

        assert id1 == id2
        assert len(teams) == 1


class TestExtractTeamsFromMatch:
    def test_returns_two_team_ids(self, four_players):
        teams = {}
        t1, t2 = extract_teams_from_match(four_players, teams)

        assert t1.startswith("TEAM-")
        assert t2.startswith("TEAM-")
        assert t1 != t2

    def test_two_teams_registered(self, four_players):
        teams = {}
        extract_teams_from_match(four_players, teams)
        assert len(teams) == 2

    def test_team_compositions_correct(self, four_players):
        teams = {}
        t1, t2 = extract_teams_from_match(four_players, teams)

        assert set([teams[t1][DataKeys.Team.PLAYER_1], teams[t1][DataKeys.Team.PLAYER_2]]) == {"PLR-001-ABC123", "PLR-002-DEF456"}
        assert set([teams[t2][DataKeys.Team.PLAYER_1], teams[t2][DataKeys.Team.PLAYER_2]]) == {"PLR-003-GHI789", "PLR-004-JKL012"}

    def test_same_match_twice_does_not_duplicate_teams(self, four_players):
        """Calling extract_teams_from_match twice with the same players must not grow the dict."""
        teams = {}
        extract_teams_from_match(four_players, teams)
        extract_teams_from_match(four_players, teams)
        assert len(teams) == 2


# ── Run Consolidation ─────────────────────────────────────────────────────────

class TestWriteOutput:
    def test_creates_file_with_correct_content(self, temp_dirs):
        data = [{"id": 1, "name": "Test"}]
        _write_output(data, "test.json", Path(temp_dirs["output"]))

        result = json.loads((Path(temp_dirs["output"]) / "test.json").read_text())
        assert result == data

    def test_creates_output_dir_if_missing(self, temp_dirs):
        new_dir = Path(temp_dirs["output"]) / "nested" / "dir"
        _write_output([{"x": 1}], "out.json", new_dir)
        assert (new_dir / "out.json").exists()


class TestLoadRawPoule:
    def test_loads_list_of_dicts(self, temp_dirs):
        data = [{"match_id": "match_001"}, {"match_id": "match_002"}]
        path = Path(temp_dirs["raw"]) / "poule_a.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        assert _load_raw_poule(path) == data

    def test_empty_file_returns_empty_list(self, temp_dirs):
        path = Path(temp_dirs["raw"]) / "empty.json"
        path.write_text("[]", encoding="utf-8")

        assert _load_raw_poule(path) == []


class TestWalkTournament:
    @patch("pipeline.run_consolidation.load_tournament_metadata")
    @patch("pipeline.run_consolidation.extract_players_from_match")
    @patch("pipeline.run_consolidation.extract_teams_from_match")
    @patch("pipeline.run_consolidation.parse_match")
    def test_returns_tournament_matches_players(
        self, mock_parse, mock_teams, mock_players, mock_meta, temp_dirs
    ):
        mock_meta.return_value    = {DataKeys.Tournament.ID: "TOURN-001"}
        mock_players.return_value = [
            {DataKeys.Player.ID: "PLR-001"}, {DataKeys.Player.ID: "PLR-002"},
            {DataKeys.Player.ID: "PLR-003"}, {DataKeys.Player.ID: "PLR-004"},
        ]
        mock_teams.return_value = ("TEAM-AA", "TEAM-BB")
        mock_parse.return_value = {DataKeys.Match.ID: "match_001"}

        # Build tournament folder structure
        t_path = Path(temp_dirs["raw"]) / "TOURN-001"
        cat    = t_path / "7_6_sterk"
        cat.mkdir(parents=True)
        (cat / "poule_a.json").write_text(json.dumps([{"match_id": "match_001"}]), encoding="utf-8")

        tournament, matches, players = _walk_tournament(
            t_path, {}, {}, {}, temp_dirs["input"]
        )

        assert tournament == {DataKeys.Tournament.ID: "TOURN-001"}
        assert len(matches) == 1
        assert len(players) == 4

    @patch("pipeline.run_consolidation.load_tournament_metadata")
    @patch("pipeline.run_consolidation.extract_players_from_match")
    @patch("pipeline.run_consolidation.extract_teams_from_match")
    @patch("pipeline.run_consolidation.parse_match")
    def test_multiple_categories_and_poules(
        self, mock_parse, mock_teams, mock_players, mock_meta, temp_dirs
    ):
        mock_meta.return_value    = {DataKeys.Tournament.ID: "TOURN-001"}
        mock_players.return_value = [
            {DataKeys.Player.ID: "PLR-001"}, {DataKeys.Player.ID: "PLR-002"},
            {DataKeys.Player.ID: "PLR-003"}, {DataKeys.Player.ID: "PLR-004"},
        ]
        mock_teams.return_value = ("TEAM-AA", "TEAM-BB")
        mock_parse.return_value = {DataKeys.Match.ID: "match_001"}

        t_path = Path(temp_dirs["raw"]) / "TOURN-001"
        for cat in ["cat_a", "cat_b"]:
            d = t_path / cat
            d.mkdir(parents=True)
            for poule in ["poule_a.json", "poule_b.json"]:
                (d / poule).write_text(
                    json.dumps([{"match_id": f"{cat}_{poule}"}]), encoding="utf-8"
                )

        _, matches, _ = _walk_tournament(t_path, {}, {}, {}, temp_dirs["input"])
        # 2 categories × 2 poules × 1 match each
        assert len(matches) == 4

    @patch("pipeline.run_consolidation.load_tournament_metadata")
    def test_missing_metadata_raises(self, mock_meta, temp_dirs):
        mock_meta.side_effect = FileNotFoundError("Missing metadata.json")

        t_path = Path(temp_dirs["raw"]) / "TOURN-001"
        t_path.mkdir()

        with pytest.raises(FileNotFoundError):
            _walk_tournament(t_path, {}, {}, {}, temp_dirs["input"])

    @patch("pipeline.run_consolidation.load_tournament_metadata")
    @patch("pipeline.run_consolidation.extract_players_from_match")
    @patch("pipeline.run_consolidation.extract_teams_from_match")
    @patch("pipeline.run_consolidation.parse_match")
    def test_empty_category_produces_no_matches(
        self, mock_parse, mock_teams, mock_players, mock_meta, temp_dirs
    ):
        mock_meta.return_value = {DataKeys.Tournament.ID: "TOURN-001"}

        t_path = Path(temp_dirs["raw"]) / "TOURN-001"
        (t_path / "empty_cat").mkdir(parents=True)

        _, matches, players = _walk_tournament(t_path, {}, {}, {}, temp_dirs["input"])

        assert matches  == []
        assert players  == []
        mock_parse.assert_not_called()


class TestConsolidate:
    @patch("pipeline.run_consolidation._walk_tournament")
    @patch("pipeline.run_consolidation.deduplicate_players")
    @patch("pipeline.run_consolidation.load_id_map")
    @patch("pipeline.run_consolidation.load_players")
    @patch("pipeline.run_consolidation.save_id_map")
    @patch("pipeline.run_consolidation.save_players")
    @patch("pipeline.run_consolidation._write_output")
    def test_writes_four_output_files(
        self, mock_write, mock_save_players, mock_save_id_map,
        mock_load_players, mock_load_id_map, mock_dedup, mock_walk, temp_dirs
    ):
        mock_load_id_map.return_value    = {}
        mock_load_players.return_value   = {}
        mock_walk.return_value           = ({"id": "TOURN-001"}, [{"id": "match_001"}], [{"id": "PLR-001"}])
        mock_dedup.return_value          = [{"id": "PLR-001"}]

        (Path(temp_dirs["raw"]) / "TOURN-001").mkdir()

        consolidate(temp_dirs["raw"], temp_dirs["output"], temp_dirs["input"])

        assert mock_write.call_count == 4  # tournaments, matches, players, teams

    @patch("pipeline.run_consolidation._walk_tournament")
    @patch("pipeline.run_consolidation.deduplicate_players")
    @patch("pipeline.run_consolidation.load_id_map")
    @patch("pipeline.run_consolidation.load_players")
    @patch("pipeline.run_consolidation.save_id_map")
    @patch("pipeline.run_consolidation.save_players")
    @patch("pipeline.run_consolidation._write_output")
    def test_skips_tournament_on_missing_metadata(
        self, mock_write, mock_save_players, mock_save_id_map,
        mock_load_players, mock_load_id_map, mock_dedup, mock_walk, temp_dirs
    ):
        """A FileNotFoundError from _walk_tournament must skip the tournament, not crash."""
        mock_load_id_map.return_value  = {}
        mock_load_players.return_value = {}
        mock_walk.side_effect          = FileNotFoundError("No metadata")
        mock_dedup.return_value        = []

        (Path(temp_dirs["raw"]) / "TOURN-001").mkdir()

        consolidate(temp_dirs["raw"], temp_dirs["output"], temp_dirs["input"])

        # Should still write four empty output files
        assert mock_write.call_count == 4

    def test_missing_raw_path_raises(self, temp_dirs):
        with pytest.raises(FileNotFoundError, match="Raw data path does not exist"):
            consolidate("/non/existent/path", temp_dirs["output"], temp_dirs["input"])

    @patch("pipeline.run_consolidation._walk_tournament")
    @patch("pipeline.run_consolidation.deduplicate_players")
    @patch("pipeline.run_consolidation.load_id_map")
    @patch("pipeline.run_consolidation.load_players")
    @patch("pipeline.run_consolidation.save_id_map")
    @patch("pipeline.run_consolidation.save_players")
    @patch("pipeline.run_consolidation._write_output")
    def test_id_map_and_players_saved_once(
        self, mock_write, mock_save_players, mock_save_id_map,
        mock_load_players, mock_load_id_map, mock_dedup, mock_walk, temp_dirs
    ):
        """id_map and players must be saved exactly once at the end."""
        mock_load_id_map.return_value  = {}
        mock_load_players.return_value = {}
        mock_walk.return_value         = ({}, [], [])
        mock_dedup.return_value        = []

        (Path(temp_dirs["raw"]) / "TOURN-001").mkdir()

        consolidate(temp_dirs["raw"], temp_dirs["output"], temp_dirs["input"])

        mock_save_id_map.assert_called_once()
        mock_save_players.assert_called_once()

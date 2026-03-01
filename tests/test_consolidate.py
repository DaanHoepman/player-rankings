import json
import shutil
import sys
from pathlib import Path

# ensure the "src" package is importable when running tests from the repo root
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

def _fixture_path(*parts: str) -> Path:
    """Helper to build a path relative to the fixtures directory."""
    return Path(__file__).parent / "fixtures" / Path("".join(parts))


import pytest

from src.constants import DataKeys
from src.pipeline.consolidate import (
    _write_output,
    _load_raw_poule,
    _substitute_canonical_ids,
    _walk_tournament,
    consolidate,
)
from src.pipeline._deduplicator import deduplicate_players
from src.pipeline._id_resolver import load_id_map, load_players


# ---------- basic utility tests ----------

def test_write_output_creates_file(tmp_path, capsys):
    data = [{"foo": "bar"}, {"baz": 123}]
    _write_output(data, "out.json", tmp_path)
    out_file = tmp_path / "out.json"
    assert out_file.exists(), "output file should be written"

    with open(out_file, encoding="utf-8") as f:
        assert json.load(f) == data

    captured = capsys.readouterr()
    assert "Wrote 2 records to" in captured.out


def test_load_raw_poule_valid_empty_and_malformed():
    # valid file from fixtures
    valid = Path(__file__).parent / "fixtures" / "raw" / "TOURN-001" / "76_sterk" / "r1_groep_a.json"
    records = _load_raw_poule(valid)
    assert isinstance(records, list) and len(records) == 5

    empty = Path(__file__).parent / "fixtures" / "raw" / "TOURN-001" / "76_sterk" / "r2_groep_empty.json"
    assert _load_raw_poule(empty) == []

    broken = Path(__file__).parent / "fixtures" / "raw" / "TOURN-001" / "76_sterk" / "r3_groep_malformed.json.broken"
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _load_raw_poule(broken)


def test_substitute_canonical_ids_does_replacement():
    parsed = {
        DataKeys.Match.TEAM_1: {DataKeys.Team.PLAYER_1: None, DataKeys.Team.PLAYER_2: None},
        DataKeys.Match.TEAM_2: {DataKeys.Team.PLAYER_1: None, DataKeys.Team.PLAYER_2: None},
    }
    # raw_match values are dictionaries with at least "name" key
    raw = {
        DataKeys.Match.TEAM_1: {
            DataKeys.Team.PLAYER_1: {"id": 1, "name": "Alice"},
            DataKeys.Team.PLAYER_2: {"id": 2, "name": "Bob"},
        },
        DataKeys.Match.TEAM_2: {
            DataKeys.Team.PLAYER_1: {"id": 3, "name": "Charlie"},
            DataKeys.Team.PLAYER_2: {"id": 4, "name": "Dana"},
        },
    }
    mapping = {"Alice": "ID1", "Bob": "ID2", "Charlie": "ID3"}

    result = _substitute_canonical_ids(parsed, raw, mapping)
    # original parsed object should not be mutated
    assert parsed[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_1] is None

    assert result[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_1] == "ID1"
    assert result[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_2] == "ID2"
    assert result[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_1] == "ID3"
    assert result[DataKeys.Match.TEAM_2][DataKeys.Team.PLAYER_2] is None


def test_deduplicate_players_collapses_duplicates():
    players = [
        {DataKeys.Player.ID: "A", DataKeys.Player.NAME: "x"},
        {DataKeys.Player.ID: "B", DataKeys.Player.NAME: "y"},
        {DataKeys.Player.ID: "A", DataKeys.Player.NAME: "x"},
    ]
    unique = deduplicate_players(players)
    assert len(unique) == 2
    ids = {p[DataKeys.Player.ID] for p in unique}
    assert ids == {"A", "B"}


# ---------- _walk_tournament tests ----------

def _clone_tournament(src_folder: Path, dest_root: Path, keep_files=None):
    """Copy a subset of files from the fixture tournament to a temporary location.

    ``keep_files`` is a list of substring patterns that will be kept; all other
    poule json files are deleted.  The tournament's metadata.json is always
    preserved since it is required for parsing.
    """
    dst = dest_root / src_folder.name
    shutil.copytree(src_folder, dst)
    if keep_files is not None:
        for p in dst.rglob("*.json"):
            # always keep the metadata file
            if p.name == "metadata.json":
                continue
            if not any(pattern in p.name for pattern in keep_files):
                p.unlink()
    return dst


def test_walk_tournament_success(tmp_path):
    """Full walk of a cleaned replica of TOURN-001 should return the expected
    counts and substitute canonical ids correctly."""
    src = Path(__file__).parent / "fixtures" / "raw" / "TOURN-001"
    # keep only the good poule files and the second category
    clean = _clone_tournament(src, tmp_path, keep_files=["r1_groep_a", "r1_groep_b", "r1_groep_a.json", "r1_groep_a.json"])
    # also remove the three explicitly bad files if they were copied
    for bad in ("r3_groep_malformed.json.broken", "r4_missing_match_id.json.bad", "r5_missing_score.json.bad"):
        for p in clean.rglob(bad):
            p.unlink()

    id_map = load_id_map(str(Path(__file__).parent / "fixtures" / "input"))
    players = load_players(str(Path(__file__).parent / "fixtures" / "input"))

    tournament, matches, raw_players = _walk_tournament(
        tournament_path=clean,
        id_map=id_map,
        players=players,
        input_path=str(Path(__file__).parent / "fixtures" / "input"),
    )

    assert tournament[DataKeys.Tournament.ID] == "TOURN-001"
    # two poules contained data: 5 + 1 matches; plus one from the second category
    assert len(matches) == 7
    assert len(raw_players) == 7 * 4

    # verify substitution of canonical id for first match
    first = matches[0]
    assert first[DataKeys.Match.TEAM_1][DataKeys.Team.PLAYER_1] == "PLR-001"


def test_walk_tournament_raises_on_missing_metadata(tmp_path):
    # folder without metadata should cause FileNotFoundError
    bad = tmp_path / "no_meta"
    (bad / "76_sterk").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        _walk_tournament(bad, {}, {}, "unused")


def test_walk_tournament_raises_for_bad_match(tmp_path):
    # create a tournament with a single poule file containing a record missing match_id
    t = tmp_path / "TOURN-BAD"
    t.mkdir()
    # copy minimal metadata
    src_meta = Path(__file__).parent / "fixtures" / "raw" / "TOURN-001" / "metadata.json"
    shutil.copy(src_meta, t / "metadata.json")
    cat = t / "cat"
    cat.mkdir()
    badmatch = [
        {
            # intentionally leave out "match_id" key
            "date": "2025-01-01",
            DataKeys.Match.TEAM_1: {DataKeys.Team.PLAYER_1: {"id": 1, "name": "Player Alpha"}, DataKeys.Team.PLAYER_2: {"id": 2, "name": "Player Bravo"}, "score": 0},
            DataKeys.Match.TEAM_2: {DataKeys.Team.PLAYER_1: {"id": 3, "name": "Player Charlie"}, DataKeys.Team.PLAYER_2: {"id": 4, "name": "Player Delta"}, "score": 0},
        }
    ]
    with open(cat / "poule.json", "w", encoding="utf-8") as f:
        json.dump(badmatch, f)

    id_map = load_id_map(str(Path(__file__).parent / "fixtures" / "input"))
    players = load_players(str(Path(__file__).parent / "fixtures" / "input"))

    with pytest.raises(KeyError):
        _walk_tournament(t, id_map, players, str(Path(__file__).parent / "fixtures" / "input"))


def test_walk_tournament_handles_empty_category(tmp_path):
    # build a tournament with metadata and an empty category folder
    t = tmp_path / "TOURN-EMPTYCAT"
    t.mkdir()
    shutil.copy(
        Path(__file__).parent / "fixtures" / "raw" / "TOURN-001" / "metadata.json",
        t / "metadata.json",
    )
    (t / "emptycat").mkdir()

    id_map = {}
    players = {}
    tournament, matches, raw_players = _walk_tournament(t, id_map, players, "unused")
    assert tournament[DataKeys.Tournament.ID] == "TOURN-EMPTYCAT"
    assert matches == []
    assert raw_players == []


# ---------- consolidate() integration tests ----------

def test_consolidate_raises_if_raw_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        consolidate(str(tmp_path / "doesnotexist"), str(tmp_path / "out"), str(tmp_path / "in"))


def test_consolidate_complete_run(tmp_path, capsys):
    # make a temporary copy of the fixtures and remove bad files
    raw_src = Path(__file__).parent / "fixtures" / "raw"
    raw_copy = tmp_path / "raw"
    shutil.copytree(raw_src, raw_copy)
    # the fixture already contains a TOURN-NO-META folder; we'll keep that
    # remove any tournaments other than TOURN-001 and TOURN-NO-META so our
    # assertions are deterministic
    for entry in list(raw_copy.iterdir()):
        if entry.is_dir() and entry.name not in ("TOURN-001", "TOURN-NO-META"):
            shutil.rmtree(entry)
    # remove all problematic files from the copy (they live under TOURN-001)
    for bad in ("r3_groep_malformed.json.broken", "r4_missing_match_id.json.bad", "r5_missing_score.json.bad"):
        for p in raw_copy.rglob(bad):
            p.unlink()

    input_copy = tmp_path / "input"
    shutil.copytree(Path(__file__).parent / "fixtures" / "input", input_copy)

    out = tmp_path / "out"
    consolidate(str(raw_copy), str(out), str(input_copy))

    captured = capsys.readouterr().out
    assert "Skipping TOURN-NO-META" in captured

    # read output files
    tournaments = json.load(open(out / "tournaments.json", encoding="utf-8"))
    matches = json.load(open(out / "matches.json", encoding="utf-8"))
    players_out = json.load(open(out / "players.json", encoding="utf-8"))

    assert len(tournaments) == 1
    assert tournaments[0][DataKeys.Tournament.ID] == "TOURN-001"

    assert len(matches) == 7
    # unique players should be 13 according to the fixture data
    assert len(players_out) == 13

    # confirm that id_map and players file were written back
    saved_id_map = load_id_map(str(input_copy))
    saved_players = load_players(str(input_copy))
    assert saved_id_map
    assert saved_players


def test_consolidate_fails_on_malformed_file(tmp_path):
    # create a raw directory containing one malformed poule file
    raw = tmp_path / "raw_bad"
    raw.mkdir()
    t = raw / "T1"
    t.mkdir()
    # copy metadata over
    shutil.copy(
        Path(__file__).parent / "fixtures" / "raw" / "TOURN-001" / "metadata.json",
        t / "metadata.json",
    )
    cat = t / "cat"
    cat.mkdir()
    with open(cat / "broken.json", "w", encoding="utf-8") as f:
        f.write("not a json")

    input_copy = tmp_path / "input"
    shutil.copytree(Path(__file__).parent / "fixtures" / "input", input_copy)
    out = tmp_path / "out"

    with pytest.raises(json.JSONDecodeError):
        consolidate(str(raw), str(out), str(input_copy))

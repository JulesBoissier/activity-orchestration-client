"""Readable process names on the dashboard."""

import json

from src.app.display_names import display_name, load_display_names


def test_lookup_ignores_case():
    """``Code.exe``, ``code.exe`` and ``CODE.EXE`` all map to the same readable name.

    Why: Windows file names are case-insensitive and the watchdog reports the name as the
    process was launched. The old lookup lowercased the process name but not the file's
    keys, so entries like ``sourceTree.exe`` and ``7zFM.exe`` never matched.
    """
    names = load_display_names()

    assert display_name("SourceTree.exe", names) == "Sourcetree"
    assert display_name("7zFM.exe", names) == "7-Zip"
    assert display_name("CODE.EXE", names) == display_name("code.exe", names)


def test_mixed_case_keys_in_a_custom_file_still_match(tmp_path):
    """Keys are normalised when the file is loaded, whatever case they're written in.

    Why: the mapping file is edited by hand. A new entry shouldn't silently fail because
    of its capitalisation.
    """
    path = tmp_path / "names.json"
    path.write_text(json.dumps({"MyApp.EXE": "My App"}))

    assert display_name("myapp.exe", load_display_names(path)) == "My App"


def test_unknown_or_empty_names_pass_through():
    """Processes without an entry keep their own name; gap rows stay empty.

    Why: the dashboard must show every app, not only mapped ones, and gap rows must stay
    recognisable as gaps.
    """
    names = load_display_names()

    assert display_name("obscure-tool.exe", names) == "obscure-tool.exe"
    assert display_name("", names) == ""
    assert display_name(None, names) is None


def test_unreadable_file_gives_no_names(tmp_path):
    """A missing or malformed mapping file yields an empty mapping instead of an error.

    Why: display names are cosmetic; a broken file mustn't take the dashboard down.
    """
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")

    assert load_display_names(tmp_path / "missing.json") == {}
    assert load_display_names(bad) == {}

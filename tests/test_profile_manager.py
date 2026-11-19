"""Behaviour of ``ProfileManager``'s startup prompt."""

from unittest.mock import MagicMock

from src.backend.profile_manager import ProfileManager


def manager(load_statuses):
    vision = MagicMock()
    vision.list_profiles.return_value = {
        "profiles": [{"id": 1, "profile_name": "desk", "updated_at": "2026-11-19"}]
    }
    vision.load_profile.side_effect = load_statuses
    pm = ProfileManager(vision, MagicMock(), monitor=MagicMock())
    pm.create_new_profile = MagicMock()
    return pm, vision


def test_unknown_profile_id_asks_again(monkeypatch):
    """An id the vision service doesn't know is reported and the user is asked again.

    Why: the vision service answers 404 for unknown ids and keeps its calibration. Before,
    a typo silently started tracking with no usable calibration.
    """
    answers = iter(["7", "1"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    pm, vision = manager([404, 200])

    pm.select_or_create_profile()

    assert [c.args[0] for c in vision.load_profile.call_args_list] == ["7", "1"]
    pm.create_new_profile.assert_not_called()


def test_empty_answer_creates_a_profile(monkeypatch):
    """Pressing enter at the prompt starts a new calibration.

    Why: first-time users have no profile to pick.
    """
    monkeypatch.setattr("builtins.input", lambda *a: "")
    pm, vision = manager([])

    pm.select_or_create_profile()

    pm.create_new_profile.assert_called_once()
    vision.load_profile.assert_not_called()

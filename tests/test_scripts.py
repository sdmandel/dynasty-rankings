"""Focused tests for public-data build helpers."""
from __future__ import annotations

from concurrent.futures import Future
import sys
from types import ModuleType

import pytest

try:
    import src.shared.utils  # noqa: F401
except ModuleNotFoundError:
    src_module = ModuleType("src")
    shared_module = ModuleType("src.shared")
    utils_module = ModuleType("src.shared.utils")
    utils_module.normalize_name = lambda value: value.casefold()
    sys.modules.update({
        "src": src_module,
        "src.shared": shared_module,
        "src.shared.utils": utils_module,
    })

from scripts import fetch_season_stats, normalize_team_names


def test_team_name_normalization_only_replaces_exact_values() -> None:
    mapping = {"Rod Beck": "Rollie Fingers"}
    payload = {
        "team": "Rod Beck",
        "summary": "Rod Beck moved into first place.",
    }

    assert normalize_team_names.normalize(payload, mapping) == {
        "team": "Rollie Fingers",
        "summary": "Rod Beck moved into first place.",
    }


def test_team_name_normalization_rejects_key_collisions() -> None:
    with pytest.raises(ValueError, match="overwrite key"):
        normalize_team_names.normalize(
            {"Rod Beck": 1, "Rollie Fingers": 2},
            {"Rod Beck": "Rollie Fingers"},
        )


def test_qs_build_rejects_excessive_boxscore_failures(monkeypatch) -> None:
    game_pks = list(range(10))
    monkeypatch.setattr(fetch_season_stats, "_fetch_completed_game_pks", lambda season: game_pks)

    def failed_future(game_pk: int) -> Future:
        future = Future()
        future.set_result(([], "request failed"))
        return future

    class ImmediatePool:
        def __init__(self, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            pass

        def submit(self, func, game_pk: int) -> Future:
            return failed_future(game_pk)

    monkeypatch.setattr(fetch_season_stats, "ThreadPoolExecutor", ImmediatePool)

    with pytest.raises(RuntimeError, match="refusing to publish partial data"):
        fetch_season_stats._compute_qs(2026)

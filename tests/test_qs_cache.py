import datetime
import json

from scripts import fetch_season_stats as stats


def test_successful_boxscores_reused_and_expired(monkeypatch, tmp_path):
    cache = tmp_path / "qs.json"
    monkeypatch.setattr(stats, "_fetch_completed_game_pks", lambda season: [1, 2])
    calls = []
    def boxscore(pk):
        calls.append(pk)
        return [("pitcher", True)], None
    monkeypatch.setattr(stats, "_boxscore_qs", boxscore)
    assert stats._compute_qs(2026, cache) == {"pitcher": 2}
    assert stats._compute_qs(2026, cache) == {"pitcher": 2}
    assert sorted(calls) == [1, 2]
    payload = json.loads(cache.read_text())
    payload["games"]["1"]["fetched"] = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    cache.write_text(json.dumps(payload))
    assert stats._compute_qs(2026, cache) == {"pitcher": 2}
    assert len(calls) == 3 and calls[-1] == 1


def test_failed_boxscore_is_not_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(stats, "_fetch_completed_game_pks", lambda season: [1])
    monkeypatch.setattr(stats, "_boxscore_qs", lambda pk: ([], "unavailable"))
    path = tmp_path / "cache.json"
    stats._compute_qs(2026, path)
    assert json.loads(path.read_text())["games"] == {}

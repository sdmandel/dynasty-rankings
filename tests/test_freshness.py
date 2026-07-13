"""Freshness and source-status behavior for generated dashboards."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_freshness_helper_has_safe_status_and_date_semantics() -> None:
    js = _read(ROOT / "assets" / "freshness.js")
    for status in ("current", "delayed", "stale", "archived", "unknown"):
        assert f"{status}:" in js
    assert "DATE_ONLY" in js
    assert "timeZoneName: 'short'" in js
    assert "time unavailable" in js
    assert "Freshness unknown" in js


def test_live_data_pages_render_shared_freshness_component() -> None:
    expectations = {
        "standings.html": "Fantrax",
        "transactions.html": "Fantrax",
        "prospects.html": "Oracle rankings and MLB Stats API",
        "closers.html": "MLB Stats API, FantasyPros and FanGraphs",
    }
    for filename, source in expectations.items():
        html = _read(ROOT / filename)
        assert 'id="freshnessEl"' in html
        assert 'src="assets/freshness.js"' in html
        assert "SiteFreshness.render('#freshnessEl'" in html
        assert f"source: '{source}'" in html


def test_live_data_pages_do_not_promise_unverified_cadences() -> None:
    standings = _read(ROOT / "standings.html")
    transactions = _read(ROOT / "transactions.html")
    closers = _read(ROOT / "closers.html")
    assert "Live roto standings" not in standings
    assert "Updated hourly" not in standings
    assert "Updated every 6 hours" not in transactions
    assert "Current save leaders" not in closers

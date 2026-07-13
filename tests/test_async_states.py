from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def page(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_feed_exposes_accessible_async_states_and_retry() -> None:
    html = page("feed.html")
    assert 'id="loadingMsg" class="state-msg" role="status" aria-live="polite"' in html
    assert "function loadFeed()" in html
    assert "status.setAttribute('role','alert')" in html
    assert 'type="button" onclick="loadFeed()">Retry loading feed</button>' in html
    assert "No events match this filter." in html


def test_rivalries_exposes_accessible_async_states_and_retry() -> None:
    html = page("rivalries.html")
    assert 'id="loadingMsg" class="state-msg" role="status" aria-live="polite"' in html
    assert "function loadRivalries()" in html
    assert "status.setAttribute('role','alert')" in html
    assert 'type="button" onclick="loadRivalries()">Retry loading rivalries</button>' in html
    assert "No team rivalry matchups are available in this snapshot." in html

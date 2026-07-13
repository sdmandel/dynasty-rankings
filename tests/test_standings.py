"""Standings table accessibility and responsive behavior."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html() -> str:
    return (ROOT / "standings.html").read_text(encoding="utf-8")


def test_category_sort_headers_are_keyboard_buttons_with_aria_sort() -> None:
    html = _html()

    assert "button.type = 'button'" in html
    assert "button.className = 'sort-button'" in html
    assert "th.setAttribute('aria-sort', isActive ? direction : 'none')" in html
    assert "button.addEventListener('click'" in html
    assert ".sort-button:focus-visible" in html


def test_category_table_identifies_roto_points_and_scroll_region() -> None:
    html = _html()

    assert "Values are roto points, not raw stats." in html
    assert "Roto points awarded in each scoring category." in html
    assert 'role="region" aria-label="Category roto points standings" tabindex="0"' in html
    assert '<caption class="table-caption">Overall standings ranked by total roto points.</caption>' in html
    assert '<th scope="row" class="team-col">' in html


def test_category_table_keeps_headers_and_team_column_visible() -> None:
    html = _html()

    assert ".cat-table thead th {\n  position: sticky;" in html
    assert ".cat-table tbody th.team-col {\n  position: sticky;" in html
    assert "overflow-x: auto" in html


def test_standings_team_links_preserve_roster_depth_deep_link() -> None:
    html = _html()

    assert 'href="${rosterDepthHref(t.team)}"' in html
    assert "return `roster_depth.html?team=${encodeURIComponent(slugifyTeam(teamName))}`" in html


def test_standings_freshness_stays_data_driven() -> None:
    html = _html()

    assert "timestamp: data.generated_at || data.generated" in html
    assert "source: 'Fantrax'" in html

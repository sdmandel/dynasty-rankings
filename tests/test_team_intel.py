from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "team_intel.html").read_text()


def test_team_intel_has_shareable_mode_navigation():
    assert 'aria-label="Team Intel sections"' in HTML
    for section_id in ("overview", "contention", "projection", "trade-strategy"):
        assert f'href="#{section_id}"' in HTML
        assert f'id="{section_id}"' in HTML


def test_team_intel_modes_use_section_headings():
    assert HTML.count('<section class="intel-mode"') == 4
    assert 'aria-labelledby="overview-heading"' in HTML
    assert '<h2 id="contention-heading">' in HTML
    assert '<h2 id="projection-heading">' in HTML
    assert '<h2 id="trade-heading">' in HTML


def test_chart_tooltips_support_focus_and_touch():
    assert 'role="tooltip" aria-hidden="true"' in HTML
    assert "addEventListener('focus'," in HTML
    assert "addEventListener('blur'," in HTML
    assert "isTouchInspection()" in HTML
    assert "row.tabIndex = 0" in HTML
    assert "aria-describedby" in HTML


def test_mode_navigation_tracks_the_hash():
    assert "function syncModeNavigation()" in HTML
    assert "window.addEventListener('hashchange', syncModeNavigation)" in HTML

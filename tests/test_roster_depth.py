"""Responsive and accessible behavior for the roster-depth page and generator."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _html() -> str:
    return (ROOT / "roster_depth.html").read_text(encoding="utf-8")


def test_roster_depth_has_mobile_team_first_view() -> None:
    html = _html()
    assert 'id="mobileDepth"' in html
    assert "const buildMobileDepth = () =>" in html
    assert "details.className = 'mobile-team';" in html
    assert ".sticky-bar-wrap, .table-wrap { display: none; }" in html
    assert ".mobile-depth { display: block; }" in html


def test_roster_depth_player_modal_is_keyboard_and_touch_accessible() -> None:
    html = _html()
    assert "makeButton(pill, position, team)" in html
    assert "openPlayer(pill.dataset.playerKey, true, pill)" in html
    assert "document.body.style.overflow = 'hidden';" in html
    assert "event.key === 'Tab'" in html
    assert "modalTrigger.focus()" in html
    assert "event.key === 'Escape'" in html


def test_roster_depth_freshness_is_not_stale_week_nine_copy() -> None:
    html = _html()
    assert "Updated July 12, 2026" in html
    assert "exact time unavailable" in html
    assert "Week 9" not in html


def test_roster_depth_generator_keeps_mobile_and_modal_enhancements() -> None:
    generator = (ROOT.parent / "scripts" / "update_depth_chart.py").read_text(encoding="utf-8")
    assert 'id="mobileDepth"' in generator
    assert "const buildMobileDepth = () =>" in generator
    assert "makeButton(pill, position, team)" in generator
    assert "openPlayer(pill.dataset.playerKey, true, pill)" in generator
    assert "modalTrigger.focus()" in generator
    assert "Updated {date_str}" in generator

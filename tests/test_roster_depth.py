"""Responsive and accessible behavior for the roster-depth page and generator."""
from pathlib import Path
from datetime import datetime
import re

import pytest

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
    match = re.search(r"Updated ([A-Z][a-z]+ \d{1,2}, \d{4})", html)
    assert match
    assert datetime.strptime(match[1], "%B %d, %Y") >= datetime(2026, 7, 12)
    assert "exact time unavailable" in html
    assert "Week 9" not in html


def test_roster_depth_generator_keeps_mobile_and_modal_enhancements() -> None:
    generator_path = ROOT.parent / "scripts" / "update_depth_chart.py"
    if not generator_path.exists():
        pytest.skip("upstream bot generator is not present in the standalone site checkout")
    generator = generator_path.read_text(encoding="utf-8")
    assert 'id="mobileDepth"' in generator
    assert "const buildMobileDepth = () =>" in generator
    assert "makeButton(pill, position, team)" in generator
    assert "openPlayer(pill.dataset.playerKey, true, pill)" in generator
    assert "modalTrigger.focus()" in generator
    assert "Updated {date_str}" in generator

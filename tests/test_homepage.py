"""Homepage hierarchy and progressive-enhancement regressions."""
from pathlib import Path

from scripts.build_home_preview import update_index_fallback


ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "index.html").read_text(encoding="utf-8")


def test_homepage_prioritizes_repeat_visit_tasks() -> None:
    headings = [
        "The Standings",
        "Latest Around the League",
        "Strategic Tools",
        "League Reference",
    ]
    positions = [PAGE.index(f'<div class="section-label">{heading}</div>') for heading in headings]
    assert positions == sorted(positions)


def test_homepage_standings_freshness_is_truthful_and_data_driven() -> None:
    assert ">Live Standings<" not in PAGE
    assert '<script src="assets/freshness.js"></script>' in PAGE
    assert 'id="standingsFreshness"' in PAGE
    assert "SiteFreshness.render('#standingsFreshness'" in PAGE
    assert "generatedAt: data.generated_at" in PAGE
    assert "source: 'Fantrax standings snapshot'" in PAGE
    assert "Freshness unknown" in PAGE


def test_homepage_cards_are_links_with_visible_keyboard_focus() -> None:
    for route in (
        "week15_power_rankings.html",
        "transactions.html",
        "team_intel.html",
        "roster_depth.html",
        "prospects.html",
        "closers.html",
        "rules.html",
        "franchise_history.html",
    ):
        assert f'<a href="{route}"' in PAGE or f'<a class="header-link" href="{route}"' in PAGE
    assert ".card:focus-visible" in PAGE
    assert ".tool-tile:focus-visible" in PAGE
    assert "outline: 3px solid var(--gold)" in PAGE


def test_homepage_keeps_generator_fallback_anchor() -> None:
    assert PAGE.count('<div class="lb-list" id="leaderboardList">') == 1
    assert PAGE.index('<div class="lb-list" id="leaderboardList">') < PAGE.index(
        '<div class="standings-link-wrap">'
    )


def test_homepage_generator_can_refresh_reordered_fallback(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(PAGE, encoding="utf-8")
    preview = {
        "leaderboard": [
            {"rank": 1, "team": "Test Team", "total_pts": 99, "pts_change": 1.5}
        ]
    }

    update_index_fallback(preview, site_root=tmp_path)

    updated = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<div class="lb-team">Test Team</div>' in updated
    assert '<div class="lb-change up">+1.5</div>' in updated
    assert '<div class="section-label">Latest Around the League</div>' in updated

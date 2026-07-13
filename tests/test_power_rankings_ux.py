from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_FILES = (
    ROOT / "templates" / "power_rankings_template.html",
    ROOT / "week15_power_rankings.html",
)


def _html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_current_article_and_template_put_rankings_before_secondary_content():
    for path in ARTICLE_FILES:
        html = _html(path)
        rankings = html.index('<main class="rankings" id="rankings">')
        league_desk = html.index('<section class="post-rankings" id="league-desk"')
        methodology = html.index('<section class="footnote" id="methodology"')
        assert rankings < league_desk < methodology, path


def test_article_jump_links_have_matching_section_targets():
    for path in ARTICLE_FILES:
        html = _html(path)
        assert '<nav class="article-jumps" aria-label="On this page">' in html, path
        targets = ["rankings", "player-key", "league-desk", "methodology"]
        positions = [html.index(f'href="#{target}"') for target in targets]
        assert positions == sorted(positions), path
        assert all(f'id="{target}"' in html for target in targets), path


def test_current_issue_player_references_are_accessible_links():
    html = _html(ROOT / "week15_power_rankings.html")
    assert '<a class="player-pill' in html
    assert 'href="dynasty_rankings.html?player=' in html
    assert 'aria-label="' in html


def test_rankings_styles_expose_link_focus_and_hover_states():
    css = (ROOT / "assets" / "power-rankings.css").read_text(encoding="utf-8")

    assert ".key-players a.player-pill:focus-visible" in css
    assert ".key-players a.player-pill:hover" in css
    assert "outline: 2px solid var(--gold-500)" in css

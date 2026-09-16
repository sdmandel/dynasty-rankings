from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_ARTICLE = max(
    ROOT.glob("week*_power_rankings.html"),
    key=lambda path: int(path.stem.split("_")[0].removeprefix("week")),
)
ARTICLE_FILES = (ROOT / "templates" / "power_rankings_template.html",)


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
    html = _html(CURRENT_ARTICLE)
    assert '<a class="player-pill' in html
    assert 'href="dynasty_rankings.html?player=' in html
    assert 'aria-label="' in html


def test_rankings_styles_expose_link_focus_and_hover_states():
    css = (ROOT / "assets" / "power-rankings.css").read_text(encoding="utf-8")

    assert ".key-players a.player-pill:focus-visible" in css
    assert ".key-players a.player-pill:hover" in css
    assert "outline: 2px solid var(--gold-500)" in css


def test_current_and_future_articles_have_no_process_notes_or_rank_comparisons():
    import re
    from html import unescape
    for path in ROOT.glob("week*_power_rankings.html"):
        if int(path.stem.split("_")[0].removeprefix("week")) < 24:
            continue  # Preserve historical issues; enforce policy from Week 24 onward.
        html = _html(path)
        assert not re.search(r'badge-(?:up|down|last|new)|badge--last', html), path
        text = unescape(re.sub(r"<[^>]*>", " ", html))
        text = " ".join(text.split())
        forbidden = (
            r"\b(?:frozen|snapshot|pipeline|scaffolding|drafting|methodology)\b",
            r"\b(?:source data|data sources|rank order|previous published issue)\b",
            r"\b(?:last|previous|prior) (?:week(?:’s|'s)?|issue(?:’s|'s)?).{0,35}(?:rank|#)",
            r"\b(?:rank(?:ed|ing|ings)?|#\d+).{0,35}(?:last|previous|prior) (?:week|issue)",
            r"\b(?:up|down|rose|fell|climbed|dropped|jumped|gained|lost) (?:by )?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) (?:spots?|places?|ranks?)\b",
            r"\b(?:week.over.week|rank(?:ing)? (?:movement|change)|movement compares)\b",
            r"\b(?:season results|recent form|active.roster outlook|season history)\s+\d+%",
        )
        assert not any(re.search(pattern, text, re.I) for pattern in forbidden), path

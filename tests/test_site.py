"""Static site smoke tests for the powerrankings GH Pages site."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
HTML_FILES = sorted(ROOT.glob("*.html"))
META_HTML_FILES = [p for p in HTML_FILES if p.name != "404.html"]
SHELL_HTML_FILES = HTML_FILES
SHELL_CSS_HTML_FILES = [p for p in HTML_FILES if p.name not in {"index.html", "404.html"}]
REQUIRED_META = {"og:title", "og:image"}
FEEDBACK_REPO = "sdmandel/dynasty-rankings"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages-on-release.yml"


class StrictHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_pages_deploy_triggers_on_generated_public_payloads() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    for path in (
        "data/standings.json",
        "data/transactions.json",
        "data/trade_block.json",
        "data/franchises.json",
        "data/home_preview.json",
        "data/league_intelligence.json",
        "data/managers.json",
        "data/oracle_public.json",
        "data/rivalries.json",
        "index.html",
    ):
        assert f'- "{path}"' in workflow, f"Pages deploy workflow must include {path}"


@pytest.mark.parametrize("html_file", HTML_FILES, ids=lambda p: p.name)
def test_html_parses(html_file: Path) -> None:
    parser = StrictHTMLParser()
    parser.feed(_read(html_file))
    parser.close()
    assert not parser.errors, f"parse errors: {parser.errors}"


@pytest.mark.parametrize("html_file", META_HTML_FILES, ids=lambda p: p.name)
def test_meta_tags(html_file: Path) -> None:
    html = _read(html_file)
    assert re.search(r"<title>[^<]+</title>", html), "missing <title>"
    assert re.search(
        r'<meta[^>]+name=["\']viewport["\']', html
    ), "missing viewport meta"
    assert re.search(r'<link[^>]+rel=["\']icon["\']', html), "missing favicon link"
    for prop in REQUIRED_META:
        assert re.search(
            rf'<meta[^>]+property=["\']{re.escape(prop)}["\']', html
        ), f"missing og meta: {prop}"


@pytest.mark.parametrize("html_file", HTML_FILES, ids=lambda p: p.name)
def test_relative_links_resolve(html_file: Path) -> None:
    html = _read(html_file)
    href_pattern = re.compile(r'(?:href|src)=["\']([^"\']+)["\']')
    for raw in href_pattern.findall(html):
        if not raw or raw.startswith(("#", "data:", "mailto:", "javascript:")):
            continue
        parsed = urlparse(raw)
        if parsed.scheme or parsed.netloc:
            continue
        path = raw.split("#", 1)[0].split("?", 1)[0]
        if not path:
            continue
        if path.startswith("/"):
            target = (ROOT / path.lstrip("/")).resolve()
        else:
            target = (html_file.parent / path).resolve()
        assert target.exists(), f"{html_file.name} references missing {raw}"


@pytest.mark.parametrize("html_file", SHELL_HTML_FILES, ids=lambda p: p.name)
def test_pages_include_shared_hub_shell(html_file: Path) -> None:
    html = _read(html_file)
    assert 'href="assets/nav.css"' in html, f"{html_file.name} missing shared nav CSS"
    assert 'src="assets/site-shell.js"' in html, f"{html_file.name} missing shared shell JS"


@pytest.mark.parametrize("html_file", SHELL_CSS_HTML_FILES, ids=lambda p: p.name)
def test_inner_pages_include_shared_shell_css(html_file: Path) -> None:
    html = _read(html_file)
    assert 'href="assets/site-shell.css"' in html, f"{html_file.name} missing shared shell CSS"


def test_analytics_loader_is_present_everywhere() -> None:
    shell_js = _read(ROOT / "assets" / "site-shell.js")
    analytics_js = _read(ROOT / "assets" / "analytics.js")

    assert "assets/analytics.js" in shell_js
    assert "window.siteAnalytics" in analytics_js
    assert "nav_click" in analytics_js
    assert "cloudflareinsights.com/beacon.min.js" in analytics_js

    for html_file in HTML_FILES:
        html = _read(html_file)
        assert 'src="assets/site-shell.js"' in html, f"{html_file.name} missing shared shell JS"
        assert "data-cf-beacon" not in html, f"{html_file.name} still embeds a beacon inline"
        if html_file.name in {"index.html", "404.html"}:
            assert 'src="assets/analytics.js"' in html, f"{html_file.name} missing inline analytics tag"


def test_standings_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "standings.json"))
    assert "generated" in data
    assert "week" in data
    assert "category_order" in data and isinstance(data["category_order"], list)
    assert "category_leaders" in data and isinstance(data["category_leaders"], dict)
    assert "teams" in data and isinstance(data["teams"], list)
    assert data["teams"], "standings has no teams"
    for cat in data["category_order"]:
        assert cat in data["category_leaders"], f"missing category leader for {cat}"
    for team in data["teams"]:
        for key in ("rank", "team", "total_pts", "pts_behind", "pts_change", "categories"):
            assert key in team, f"standings team missing {key}"
        assert isinstance(team["categories"], dict)
        for cat in data["category_order"]:
            assert cat in team["categories"], f"{team['team']} missing category {cat}"
            assert "pts" in team["categories"][cat], f"{team['team']} missing pts for {cat}"


def test_transactions_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "transactions.json"))
    assert "generated" in data
    assert "transactions" in data and isinstance(data["transactions"], list)
    for txn in data["transactions"]:
        for key in ("id", "date", "type", "team", "player", "badge"):
            assert key in txn, f"transaction missing {key}"


def test_prospects_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "prospects.json"))
    assert "generated" in data
    assert "teams" in data and isinstance(data["teams"], list)
    for team in data["teams"]:
        for key in ("team", "count", "prospects"):
            assert key in team, f"prospect team missing {key}"
        assert isinstance(team["prospects"], list)
        if team["prospects"]:
            first = team["prospects"][0]
            for key in ("rank", "name", "org", "level", "positions", "age"):
                assert key in first, f"prospect missing {key}"


def test_franchises_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "franchises.json"))
    assert "generated" in data
    assert "teams" in data and isinstance(data["teams"], list)
    if data["teams"]:
        first = data["teams"][0]
        for key in ("team", "season_summaries", "snapshots", "transactions", "insights_2025"):
            assert key in first
        if first["insights_2025"]:
            insight = first["insights_2025"][0]
            for key in ("type", "label", "value", "detail"):
                assert key in insight


def test_feed_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "feed.json"))
    assert "generated" in data
    assert "events" in data and isinstance(data["events"], list)
    if data["events"]:
        first = data["events"][0]
        for key in ("event_id", "date", "event_type", "title", "detail"):
            assert key in first


def test_rivalries_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "rivalries.json"))
    assert "generated" in data
    assert "teams" in data and isinstance(data["teams"], list)
    assert "leaders" in data and isinstance(data["leaders"], list)
    if data["teams"]:
        first = data["teams"][0]
        for key in ("team", "rivals"):
            assert key in first
        if first["rivals"]:
            rival = first["rivals"][0]
            for key in (
                "rival_team",
                "rivalry_score",
                "finish_proximity_score",
                "category_similarity_score",
                "points_stolen_score",
                "tags",
            ):
                assert key in rival


def test_league_intelligence_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "league_intelligence.json"))
    assert "generated" in data
    assert "snapshot_date" in data
    assert "teams" in data and isinstance(data["teams"], list)
    for key in ("contention", "luck", "volatility"):
        assert key in data and isinstance(data[key], list)
    if data["teams"]:
        first = data["teams"][0]
        for key in ("team", "tier", "points_back", "reachable_points", "tight_categories", "luck", "volatility"):
            assert key in first


def test_oracle_public_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "oracle_public.json"))
    assert "generated" in data
    assert "season" in data
    assert "snapshot_date" in data
    assert "sources" in data and isinstance(data["sources"], dict)
    assert "teams" in data and isinstance(data["teams"], list)
    assert data["teams"], "oracle_public has no teams"
    first = data["teams"][0]
    for key in (
        "team",
        "oracle_rank",
        "standings_rank",
        "total_value",
        "mlb_value",
        "farm_value",
        "avg_age",
        "public_archetypes",
        "pressure",
        "trade_needs",
        "trend",
    ):
        assert key in first, f"oracle_public team missing {key}"
    assert isinstance(first["public_archetypes"], list)
    assert isinstance(first["trade_needs"], list)
    for key in ("score", "gain_target", "loss_risk", "summary"):
        assert key in first["pressure"], f"oracle_public pressure missing {key}"
    for key in ("pts_change", "stock", "summary"):
        assert key in first["trend"], f"oracle_public trend missing {key}"


def test_home_preview_schema_and_freshness() -> None:
    data = json.loads(_read(ROOT / "data" / "home_preview.json"))
    standings = json.loads(_read(ROOT / "data" / "standings.json"))
    transactions = json.loads(_read(ROOT / "data" / "transactions.json"))
    oracle = json.loads(_read(ROOT / "data" / "oracle_public.json"))

    assert data["generated"] == standings["generated"]
    assert data["generated_at"] == standings["generated_at"]
    assert data["snapshot_date"] == oracle["snapshot_date"]
    assert "leaderboard" in data and isinstance(data["leaderboard"], list)
    assert "transactions" in data and isinstance(data["transactions"], list)
    assert "oracle_teams" in data and isinstance(data["oracle_teams"], list)
    assert len(data["leaderboard"]) == 6
    assert len(data["transactions"]) <= 9
    assert len(data["oracle_teams"]) == len(oracle["teams"])

    expected_leaderboard = [
        {
            "rank": team["rank"],
            "team": team["team"],
            "total_pts": team["total_pts"],
            "pts_change": team["pts_change"],
        }
        for team in sorted(standings["teams"], key=lambda team: team.get("rank") or 99)[:6]
    ]
    expected_transactions = [
        {
            "type": txn["type"],
            "team": txn["team"],
            "player": txn["player"],
        }
        for txn in transactions["transactions"][:9]
    ]
    assert data["leaderboard"] == expected_leaderboard
    assert data["transactions"] == expected_transactions
    html = _read(ROOT / "index.html")
    for team in expected_leaderboard:
        change = float(team["pts_change"] or 0)
        change_txt = f"+{change:.1f}" if change > 0 else f"{change:.1f}"
        assert f'<div class="lb-rank">#{team["rank"]}</div>' in html
        assert f'<div class="lb-team">{team["team"]}</div>' in html
        assert f'<div class="lb-pts">{float(team["total_pts"]):.1f}</div>' in html
        assert f">{change_txt}</div>" in html
    for team in data["oracle_teams"]:
        for key in ("team", "oracle_rank", "total_value", "mlb_value", "farm_value", "avg_age", "scatter_move"):
            assert key in team, f"home preview oracle team missing {key}"


def test_rules_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "rules.json"))
    assert "version_label" in data
    assert "supplemental_version_label" in data
    assert "sections" in data and isinstance(data["sections"], list)
    assert data["sections"], "rules has no sections"
    first = data["sections"][0]
    for key in ("number", "title", "anchor", "source", "summary", "highlights", "blocks"):
        assert key in first, f"rules section missing {key}"
    assert "blocks" in first and isinstance(first["blocks"], list)


def test_rules_include_constitution_sections() -> None:
    data = json.loads(_read(ROOT / "data" / "rules.json"))
    constitution_sections = [section for section in data["sections"] if section.get("source") == "constitution"]
    assert constitution_sections, "expected at least one constitution section in rules payload"
    assert data["supplemental_version_label"], "expected supplemental constitution version label"
    for section in constitution_sections:
        assert section["summary"], f"constitution section {section['title']} missing summary"


def test_rules_page_toc_links_match_sections() -> None:
    html = _read(ROOT / "rules.html")
    data = json.loads(_read(ROOT / "data" / "rules.json"))
    assert 'id="tocList"' in html, "rules page missing TOC container"
    assert 'id="sections"' in html, "rules page missing sections container"
    assert 'class="section-summary"' in html, "rules page missing section summary hook"
    assert 'class="section-source"' in html, "rules page missing source badge hook"
    assert 'class="rule-block-grid"' in html, "rules page should render kv blocks as block cards"
    assert 'class="rules-table"' not in html, "rules page should not render kv blocks as tables"
    assert 'href="#${esc(section.anchor)}"' in html, "rules TOC template missing section anchor href"
    assert 'id="${esc(section.anchor)}"' in html, "rules section template missing section anchor id"

    section_anchors: list[str] = []
    block_anchors: list[str] = []
    for section in data["sections"]:
        assert "items" not in section, f"{section['title']} still has redundant top-level items"
        anchor = section["anchor"]
        assert isinstance(anchor, str) and anchor, "rules section anchor missing"
        assert re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", anchor), f"invalid section anchor: {anchor}"
        section_anchors.append(anchor)
        for block in section.get("blocks", []):
            if block.get("title") and block.get("anchor"):
                block_anchor = block["anchor"]
                assert re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", block_anchor), f"invalid block anchor: {block_anchor}"
                block_anchors.append(block_anchor)

    assert len(section_anchors) == len(set(section_anchors)), "duplicate rules section anchors"
    assert len(block_anchors) == len(set(block_anchors)), "duplicate rules block anchors"


def test_managers_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "managers.json"))
    assert "generated" in data
    assert "season" in data
    assert "managers" in data and isinstance(data["managers"], list)
    if data["managers"]:
        first = data["managers"][0]
        for key in ("team", "archetype", "trade_count", "add_count", "drop_count", "roster_churn"):
            assert key in first, f"manager missing {key}"


def test_closers_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "closers.json"))
    assert "generated" in data
    assert "snapshot_date" in data
    assert "closers" in data and isinstance(data["closers"], list)
    assert "by_dynasty_team" in data and isinstance(data["by_dynasty_team"], dict)
    if data["closers"]:
        first = data["closers"][0]
        for key in ("closer_name", "bullpen_team", "dynasty_team", "recent_saves", "confidence_score", "unstable_flag"):
            assert key in first, f"closer missing {key}"


def test_team_registry_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "team_registry.json"))
    assert "generated" in data
    assert "season" in data
    assert "teams" in data and isinstance(data["teams"], list)
    aliases: list[str] = []
    keys: list[str] = []
    for team in data["teams"]:
        for key in ("team_key", "display_name", "aliases"):
            assert key in team, f"team registry entry missing {key}"
        assert isinstance(team["aliases"], list) and team["aliases"], "team registry aliases missing"
        aliases.extend(team["aliases"])
        keys.append(team["team_key"])
    assert len(keys) == len(set(keys)), "duplicate team registry keys"
    assert len(aliases) == len(set(aliases)), "duplicate team registry aliases"


def test_oracle_public_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "oracle_public.json"))
    assert "generated" in data
    assert "season" in data
    assert "sources" in data and isinstance(data["sources"], dict)
    assert "teams" in data and isinstance(data["teams"], list)
    if data["teams"]:
        first = data["teams"][0]
        for key in (
            "team",
            "oracle_rank",
            "standings_rank",
            "total_value",
            "mlb_value",
            "farm_value",
            "avg_age",
            "contention_tier",
            "public_archetypes",
            "pressure",
            "trade_needs",
            "trend",
        ):
            assert key in first, f"oracle_public team missing {key}"
        assert isinstance(first["public_archetypes"], list)
        assert isinstance(first["trade_needs"], list)


def test_feedback_js_points_at_repo() -> None:
    js = _read(ROOT / "assets" / "feedback.js") if (ROOT / "assets" / "feedback.js").exists() else _read(ROOT / "feedback.js")
    assert FEEDBACK_REPO in js, f"feedback.js should reference {FEEDBACK_REPO}"


def test_issue_templates_exist() -> None:
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml").exists()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature.yml").exists()


def test_roster_depth_keeps_position_header_visible() -> None:
    html = _read(ROOT / "roster_depth.html")
    assert 'class="sticky-bar-wrap"' in html
    assert 'id="stickyBarScroll"' in html
    assert 'id="tableScroll"' in html
    assert 'position: sticky;' in html

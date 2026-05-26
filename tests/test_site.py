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
WEEKLY_HTML_FILES = sorted(ROOT.glob("week*_power_rankings.html"))
WEEKLY_TEMPLATE = ROOT / "templates" / "power_rankings_template.html"
META_HTML_FILES = [p for p in HTML_FILES if p.name != "404.html"]
SHELL_HTML_FILES = HTML_FILES
SHELL_CSS_HTML_FILES = [p for p in HTML_FILES if p.name not in {"index.html", "404.html"}]
REQUIRED_META = {"og:title", "og:image"}
FEEDBACK_ENDPOINT = "baseball-feedback.baseball-feedback.workers.dev"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages-on-release.yml"


class StrictHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_theme_boot_is_external_and_before_stylesheets() -> None:
    checked_files = HTML_FILES + [WEEKLY_TEMPLATE]

    for html_file in checked_files:
        text = _read(html_file)
        assert "localStorage.getItem('pr-theme')" not in text, (
            f"{html_file.name} still has the inline theme boot snippet"
        )

    for html_file in HTML_FILES:
        html = _read(html_file)
        boot = html.find('src="assets/fouc-prevention.js"')
        stylesheet = html.find('rel="stylesheet"')
        assert boot != -1, f"{html_file.name} missing external FOUC prevention script"
        assert stylesheet != -1, f"{html_file.name} missing stylesheet"
        assert boot < stylesheet, f"{html_file.name} loads FOUC prevention after first stylesheet"


def test_weekly_power_rankings_use_canonical_stylesheet() -> None:
    assert (ROOT / "assets" / "power-rankings.css").exists()
    assert '@import url("power-rankings.css")' in _read(ROOT / "assets" / "power-rankings-theme.css")

    for html_file in WEEKLY_HTML_FILES + [WEEKLY_TEMPLATE]:
        html = _read(html_file)
        assert 'href="assets/power-rankings.css"' in html, (
            f"{html_file.name} missing canonical weekly power rankings CSS"
        )
        assert 'href="assets/power-rankings-theme.css"' not in html, (
            f"{html_file.name} still depends on compatibility shim"
        )

    for html_file in HTML_FILES:
        assert 'href="assets/power-rankings-theme.css"' not in _read(html_file), (
            f"{html_file.name} still depends on compatibility shim"
        )


def test_weekly_power_rankings_mobile_content_is_contained() -> None:
    css = _read(ROOT / "assets" / "power-rankings.css")
    week10 = _read(ROOT / "week10_power_rankings.html")

    assert "grid-template-columns: 72px minmax(0, 1fr);" in css
    assert "grid-template-columns: 52px minmax(0, 1fr);" in css
    assert ".rank-content {\n    padding-left: 8px;\n    min-width: 0;" in css
    assert ".blurb a {\n    overflow-wrap: anywhere;" in css
    assert ".player-pill {\n    display: inline-block;" in css
    assert ".player-pill {\n    display: inline-flex;" not in css
    assert "height: auto;" in css
    assert "text-transform: none;" in css
    assert ".key-players .player-pill {\n    display: block;\n    width: 100%;" in css
    assert ".legend .player-pill {\n  white-space: nowrap;" in css
    assert 'class="site-shell-back-link"' not in week10


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
        "data/rules.json",
        "data/site_manifest.json",
        "data/site_updates.json",
        "llms.txt",
        "robots.txt",
        "sitemap.xml",
        "index.html",
    ):
        assert f'- "{path}"' in workflow, f"Pages deploy workflow must include {path}"


def test_dynasty_rankings_supports_search_deep_link() -> None:
    html = _read(ROOT / "dynasty_rankings.html")

    assert "params.get('search')" in html
    assert "document.getElementById('searchInput').value = searchParam;" in html
    assert 'tr[data-rank="${rankParam}"]' in html
    assert 'tr[data-player-slug="${CSS.escape(exactSlug)}"]' in html


def test_agent_discovery_files_exist_and_reference_public_data() -> None:
    for name in ("llms.txt", "robots.txt", "sitemap.xml"):
        assert (ROOT / name).exists(), f"missing {name}"

    manifest = json.loads(_read(ROOT / "data" / "site_manifest.json"))
    updates = json.loads(_read(ROOT / "data" / "site_updates.json"))
    llms = _read(ROOT / "llms.txt")
    robots = _read(ROOT / "robots.txt")
    sitemap = _read(ROOT / "sitemap.xml")

    assert "pages" in manifest and manifest["pages"]
    assert "public_data" in manifest and manifest["public_data"]
    assert updates["pages"]["index.html"]["source"] == "data/home_preview.json"
    assert updates["pages"]["dynasty_rankings.html"]["source"] == "data/dynasty_rankings_latest.json"
    assert "/data/site_manifest.json" in llms
    assert "/data/dynasty_rankings_latest.json" in llms
    assert "Sitemap: https://baseball.stephenmandella.com/sitemap.xml" in robots
    assert "https://baseball.stephenmandella.com/standings.html" in sitemap
    assert "https://baseball.stephenmandella.com/dynasty_rankings.html" in sitemap
    dynasty = next(page for page in manifest["pages"] if page["path"] == "dynasty_rankings.html")
    assert dynasty["indexable"] is True
    assert "data/dynasty_rankings_latest.json" in dynasty["data"]


def test_js_heavy_pages_include_structured_data_summary() -> None:
    for name in ("standings.html", "team_intel.html", "dynasty_rankings.html", "prospects.html", "transactions.html", "power_rankings.html"):
        html = _read(ROOT / name)
        assert 'type="application/ld+json"' in html, f"{name} missing JSON-LD summary"


def test_dynasty_rankings_is_agent_discoverable() -> None:
    html = _read(ROOT / "dynasty_rankings.html")
    data = json.loads(_read(ROOT / "data" / "dynasty_rankings_latest.json"))
    assert '<meta name="robots" content="index, follow">' in html
    assert "data/dynasty_rankings_latest.json" in html
    assert "rankings" in data and data["rankings"]


def test_index_uses_shared_theme_stack_without_legacy_fonts() -> None:
    html = _read(ROOT / "index.html")
    assert 'href="assets/theme.css"' in html
    assert 'href="assets/site.css"' in html
    assert 'href="assets/site-shell.css"' in html
    assert "Bebas Neue" not in html
    assert "DM Sans" not in html


def test_fangraphs_links_are_app_aware() -> None:
    helper = _read(ROOT / "assets" / "fangraphs-links.js")
    assert "com.fangraphs.fangraphsmobile" in helper
    assert "intent://" in helper
    assert "browser_fallback_url" in helper
    for name in ("prospects.html", "dynasty_rankings.html", "roster_depth.html"):
        html = _read(ROOT / name)
        assert 'src="assets/fangraphs-links.js"' in html
        assert "fangraphsLinks" in html


def test_dynasty_rankings_sort_keeps_blank_numeric_values_last() -> None:
    html = _read(ROOT / "dynasty_rankings.html")
    assert "const _descFirstCols = new Set" in html
    assert "if (aMissing) return 1;" in html
    assert "if (bMissing) return -1;" in html
    assert "'st_sb'" in html and "'mlb_sb'" in html


def test_dynasty_rankings_advanced_row_cells_match_header_order() -> None:
    html = _read(ROOT / "dynasty_rankings.html")
    start = html.index("function _buildRow")
    end = html.index("return tr;", start)
    create_row = html[start:end]
    assert "COLS.forEach(col => tr.appendChild(_cellForColumn(p, col)));" in create_row
    assert "const _numericCols = new Set(COLS.filter(col => col.numeric).map(col => col.key));" in html
    assert "const _descFirstCols = new Set(COLS.filter(col => col.descFirst).map(col => col.key));" in html
    assert "window.rankingsFieldSchema = RANKINGS_FIELD_SCHEMA;" in html
    assert "th.title = col.description;" in html


def test_hardcoded_color_audit_tool_exists() -> None:
    script = ROOT / "scripts" / "audit_hardcoded_colors.py"
    assert script.exists()
    text = _read(script)
    assert "COLOR_RE" in text
    assert "ALLOWLIST_CONTEXT" in text


def test_rank_history_modal_css_is_shared() -> None:
    site_css = _read(ROOT / "assets" / "site.css")
    dynasty_html = _read(ROOT / "dynasty_rankings.html")
    depth_html = _read(ROOT / "roster_depth.html")
    prospects_html = _read(ROOT / "prospects.html")

    assert ".player-modal {" in site_css
    assert ".player-panel {" in site_css
    assert ".src-pill {" in site_css
    assert ".src-pill-oracle" in site_css
    assert ".src-pill-fg" in site_css
    assert ".player-panel {" not in dynasty_html
    assert ".player-panel {" not in depth_html
    assert ".player-panel {" not in prospects_html
    assert ".src-pill {" not in dynasty_html
    assert ".src-pill {" not in depth_html
    assert ".src-pill {" not in prospects_html


def test_team_intel_table_links_and_bar_metadata_are_visible() -> None:
    html = _read(ROOT / "team_intel.html")
    assert "function rosterDepthLink(teamName" in html
    assert '<td>${rosterDepthLink(team.team)}</td>' in html
    assert 'href="${rosterDepthHref(row.team)}"' in html
    assert "Avg age:" in html
    assert "Scatter move: no prior oracle snapshot" in html


def test_prospects_desk_opens_shared_player_modal() -> None:
    html = _read(ROOT / "prospects.html")
    assert "wireDeskToModal();" in html
    assert "function wireDeskToModal()" in html
    assert "openPlayerModal(row.dataset.playerName)" in html
    assert "goToRadarPlayer(row.dataset.playerName" not in html
    assert "oracleLinkHtml(player.rankings_url)" in html


def test_dynasty_rankings_schema_is_discoverable() -> None:
    schema = json.loads(_read(ROOT / "data" / "dynasty_rankings_schema.json"))
    manifest = json.loads(_read(ROOT / "data" / "site_manifest.json"))
    llms = _read(ROOT / "llms.txt")
    assert schema["dataset"] == "data/dynasty_rankings_latest.json"
    assert schema["fields"]
    assert "data/dynasty_rankings_schema.json" in llms
    dynasty = next(page for page in manifest["pages"] if page["path"] == "dynasty_rankings.html")
    assert "data/dynasty_rankings_schema.json" in dynasty["data"]


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
        if not raw or raw.startswith(("#", "data:", "mailto:", "javascript:", "${")):
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


def test_site_header_typography_stays_shared() -> None:
    local_header_rule = re.compile(
        r"\.(?:site-header\s*\{|eyebrow\s*\{|site-header\s+h1|site-header\s+p\s*\{|divider\s*\{)"
    )
    for html_file in HTML_FILES:
        if html_file.name == "404.html":
            continue
        html = _read(html_file)
        if 'class="site-header"' not in html or 'href="assets/site.css"' not in html:
            continue
        assert not local_header_rule.search(html), (
            f"{html_file.name} should inherit shared site-header typography from assets/site.css"
        )


def test_roster_depth_uses_shared_header_and_nav_fonts() -> None:
    html = _read(ROOT / "roster_depth.html")
    nav_css = _read(ROOT / "assets" / "nav.css")

    assert 'href="assets/site.css"' in html
    assert 'class="site-header"' in html
    assert 'class="header"' not in html
    assert "Bebas Neue" not in html
    assert "DM Sans" not in html
    assert "DM Sans" not in nav_css
    assert 'href="assets/icons.svg#icon-arrows-swap"' in html
    assert "⇄" not in html
    assert 'class="card legend-card"' in html
    assert html.count('class="legend-row"') == 2
    assert ".pill {\n  display: flex;" in html
    assert ".pill {\n  display: inline-flex;" not in html
    assert ':root[data-theme="light"]' in html
    assert "--depth-team-name: var(--text);" in html
    assert ".t1 { background: var(--depth-t1-bg);" in html
    assert ".t1 { background: #6b1212;" not in html


def test_power_rankings_archive_uses_shared_list_markup() -> None:
    html = _read(ROOT / "power_rankings.html")

    assert 'class="card archive-card"' in html
    assert 'class="list-group"' in html
    assert 'class="list-row list-row--featured"' in html
    assert 'class="archive-row' not in html
    assert 'class="archive-list"' not in html


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


def test_feedback_js_uses_no_login_issue_endpoint() -> None:
    js = _read(ROOT / "assets" / "feedback.js") if (ROOT / "assets" / "feedback.js").exists() else _read(ROOT / "feedback.js")
    assert FEEDBACK_ENDPOINT in js, f"feedback.js should post to {FEEDBACK_ENDPOINT}"
    assert "BACKYARD_FEEDBACK_ENDPOINT" in js
    assert "fetch(FEEDBACK_ENDPOINT" in js
    assert "issues/new" not in js
    assert "mailto:" not in js


def test_issue_templates_exist() -> None:
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml").exists()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature.yml").exists()


def test_roster_depth_keeps_position_header_visible() -> None:
    html = _read(ROOT / "roster_depth.html")
    assert 'class="sticky-bar-wrap"' in html
    assert 'id="stickyBarScroll"' in html
    assert 'id="tableScroll"' in html
    assert 'position: sticky;' in html


def test_roster_depth_supports_team_deep_links() -> None:
    html = _read(ROOT / "roster_depth.html")
    assert "const scrollToLinkedTeam = () =>" in html
    assert "new URLSearchParams(window.location.search).get('team')" in html
    assert "targetRow.scrollIntoView({ block: 'start', behavior: 'auto' });" in html
    assert "tbody tr.team-target" in html

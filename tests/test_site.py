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
REQUIRED_META = {"og:title", "og:image"}
FEEDBACK_REPO = "sdmandel/dynasty-rankings"


class StrictHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


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


def test_standings_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "standings.json"))
    assert "generated" in data
    assert "teams" in data and isinstance(data["teams"], list)
    assert data["teams"], "standings has no teams"
    for team in data["teams"]:
        assert "rank" in team
        assert "team" in team or "name" in team


def test_transactions_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "transactions.json"))
    assert "generated" in data
    assert "transactions" in data and isinstance(data["transactions"], list)
    if data["transactions"]:
        first = data["transactions"][0]
        for key in ("type", "team", "player"):
            assert key in first, f"transaction missing {key}"


def test_prospects_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "prospects.json"))
    assert "generated" in data
    assert "teams" in data and isinstance(data["teams"], list)


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


def test_rules_schema() -> None:
    data = json.loads(_read(ROOT / "data" / "rules.json"))
    assert "version_label" in data
    assert "sections" in data and isinstance(data["sections"], list)
    assert data["sections"], "rules has no sections"
    first = data["sections"][0]
    for key in ("number", "title", "anchor", "items"):
        assert key in first, f"rules section missing {key}"
    assert "blocks" in first and isinstance(first["blocks"], list)


def test_rules_page_toc_links_match_sections() -> None:
    html = _read(ROOT / "rules.html")
    data = json.loads(_read(ROOT / "data" / "rules.json"))
    for section in data["sections"]:
        anchor = section["anchor"]
        assert f'href="#{anchor}"' in html or "tocList" in html
        assert f'id="{anchor}"' in html or "renderSections" in html
        for block in section.get("blocks", []):
            if block.get("title") and block.get("anchor"):
                assert block["anchor"]


def test_feedback_js_points_at_repo() -> None:
    js = _read(ROOT / "assets" / "feedback.js") if (ROOT / "assets" / "feedback.js").exists() else _read(ROOT / "feedback.js")
    assert FEEDBACK_REPO in js, f"feedback.js should reference {FEEDBACK_REPO}"


def test_issue_templates_exist() -> None:
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml").exists()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature.yml").exists()

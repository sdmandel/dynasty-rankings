from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = (ROOT / "rules.html").read_text(encoding="utf-8")
HISTORY = (ROOT / "franchise_history.html").read_text(encoding="utf-8")


def test_rules_contents_is_sticky_and_collapsible() -> None:
    assert 'position: sticky' in RULES
    assert 'id="tocToggle"' in RULES
    assert 'aria-controls="tocList"' in RULES
    assert "syncTocVisibility" in RULES
    assert ".rules-layout > main," in RULES


def test_rules_generated_content_uses_semantic_headings_and_tables() -> None:
    assert '<h2 class="section-title">' in RULES
    assert '<h3 class="block-title"' in RULES
    assert '<th scope="col">${esc(col)}</th>' in RULES


def test_franchise_selection_is_explicit_and_accessible() -> None:
    assert 'id="franchisePickerLabel"' in HISTORY
    assert 'role="group" aria-labelledby="franchisePickerLabel"' in HISTORY
    assert 'id="selectionStatus" aria-live="polite"' in HISTORY
    assert 'aria-label="Snapshot date range"' in HISTORY
    assert 'aria-pressed="true"' in HISTORY


def test_franchise_state_is_shareable_and_handles_history_navigation() -> None:
    assert "new URLSearchParams(location.search)" in HISTORY
    assert "params.set('team'," in HISTORY
    assert "params.set('range'," in HISTORY
    assert "history.pushState" in HISTORY
    assert "window.addEventListener('popstate', syncFromUrl)" in HISTORY


def test_franchise_archive_status_comes_from_payload_metadata() -> None:
    assert "years.includes(currentYear)" in HISTORY
    assert "Current season + archive" in HISTORY
    assert "Archived snapshots" in HISTORY
    assert "data.generated" in HISTORY

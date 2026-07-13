from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "transactions.html").read_text(encoding="utf-8")


def test_transaction_feed_precedes_manager_profiles() -> None:
    assert PAGE.index('id="mainContent"') < PAGE.index('id="mgrSection"')
    assert '<details class="manager-profile-card">' in PAGE
    assert "How profiles work" in PAGE


def test_transaction_filters_are_labeled_and_accessible() -> None:
    assert 'role="group" aria-labelledby="typeFilterLabel"' in PAGE
    assert PAGE.count('aria-pressed="false"') == 4
    assert 'aria-pressed="true"' in PAGE
    assert '<label class="filter-label" for="teamFilter">Team</label>' in PAGE
    assert '<label class="filter-label" for="dateFilter">Date</label>' in PAGE
    assert 'id="resultStatus" role="status" aria-live="polite"' in PAGE


def test_transaction_filter_state_uses_url_and_history() -> None:
    assert "new URLSearchParams(location.search)" in PAGE
    assert "history.pushState" in PAGE
    assert "window.addEventListener('popstate'" in PAGE
    assert "params.set('type', activeFilter)" in PAGE
    assert "params.set('team', activeTeam)" in PAGE
    assert "params.set('date', activeDate)" in PAGE


def test_transaction_page_has_empty_and_error_recovery_states() -> None:
    assert "No transactions match these filters" in PAGE
    assert "location.reload()" in PAGE
    assert "Could not load transaction data" in PAGE


def test_date_filter_is_anchored_to_export_data() -> None:
    assert "ALL_TXNS.reduce" in PAGE
    assert "cutoff.setDate" in PAGE

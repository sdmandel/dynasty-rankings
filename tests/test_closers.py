"""Focused accessibility and responsive behavior checks for Closer Carousel."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "closers.html").read_text(encoding="utf-8")


def test_closer_cards_expose_text_role_state() -> None:
    assert 'class="role-state"' in PAGE
    assert "function roleLabel(share)" in PAGE
    assert "Strong confidence" not in PAGE  # Labels remain derived from live data.
    assert "${confLabel(item.confidence_score)} confidence" in PAGE
    assert "${roleLabel(item.role_share)}" in PAGE


def test_full_board_has_table_semantics() -> None:
    assert '<caption class="table-caption">' in PAGE
    assert PAGE.count('scope="col"') == 8
    assert '<th scope="row">${esc(c.closer_name' in PAGE


def test_loading_and_error_states_are_announced_and_retryable() -> None:
    assert 'id="loadingMsg" class="state-msg" role="status" aria-live="polite"' in PAGE
    assert "loading.setAttribute('role','alert')" in PAGE
    assert 'id="retryClosers"' in PAGE
    assert "addEventListener('click',loadClosers,{once:true})" in PAGE


def test_mobile_board_preserves_closer_identity_while_scrolling() -> None:
    assert "table { min-width:760px; font-size:12px; }" in PAGE
    assert "thead th:nth-child(2), tbody th:nth-child(2) { position:sticky;" in PAGE

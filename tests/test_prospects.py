from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "prospects.html").read_text(encoding="utf-8")


def test_desk_and_radar_are_accessible_url_backed_tabs() -> None:
    assert 'role="tablist" aria-label="Prospect Desk views"' in HTML
    assert HTML.count('role="tab"') == 2
    assert 'role="tabpanel" aria-labelledby="tab-desk"' in HTML
    assert 'role="tabpanel" aria-labelledby="tab-radar"' in HTML
    assert "url.searchParams.set('view', activeMode)" in HTML
    assert "window.addEventListener('popstate', syncModeFromUrl)" in HTML
    assert "function handleModeKeydown(e)" in HTML


def test_filters_expose_pressed_state_and_feedback() -> None:
    assert HTML.count('class="filter-btn') == 3
    assert 'aria-pressed="true" data-filter="all"' in HTML
    assert HTML.count('aria-pressed="false" data-filter=') == 2
    assert 'id="filterStatus" role="status" aria-live="polite"' in HTML
    assert "btn.setAttribute('aria-pressed'" in HTML


def test_radar_players_support_keyboard_activation() -> None:
    assert '<button class="player-detail-button" type="button" aria-label="${esc(playerLabel)}"' in HTML
    assert "e.target.closest('.player-detail-button[data-player-name]')" in HTML


def test_player_modal_traps_and_restores_focus() -> None:
    assert 'aria-modal="true" aria-labelledby="playerModalTitle"' in HTML
    assert "else if (e.key === 'Tab') trapModalFocus(e, modal);" in HTML
    assert "function trapModalFocus(e, modal)" in HTML
    assert "if (modalReturnFocus?.isConnected) modalReturnFocus.focus();" in HTML
    assert "document.querySelector('[data-close-player-modal]').focus();" in HTML

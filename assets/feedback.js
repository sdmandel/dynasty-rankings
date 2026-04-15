/* feedback.js — floating feedback pill + modal for every page
 * Opens a prefilled GitHub Issue Form in a new tab. No backend needed.
 */
(function () {
  'use strict';

  const REPO = 'sdmandel/dynasty-rankings';

  // ── Styles ──────────────────────────────────────────────────────────────────
  const CSS = `
    #fb-pill {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9000;
      display: flex;
      align-items: center;
      gap: 7px;
      background: #2a2a2c;
      border: 1px solid #3e3e40;
      border-radius: 999px;
      padding: 9px 16px 9px 13px;
      cursor: pointer;
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      font-weight: 500;
      color: #c2bfb8;
      box-shadow: 0 2px 14px rgba(0,0,0,0.5);
      transition: background 0.15s, border-color 0.15s, color 0.15s;
    }
    #fb-pill:hover { background: #363638; border-color: #555558; color: #f0ede6; }
    #fb-pill svg { flex-shrink: 0; }

    #fb-overlay {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 9001;
      background: rgba(0,0,0,0.65);
      backdrop-filter: blur(3px);
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    #fb-overlay.open { display: flex; }

    #fb-modal {
      background: #141416;
      border: 1px solid #2a2a2c;
      border-radius: 10px;
      padding: 32px;
      width: 100%;
      max-width: 460px;
      font-family: 'DM Sans', sans-serif;
      position: relative;
    }
    #fb-modal h2 {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 30px;
      letter-spacing: 0.03em;
      color: #f0ede6;
      margin-bottom: 4px;
    }
    #fb-modal .fb-sub {
      font-size: 13px;
      color: #7a7872;
      margin-bottom: 24px;
    }

    /* Type selector */
    .fb-type-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 22px;
    }
    .fb-type-btn {
      background: #0e0e0f;
      border: 1px solid #1e1e20;
      border-radius: 6px;
      padding: 13px 10px 11px;
      cursor: pointer;
      text-align: center;
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      color: #7a7872;
      transition: border-color 0.12s, color 0.12s, background 0.12s;
      line-height: 1.4;
    }
    .fb-type-btn:hover { border-color: #3a3a3c; color: #c2bfb8; }
    .fb-type-btn.selected {
      border-color: #c8a84b;
      color: #c8a84b;
      background: rgba(200,168,75,0.07);
    }
    .fb-type-icon { font-size: 22px; display: block; margin-bottom: 5px; }

    /* Fields */
    .fb-label {
      display: block;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #4a4845;
      margin-bottom: 6px;
    }
    .fb-req { color: #b55d5d; }
    .fb-opt { color: #4a4845; font-weight: 400; text-transform: none; letter-spacing: 0; }
    .fb-input, .fb-textarea {
      width: 100%;
      background: #0e0e0f;
      border: 1px solid #1e1e20;
      border-radius: 5px;
      padding: 10px 12px;
      font-family: 'DM Sans', sans-serif;
      font-size: 14px;
      color: #f0ede6;
      outline: none;
      transition: border-color 0.12s;
      margin-bottom: 16px;
    }
    .fb-input:focus, .fb-textarea:focus { border-color: #3a3a3c; }
    .fb-textarea { resize: vertical; min-height: 80px; }
    .fb-error {
      font-size: 12px;
      color: #b55d5d;
      margin-top: -12px;
      margin-bottom: 12px;
      display: none;
    }
    .fb-error.show { display: block; }

    /* Actions */
    .fb-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 6px;
    }
    .fb-fallback {
      font-size: 11px;
      color: #4a4845;
      text-decoration: none;
    }
    .fb-fallback:hover { color: #7a7872; }
    .fb-btns { display: flex; gap: 10px; }
    .fb-btn-cancel {
      background: none;
      border: none;
      padding: 9px 14px;
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      color: #4a4845;
      cursor: pointer;
      border-radius: 5px;
      transition: color 0.12s;
    }
    .fb-btn-cancel:hover { color: #7a7872; }
    .fb-btn-submit {
      background: #c8a84b;
      border: none;
      border-radius: 5px;
      padding: 9px 20px;
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      font-weight: 600;
      color: #0e0e0f;
      cursor: pointer;
      transition: background 0.12s;
      white-space: nowrap;
    }
    .fb-btn-submit:hover { background: #d9bb60; }

    /* Close X */
    .fb-close {
      position: absolute;
      top: 14px;
      right: 14px;
      background: none;
      border: none;
      color: #4a4845;
      font-size: 20px;
      line-height: 1;
      padding: 4px 6px;
      cursor: pointer;
      transition: color 0.12s;
    }
    .fb-close:hover { color: #7a7872; }

    @media (max-width: 520px) {
      #fb-modal { padding: 24px 18px; }
      #fb-pill .fb-pill-label { display: none; }
    }
  `;

  // ── DOM builders ────────────────────────────────────────────────────────────
  function buildPill() {
    const btn = document.createElement('button');
    btn.id = 'fb-pill';
    btn.setAttribute('aria-label', 'Send feedback');
    btn.innerHTML =
      '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">' +
        '<path d="M7 1C3.686 1 1 3.343 1 6.25c0 1.742.9 3.284 2.3 4.272L2.5 13l2.8-1.4A6.19 6.19 0 0 0 7 11.5C10.314 11.5 13 9.157 13 6.25S10.314 1 7 1Z"' +
        ' stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>' +
      '</svg>' +
      '<span class="fb-pill-label">Feedback</span>';
    return btn;
  }

  function buildOverlay() {
    const el = document.createElement('div');
    el.id = 'fb-overlay';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'true');
    el.setAttribute('aria-labelledby', 'fb-title');
    el.innerHTML =
      '<div id="fb-modal">' +
        '<button class="fb-close" aria-label="Close">&times;</button>' +
        '<h2 id="fb-title">Feedback</h2>' +
        '<p class="fb-sub">Fill in the details below and click Send — we\'ll open a prefilled issue for you, all you have to do is click submit</p>' +

        '<div class="fb-type-row">' +
          '<button class="fb-type-btn selected" data-type="bug" type="button">' +
            '<span class="fb-type-icon">🐛</span>Something\'s broken' +
          '</button>' +
          '<button class="fb-type-btn" data-type="idea" type="button">' +
            '<span class="fb-type-icon">💡</span>I have an idea' +
          '</button>' +
        '</div>' +

        '<label class="fb-label" for="fb-summary">Summary <span class="fb-req">*</span></label>' +
        '<input id="fb-summary" class="fb-input" type="text" placeholder="One line…" maxlength="120" />' +
        '<div class="fb-error" id="fb-err">Please enter a summary.</div>' +

        '<label class="fb-label" for="fb-details">Details <span class="fb-opt">(optional)</span></label>' +
        '<textarea id="fb-details" class="fb-textarea" placeholder="Any extra context…"></textarea>' +

        '<div class="fb-actions">' +
          '<a class="fb-fallback" href="https://github.com/' + REPO + '/issues/new/choose" target="_blank" rel="noopener">Open GitHub directly</a>' +
          '<div class="fb-btns">' +
            '<button class="fb-btn-cancel" type="button">Cancel</button>' +
            '<button class="fb-btn-submit" id="fb-submit" type="button">Send →</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    return el;
  }

  // ── URL builder ─────────────────────────────────────────────────────────────
  function issueUrl(type, summary, details) {
    const bug  = type === 'bug';
    const title = (bug ? '[Bug] ' : '[Idea] ') + summary;
    const body  = [
      details.trim(),
      details.trim() ? '' : null,
      '---',
      'Page: ' + location.href,
      'Time: ' + new Date().toISOString(),
    ].filter(l => l !== null).join('\n');

    const params = new URLSearchParams({
      template: bug ? 'bug.yml' : 'feature.yml',
      title,
      body,
    });
    return 'https://github.com/' + REPO + '/issues/new?' + params;
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  function init() {
    if (document.getElementById('fb-pill') || document.getElementById('fb-overlay')) return;

    // Inject styles
    let style = document.getElementById('fb-style');
    if (!style) {
      style = document.createElement('style');
      style.id = 'fb-style';
      style.textContent = CSS;
      document.head.appendChild(style);
    }

    const pill    = buildPill();
    const overlay = buildOverlay();
    document.body.appendChild(pill);
    document.body.appendChild(overlay);

    const modal     = overlay.querySelector('#fb-modal');
    const typeBtns  = overlay.querySelectorAll('.fb-type-btn');
    const summaryEl = overlay.querySelector('#fb-summary');
    const detailsEl = overlay.querySelector('#fb-details');
    const errEl     = overlay.querySelector('#fb-err');
    const submitBtn = overlay.querySelector('#fb-submit');
    const cancelBtn = overlay.querySelector('.fb-btn-cancel');
    const closeBtn  = overlay.querySelector('.fb-close');

    let selectedType = 'bug'; // pre-selected default

    function openModal() {
      overlay.classList.add('open');
      summaryEl.focus();
    }

    function closeModal() {
      overlay.classList.remove('open');
      // Reset
      selectedType = 'bug';
      typeBtns.forEach(b => b.classList.toggle('selected', b.dataset.type === 'bug'));
      summaryEl.value = '';
      detailsEl.value = '';
      errEl.classList.remove('show');
      pill.focus();
    }

    // Type toggle
    typeBtns.forEach(btn => btn.addEventListener('click', () => {
      selectedType = btn.dataset.type;
      typeBtns.forEach(b => b.classList.toggle('selected', b === btn));
    }));

    // Submit
    submitBtn.addEventListener('click', () => {
      const summary = summaryEl.value.trim();
      if (!summary) { errEl.classList.add('show'); summaryEl.focus(); return; }
      errEl.classList.remove('show');
      window.open(issueUrl(selectedType, summary, detailsEl.value), '_blank', 'noopener');
      closeModal();
    });

    // Close triggers
    cancelBtn.addEventListener('click', closeModal);
    closeBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && overlay.classList.contains('open')) closeModal();
    });

    pill.addEventListener('click', openModal);
    summaryEl.addEventListener('keydown', e => { if (e.key === 'Enter') submitBtn.click(); });

    // Focus trap
    modal.addEventListener('keydown', e => {
      if (e.key !== 'Tab') return;
      const focusable = [...modal.querySelectorAll('button, input, textarea, a[href]')];
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();

(function () {
  'use strict';

  const CONFIG = window.POLLS_CONFIG || {
    backendBaseUrl: '',
    ballotParam: 'ballot',
    pollDataUrl: 'data/polls.json'
  };

  const state = {
    poll: null,
    questions: [],
    ballotToken: '',
    ballotSession: null,
    results: null,
    loading: false
  };

  const el = {
    loading: document.getElementById('loadingMsg'),
    shell: document.getElementById('pollShell'),
    title: document.getElementById('pollTitle'),
    eyebrow: document.getElementById('pollEyebrow'),
    description: document.getElementById('pollDescription'),
    opens: document.getElementById('pollOpens'),
    closes: document.getElementById('pollCloses'),
    turnout: document.getElementById('pollTurnout'),
    authPanel: document.getElementById('authPanel'),
    authStatus: document.getElementById('authStatus'),
    ballotInput: document.getElementById('ballotCode'),
    ballotBtn: document.getElementById('ballotBtn'),
    questionList: document.getElementById('questionList'),
    form: document.getElementById('ballotForm'),
    submit: document.getElementById('submitBtn'),
    submitState: document.getElementById('submitState'),
    resultMeta: document.getElementById('resultMeta'),
    resultList: document.getElementById('resultList'),
    backendNote: document.getElementById('backendNote')
  };

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtDate(value) {
    if (!value) return 'TBD';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  }

  function setAuthStatus(text, variant) {
    el.authStatus.textContent = text;
    el.authStatus.className = 'auth-status' + (variant ? ' ' + variant : '');
  }

  function setSubmitState(text, variant) {
    el.submitState.textContent = text;
    el.submitState.className = 'submit-state' + (variant ? ' ' + variant : '');
  }

  function setLoading(message) {
    el.loading.textContent = message;
    el.loading.style.display = '';
    el.shell.style.display = 'none';
  }

  function showShell() {
    el.loading.style.display = 'none';
    el.shell.style.display = '';
  }

  function getBallotToken() {
    const params = new URLSearchParams(window.location.search);
    return (params.get(CONFIG.ballotParam) || sessionStorage.getItem('pollBallotToken') || '').trim();
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || 'Request failed');
    }
    return response.json();
  }

  async function loadPollDefinition() {
    const data = await fetchJson(CONFIG.pollDataUrl);
    state.poll = data.poll || {};
    state.questions = Array.isArray(data.questions) ? data.questions : [];
  }

  function renderPollMeta() {
    const poll = state.poll;
    el.title.textContent = poll.title || 'League Votes';
    el.eyebrow.textContent = poll.eyebrow || 'League Votes';
    el.description.textContent = poll.description || 'Rule proposals and league votes.';
    el.opens.textContent = fmtDate(poll.opens_at);
    el.closes.textContent = fmtDate(poll.closes_at);

    const turnout = state.results && typeof state.results.total_ballots === 'number'
      ? state.results.total_ballots
      : 0;
    const expected = poll.expected_voters || 12;
    el.turnout.textContent = turnout + ' / ' + expected;
  }

  function renderQuestions() {
    el.questionList.innerHTML = state.questions.map((question, index) => {
      const checkedAnswer = state.ballotSession && state.ballotSession.answers
        ? state.ballotSession.answers[question.id]
        : '';

      return `
        <section class="question-card">
          <div class="question-number">Question ${index + 1}</div>
          <h3>${esc(question.prompt)}</h3>
          <p>${esc(question.description || '')}</p>
          <div class="option-list">
            ${(question.options || []).map(option => `
              <label class="option-row">
                <input
                  type="radio"
                  name="${esc(question.id)}"
                  value="${esc(option.id)}"
                  ${checkedAnswer === option.id ? 'checked' : ''}
                  ${state.ballotSession ? '' : 'disabled'}
                >
                <span class="option-copy">
                  <span class="option-label">${esc(option.label)}</span>
                </span>
              </label>
            `).join('')}
          </div>
        </section>
      `;
    }).join('');
  }

  function renderResults() {
    const results = state.results || {};
    const aggregate = results.questions || {};

    el.resultMeta.textContent = state.results
      ? 'Live totals from validated manager ballots.'
      : 'Results will appear here once the backend is configured.';

    el.resultList.innerHTML = state.questions.map(question => {
      const questionResult = aggregate[question.id] || {};
      const total = questionResult.total_votes || 0;

      const optionsHtml = (question.options || []).map(option => {
        const votes = questionResult.options && typeof questionResult.options[option.id] === 'number'
          ? questionResult.options[option.id]
          : 0;
        const pct = total ? Math.round((votes / total) * 100) : 0;
        return `
          <div class="result-row">
            <div class="result-head">
              <span>${esc(option.label)}</span>
              <span>${votes} · ${pct}%</span>
            </div>
            <div class="result-bar">
              <span style="width:${pct}%;"></span>
            </div>
          </div>
        `;
      }).join('');

      return `
        <section class="result-card">
          <div class="result-question">${esc(question.prompt)}</div>
          ${optionsHtml}
        </section>
      `;
    }).join('');
  }

  function validateAnswers() {
    const answers = {};
    for (const question of state.questions) {
      const selected = el.form.querySelector(`input[name="${CSS.escape(question.id)}"]:checked`);
      if (question.required && !selected) {
        throw new Error('Every question needs an answer before you submit the ballot.');
      }
      answers[question.id] = selected ? selected.value : null;
    }
    return answers;
  }

  async function refreshResults() {
    if (!CONFIG.backendBaseUrl) {
      state.results = null;
      renderPollMeta();
      renderResults();
      el.backendNote.textContent = 'Backend not configured yet. The page is live, but submissions are disabled until you set POLLS_CONFIG.backendBaseUrl.';
      return;
    }

    const url = CONFIG.backendBaseUrl.replace(/\/$/, '') + '/results?poll_id=' + encodeURIComponent(state.poll.id);
    state.results = await fetchJson(url);
    renderPollMeta();
    renderResults();
    el.backendNote.textContent = 'Backend connected. Share each manager a unique ballot URL like polls.html?ballot=abc123.';
  }

  async function resolveBallot(token) {
    if (!CONFIG.backendBaseUrl) {
      setAuthStatus('Backend not configured. Add your Supabase function URL first.', 'warn');
      return;
    }

    const url = CONFIG.backendBaseUrl.replace(/\/$/, '') + '/resolve-ballot';
    const payload = await fetchJson(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ poll_id: state.poll.id, ballot_token: token })
    });

    state.ballotSession = payload;
    state.ballotToken = token;
    sessionStorage.setItem('pollBallotToken', token);
    setAuthStatus(
      payload.has_submitted
        ? 'Ballot locked to ' + payload.manager_name + '. Existing answers loaded below.'
        : 'Ballot unlocked for ' + payload.manager_name + '.',
      'ok'
    );
    renderQuestions();
  }

  async function submitBallot(event) {
    event.preventDefault();

    if (!state.ballotSession || !state.ballotToken) {
      setSubmitState('Enter a valid ballot code first.', 'error');
      return;
    }

    try {
      const answers = validateAnswers();
      el.submit.disabled = true;
      setSubmitState('Submitting ballot…');

      const url = CONFIG.backendBaseUrl.replace(/\/$/, '') + '/submit-ballot';
      const payload = await fetchJson(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          poll_id: state.poll.id,
          ballot_token: state.ballotToken,
          answers
        })
      });

      state.ballotSession = payload;
      setSubmitState(
        payload.has_submitted
          ? 'Ballot saved. You can reopen the page from the same manager link and update until the deadline.'
          : 'Ballot saved.',
        'ok'
      );
      await refreshResults();
      renderQuestions();
    } catch (error) {
      setSubmitState(error.message || 'Unable to submit ballot.', 'error');
    } finally {
      el.submit.disabled = false;
    }
  }

  async function handleBallotEnter() {
    const token = el.ballotInput.value.trim();
    if (!token) {
      setAuthStatus('Paste the ballot code from your manager link.', 'warn');
      return;
    }

    try {
      setAuthStatus('Validating ballot code…');
      await resolveBallot(token);
    } catch (error) {
      setAuthStatus(error.message || 'Unable to validate ballot code.', 'error');
    }
  }

  async function init() {
    try {
      setLoading('Loading league ballot…');
      await loadPollDefinition();
      renderPollMeta();
      renderQuestions();
      renderResults();
      showShell();

      await refreshResults();

      const token = getBallotToken();
      if (token) {
        el.ballotInput.value = token;
        await resolveBallot(token);
      } else {
        setAuthStatus('Paste a ballot code or open the page from your manager-specific ballot link.');
      }

      el.ballotBtn.addEventListener('click', handleBallotEnter);
      el.form.addEventListener('submit', submitBallot);
    } catch (error) {
      setLoading(error.message || 'Unable to load poll page.');
    }
  }

  init();
})();

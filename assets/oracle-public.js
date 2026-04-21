async function fetchOraclePublic() {
  const response = await fetch(`data/oracle_public.json?ts=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function formatOracleDate(value) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: value.includes('T') ? 'numeric' : undefined,
    minute: value.includes('T') ? '2-digit' : undefined,
  });
}

function escHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderOracleFreshness(target, data, extras = []) {
  if (!target || !data) return;
  const chips = [
    `Last updated ${formatOracleDate(data.generated_at || data.generated)}`,
    data.snapshot_date ? `Snapshot ${formatOracleDate(data.snapshot_date)}` : null,
    data.week ? `Scoring period ${data.week}` : null,
    data.season_label || null,
    ...extras.filter(Boolean),
  ].filter(Boolean);

  target.innerHTML = chips.map(item => `<span class="meta-chip">${escHtml(item)}</span>`).join('');
}


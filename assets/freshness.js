(function (global) {
  'use strict';

  const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
  const STATUS_LABELS = {
    current: 'Current',
    delayed: 'Delayed',
    stale: 'Stale',
    archived: 'Archived snapshot',
    unknown: 'Freshness unknown'
  };

  function parseTimestamp(value) {
    if (!value || typeof value !== 'string') return null;
    const dateOnly = DATE_ONLY.test(value);
    const date = dateOnly
      ? new Date(Number(value.slice(0, 4)), Number(value.slice(5, 7)) - 1, Number(value.slice(8, 10)))
      : new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return { date, dateOnly };
  }

  function derive(options) {
    const opts = options || {};
    const raw = opts.timestamp || opts.generatedAt || opts.generated || opts.snapshotDate;
    const parsed = parseTimestamp(raw);
    if (opts.archived) return { status: 'archived', raw, parsed };
    if (!parsed) return { status: 'unknown', raw: null, parsed: null };
    if (!Number.isFinite(opts.currentHours)) return { status: 'unknown', raw, parsed };

    const now = opts.now instanceof Date ? opts.now : new Date();
    const ageHours = Math.max(0, (now.getTime() - parsed.date.getTime()) / 3600000);
    const currentHours = opts.currentHours;
    const delayedHours = Number.isFinite(opts.delayedHours) ? opts.delayedHours : currentHours * 3;
    const status = ageHours <= currentHours ? 'current' : ageHours <= delayedHours ? 'delayed' : 'stale';
    return { status, raw, parsed, ageHours };
  }

  function formatTimestamp(parsed) {
    if (!parsed) return 'Update time unavailable';
    if (parsed.dateOnly) {
      const date = parsed.date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
      return `${date}; time unavailable`;
    }
    const date = parsed.date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    const time = parsed.date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
    return `${date} at ${time}`;
  }

  function render(target, options) {
    const element = typeof target === 'string' ? document.querySelector(target) : target;
    if (!element) return null;
    const result = derive(options);
    const source = options && options.source ? String(options.source) : '';
    const timeText = formatTimestamp(result.parsed);
    element.className = `freshness freshness--${result.status}`;
    element.setAttribute('role', 'status');
    element.innerHTML = '';

    const badge = document.createElement('span');
    badge.className = 'freshness__status';
    badge.textContent = STATUS_LABELS[result.status];
    const details = document.createElement('span');
    details.className = 'freshness__details';
    details.textContent = source ? `${timeText} · Source: ${source}` : timeText;
    element.append(badge, details);
    return result;
  }

  global.SiteFreshness = { derive, formatTimestamp, parseTimestamp, render };
}(window));

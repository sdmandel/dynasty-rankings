const DEFAULT_REPO = 'sdmandel/dynasty-rankings';
const ALLOWED_TYPES = new Set(['bug', 'idea']);
const DEFAULT_ALLOWED_ORIGINS = [
  'https://baseball.stephenmandella.com',
];

function allowedOrigins(env) {
  const raw = env.ALLOWED_ORIGINS || DEFAULT_ALLOWED_ORIGINS.join(',');
  return raw.split(',').map(origin => origin.trim()).filter(Boolean);
}

function isLocalhost(origin) {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
}

function corsHeaders(request, env) {
  const origin = request.headers.get('Origin') || '';
  const allowed = allowedOrigins(env);
  const allowOrigin = allowed.includes(origin) || isLocalhost(origin) ? origin : allowed[0];
  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
  };
}

function jsonResponse(request, env, body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...corsHeaders(request, env),
      'Content-Type': 'application/json; charset=utf-8',
    },
  });
}

function clean(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

function issueBody(payload) {
  return [
    clean(payload.details, 5000) || '_No details provided._',
    '',
    '---',
    `Page: ${clean(payload.page, 500) || 'Unknown'}`,
    `Submitted: ${new Date().toISOString()}`,
    `User agent: ${clean(payload.userAgent, 500) || 'Unknown'}`,
  ].join('\n');
}

async function createIssue(env, payload) {
  const repo = env.GITHUB_REPO || DEFAULT_REPO;
  const type = ALLOWED_TYPES.has(payload.type) ? payload.type : 'bug';
  const prefix = type === 'idea' ? '[Idea]' : '[Bug]';
  const title = `${prefix} ${clean(payload.summary, 120)}`;

  const response = await fetch(`https://api.github.com/repos/${repo}/issues`, {
    method: 'POST',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Content-Type': 'application/json',
      'User-Agent': 'backyard-dynasty-feedback',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    body: JSON.stringify({
      title,
      body: issueBody(payload),
      labels: ['feedback', type],
    }),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || 'GitHub issue creation failed.');
  }
  return data;
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request, env) });
    }

    if (request.method !== 'POST') {
      return jsonResponse(request, env, { ok: false, error: 'POST required.' }, 405);
    }

    if (!env.GITHUB_TOKEN) {
      return jsonResponse(request, env, { ok: false, error: 'Feedback endpoint is not configured.' }, 500);
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return jsonResponse(request, env, { ok: false, error: 'Invalid JSON.' }, 400);
    }

    payload.type = ALLOWED_TYPES.has(payload.type) ? payload.type : 'bug';
    payload.summary = clean(payload.summary, 120);

    if (!payload.summary) {
      return jsonResponse(request, env, { ok: false, error: 'Summary is required.' }, 400);
    }

    try {
      const issue = await createIssue(env, payload);
      return jsonResponse(request, env, {
        ok: true,
        issueNumber: issue.number,
        issueUrl: issue.html_url,
      });
    } catch (error) {
      return jsonResponse(request, env, {
        ok: false,
        error: error.message || 'Feedback could not be sent.',
      }, 502);
    }
  },
};

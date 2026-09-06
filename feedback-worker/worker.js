const DEFAULT_REPO = 'sdmandel/dynasty-rankings';
const ALLOWED_TYPES = new Set(['bug', 'idea']);
const MAX_BODY_BYTES = 32768;
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
  const allowOrigin = allowed.includes(origin) || (env.ALLOW_LOCALHOST === 'true' && isLocalhost(origin)) ? origin : allowed[0];
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
    const origin = request.headers.get('Origin') || '';
    if (!allowedOrigins(env).includes(origin) && !(env.ALLOW_LOCALHOST === 'true' && isLocalhost(origin))) {
      return jsonResponse(request, env, { ok: false, error: 'Origin is not allowed.' }, 403);
    }
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request, env) });
    }

    if (request.method !== 'POST') {
      return jsonResponse(request, env, { ok: false, error: 'POST required.' }, 405);
    }

    if (!env.GITHUB_TOKEN) {
      return jsonResponse(request, env, { ok: false, error: 'Feedback endpoint is not configured.' }, 500);
    }

    if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('Content-Type') || '')) {
      return jsonResponse(request, env, { ok: false, error: 'JSON content type required.' }, 415);
    }
    if (Number(request.headers.get('Content-Length')) > MAX_BODY_BYTES) {
      return jsonResponse(request, env, { ok: false, error: 'Request is too large.' }, 413);
    }
    // Cloudflare supplies this header. No caller-controlled forwarded-for fallback.
    // Anonymous submissions have no account ID; a shared IP may share this allowance.
    try {
      const key = 'feedback:' + (request.headers.get('CF-Connecting-IP') || 'unknown');
      const user = await env.FEEDBACK_RATE.limit({ key });
      const site = user.success && await env.FEEDBACK_TOTAL_RATE.limit({ key: 'feedback' });
      if (!user.success || !site.success) {
        return jsonResponse(request, env, { ok: false, error: 'Too many requests. Try again in a minute.' }, 429);
      }
    } catch {
      return jsonResponse(request, env, { ok: false, error: 'Feedback is temporarily unavailable.' }, 503);
    }

    let payload;
    try {
      const reader = request.body?.getReader();
      const chunks = [];
      let length = 0;
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          length += value.byteLength;
          if (length > MAX_BODY_BYTES) {
            await reader.cancel();
            return jsonResponse(request, env, { ok: false, error: 'Request is too large.' }, 413);
          }
          chunks.push(value);
        }
      }
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      payload = JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      return jsonResponse(request, env, { ok: false, error: 'Invalid JSON.' }, 400);
    }

    if (!payload || typeof payload !== 'object' || Array.isArray(payload) ||
        typeof payload.summary !== 'string' ||
        ['details', 'page', 'userAgent', 'type'].some(key => payload[key] != null && typeof payload[key] !== 'string')) {
      return jsonResponse(request, env, { ok: false, error: 'Expected a feedback object with a text summary.' }, 400);
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
        error: 'Feedback could not be sent. Please try again later.',
      }, 502);
    }
  },
};

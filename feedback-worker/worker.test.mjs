import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const source = await readFile(new URL('./worker.js', import.meta.url), 'utf8');
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const origin = 'https://baseball.stephenmandella.com';
const env = () => ({ GITHUB_TOKEN: 'fixture', FEEDBACK_RATE: { limit: async () => ({ success: true }) },
                    FEEDBACK_TOTAL_RATE: { limit: async () => ({ success: true }) } });
function request(body, headers = {}) {
  return new Request('https://worker.invalid', { method: 'POST', body,
    headers: { Origin: origin, 'Content-Type': 'application/json', ...headers } });
}

test('reject malformed, non-object, oversized, and disallowed-origin submissions without GitHub', async () => {
  globalThis.fetch = () => { throw new Error('Unexpected external request'); };
  for (const body of ['null', '[]', 'true', '"text"', '{}', '{', '{"summary":{}}']) {
    assert.equal((await worker.fetch(request(body), env())).status, 400);
  }
  assert.equal((await worker.fetch(request('{}', { Origin: 'https://evil.invalid' }), env())).status, 403);
  assert.equal((await worker.fetch(request('{}', { Origin: '' }), env())).status, 403);
  assert.equal((await worker.fetch(request('{}', { 'Content-Type': 'text/plain' }), env())).status, 415);
  assert.equal((await worker.fetch(request('x'.repeat(32769)), env())).status, 413);
  assert.equal((await worker.fetch(request('{}', { 'Content-Length': '32769' }), env())).status, 413);
});

test('rate denial and unavailable bindings fail closed', async () => {
  for (const field of ['FEEDBACK_RATE', 'FEEDBACK_TOTAL_RATE']) {
    const config = env();
    config[field].limit = async () => ({ success: false });
    assert.equal((await worker.fetch(request('{"summary":"hi"}'), config)).status, 429);
    delete config[field];
    assert.equal((await worker.fetch(request('{"summary":"hi"}'), config)).status, 503);
  }
});

test('valid feedback creates one mocked issue; upstream errors are generic', async () => {
  let calls = 0;
  globalThis.fetch = async (url, init) => {
    calls++;
    assert.equal(url, 'https://api.github.com/repos/sdmandel/dynasty-rankings/issues');
    assert.equal(JSON.parse(init.body).title, '[Idea] Test');
    return Response.json({ number: 42, html_url: 'https://example.invalid/42' });
  };
  assert.equal((await worker.fetch(request('{"type":"idea","summary":"Test"}'), env())).status, 200);
  assert.equal(calls, 1);
  globalThis.fetch = async () => Response.json({ message: 'private upstream details' }, { status: 500 });
  const response = await worker.fetch(request('{"summary":"Test"}'), env());
  assert.equal(response.status, 502);
  assert.ok(!(await response.text()).includes('private'));
});

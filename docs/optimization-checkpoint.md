# September 2026 optimization checkpoint

Parent execution log: `fantrax/docs/execution-checkpoint.md`. Work is isolated
from the original dirty checkout on `codex/site-optimization`.

Deployed September 5–6 (site code `3e7c421`, followed by automated data builds).
Both history manifests are now live, as are daily stats and operational feeds.
The latest observed three Pages deployments passed. Verification: 274 local
pytest tests, 3 mocked Worker tests, and offline browser interactions pass.
Only the separately deployed Worker remains blocked as described below.

Implemented and verified:

- Simple rankings renders selected columns only. Offline Chromium at 4× CPU:
  9,210 nodes (audit baseline 19,753), 468 ms initial 200 rows, 253 ms search.
  `tests/browser_smoke.py` covers mode/position filters, pins, search links, and
  modals on rankings, depth, and prospects. It aborts all external requests.
  Recheck with September 6 data: 494 ms initial rows / 308 ms search; no errors.
- Histories use a version-1 manifest and 64 content-addressed buckets. Keep old
  buckets: cached manifests must continue to resolve. Full legacy JSON remains
  for older clients; new clients fall back only when the manifest is absent.
  Producers must publish the manifest and its referenced buckets together.
  Measured live gzip GET: Soto bucket 11,285 wire bytes, versus 536,743 for the
  full compact legacy history. Median decoded dynasty bucket: 57,746 bytes.
- Builders accept explicit source/output directories; unchanged dynasty history
  is reused. MLB QS caches successful boxscores for seven days, then refreshes
  for scoring corrections. MiLB caching is in the parent bot.
- CI is reusable; Pages uploads the tested checkout and deploys that same
  artifact without checking out a mutable branch again. JSON validation includes
  nested buckets. Browser smoke is explicit locally (Playwright required).
- Oracle contract tests no longer shadow one another and cover every team.
- Feedback validation, 32 KiB streaming body limit, and rate-limit bindings are
  locally tested with mocked GitHub calls. No real feedback was submitted.

Feedback deployment is **not complete**: Wrangler's saved login refresh failed
with HTTP 400 on September 5 CT. No working Cloudflare token was available in
the task environment. Deploy `feedback-worker/wrangler.toml` when authenticated;
both bindings must ship with the code (missing protection fails closed).
Limits are 5/IP/minute and 30 total/minute per Cloudflare location, not a global
abuse-proof quota. Shared IPs share an allowance. Origin checks are not identity
authentication. Localhost is opt-in via `ALLOW_LOCALHOST=true`.
Binding design follows the [Cloudflare Rate Limiting API documentation](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/).

Do not rebuild public data from stale local private inputs. Deployment should
rebase code onto current remote data, then let the production publishers build.

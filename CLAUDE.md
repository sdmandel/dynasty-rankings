# powerrankings/ — public site repo

This directory is a separate git repo (`sdmandel/dynasty-rankings`) deployed to baseball.stephenmandella.com via GH Pages.

**Follow `../CLAUDE.md` for all coding behavior, session-start ritual, orientation-before-reading, context-budget discipline, and PR-chunk rules.** Those apply here unchanged.

Repo-specific notes:
- HTML edits and `scripts/` edits are separate chunks. Don't bundle them.
- Use `/site-deploy` to commit + push. Never `git push` directly without confirmation.

## Team name changes (rename playbook)

`data/team_registry.json` is the single source of truth for team identity:
`team_key` is the stable internal id, `display_name` is the public name, and
`aliases` is every Fantrax name that franchise has ever used. Live data sources
(standings, rankings CSV, oracle CSV) pick up a Fantrax rename automatically; the
registry is the only thing that needs a human edit, because a rename requires a
decision: same franchise (keep `team_key`, preserve history) vs. a new one.

When a team is renamed:
1. In `data/team_registry.json`, set that franchise's `display_name` to the new
   name, append the new name to `aliases`, keep the old name in `aliases`, and
   **leave `team_key` unchanged** (this keeps franchise history in
   `franchises.json` / `dynasty_history` linked).
2. Run `scripts/normalize_team_names.py` to propagate the new display name across
   the JSON payloads (it rewrites every alias → display).
3. Regenerate derived tables/pages: `build_oracle_public.py`,
   `build_home_preview.py`, and `publish_site_tables.py`; the generated HTML pages
   (`roster_depth.html`, the `index.html` scatter) refresh on the next
   `update_depth_chart.py` run. Past weekly articles intentionally keep the old
   name as history — do not rewrite them.

Symptom of a missed rename: `build_oracle_public` raises `KeyError: '<old name>'`
(registry display has no matching row in the already-renamed standings/data).

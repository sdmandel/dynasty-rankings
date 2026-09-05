# Public site orientation

This is the independent `sdmandel/dynasty-rankings` Git repository, deployed to
https://baseball.stephenmandella.com/. The parent is the Python bot repository.
In the combined workspace, start with `../CONTEXT.md` and parent `AGENTS.md`.

- Keep public HTML routes flat and stable. Preserve historical weekly articles.
- Read `CLAUDE.md` for team rename rules. `data/team_registry.json` owns stable
  team identity; old article names are historical, not rename targets.
- Most `data/*.json`, `roster_depth.html`, and parts of `index.html` are generated
  by parent bot scripts. Fix their producer; manual edits will be overwritten.
- Page UI/shared styles: `assets/`. Weekly source: `templates/` plus parent
  `scripts/weekly_article.py`; deployment remains a separate publishing action.
- Site builders: `scripts/build_dynasty_rankings.py`, `fetch_season_stats.py`,
  `build_oracle_public.py`, `build_home_preview.py`. The bot loads these from
  its selected/cloned site checkout; preserve their callable contracts.
- `feedback-worker/` is separately deployed, not a backend hosted by Pages.
  Do not submit test feedback or polls to production during verification.
- Run `../.venv/bin/python -m pytest tests/ -q`. Static tests do not verify live
  feed age, browser performance, or successful bot execution.
- Check status in both repositories; stage only your changes. Local generated
  data can be much older than deployed data and must not be blindly published.

For the September 2026 audit and repair checkpoint, see
`../docs/audit-2026-09-05.md` (in the bot repository).

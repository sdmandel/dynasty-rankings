# powerrankings Site Structure

Static GH Pages site for league-facing pages and JSON payloads.

## Layout

- `*.html` at root: public page routes (kept flat to preserve stable URLs)
- `assets/`: shared CSS/JS
- `data/`: generated JSON payloads consumed by pages
- `media/raw/`: local source/reference files not used directly by page routes
- Large media can be referenced via absolute hosted URLs to avoid CI failures from missing local binaries.
- `tests/`: smoke/schema tests for static pages and payload contracts

## Hub IA conventions (`index.html`)

- `League`: preview-enabled `tool-tile` components
- `Analysis & Tools`: link-only `card` components (no preview boxes)

## Organization policy

- Prefer non-breaking organization changes first (docs/conventions/tests).
- Avoid moving route files unless redirects and references are updated together.

## Shared shell convention

- Every non-hub page should load `assets/site-shell.css` and `assets/site-shell.js`.
- The shared shell injects and normalizes the `"← The Hub"` backlink for `.site-header` and `.header` layouts.
- New weekly pages inherit this automatically from `templates/power_rankings_template.html`.

## Public Oracle payload

- `scripts/build_oracle_public.py` generates `data/oracle_public.json`.
- The public payload is team-level only and is intended to power public-facing Oracle views without exposing the private rankings CSV.

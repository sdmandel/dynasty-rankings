# League Votes Setup

This page is built for a static site with a tiny external backend.

## Why this shape

The static page can render the ballot and results, but it cannot securely decide whether a manager has already voted. That validation has to happen on the backend.

For a 12-team league, the cleanest model is:

1. Generate one unique ballot token per manager per poll
2. Share each manager a link like `polls.html?ballot=<token>`
3. Resolve that token server-side to exactly one manager
4. Upsert that manager's answers
5. Aggregate results for display

This avoids passwords, full auth, and manual manager selection.

## Minimal backend contract

The frontend expects `window.POLLS_CONFIG.backendBaseUrl` to point at a backend with these endpoints:

### `POST /resolve-ballot`

Request:

```json
{
  "poll_id": "2026-offseason-rules",
  "ballot_token": "abc123"
}
```

Response:

```json
{
  "manager_id": "vin-mazzaro-fan-club",
  "manager_name": "Vin Mazzaro fan club",
  "has_submitted": true,
  "submitted_at": "2026-10-02T01:12:00Z",
  "answers": {
    "keep_il_at_10": "yes",
    "minors_slots": "10"
  }
}
```

### `POST /submit-ballot`

Request:

```json
{
  "poll_id": "2026-offseason-rules",
  "ballot_token": "abc123",
  "answers": {
    "keep_il_at_10": "yes",
    "minors_slots": "10"
  }
}
```

Response:

```json
{
  "manager_id": "vin-mazzaro-fan-club",
  "manager_name": "Vin Mazzaro fan club",
  "has_submitted": true,
  "submitted_at": "2026-10-02T01:20:00Z",
  "answers": {
    "keep_il_at_10": "yes",
    "minors_slots": "10"
  }
}
```

### `GET /results?poll_id=2026-offseason-rules`

Response:

```json
{
  "total_ballots": 8,
  "questions": {
    "keep_il_at_10": {
      "total_votes": 8,
      "options": {
        "yes": 5,
        "no": 3
      }
    }
  }
}
```

## Supabase schema

You can implement the backend with one Edge Function or a couple of small functions. This schema is enough:

```sql
create table public.polls (
  id text primary key,
  title text not null,
  opens_at timestamptz,
  closes_at timestamptz,
  allow_resubmission boolean not null default true
);

create table public.poll_voters (
  poll_id text not null references public.polls(id) on delete cascade,
  manager_id text not null,
  manager_name text not null,
  ballot_token text not null unique,
  primary key (poll_id, manager_id)
);

create table public.poll_ballots (
  poll_id text not null references public.polls(id) on delete cascade,
  manager_id text not null,
  answers_json jsonb not null,
  submitted_at timestamptz not null default now(),
  primary key (poll_id, manager_id)
);

create index poll_ballots_poll_id_idx on public.poll_ballots (poll_id);
```

## Enforcement

- One vote per manager is enforced by `primary key (poll_id, manager_id)` on `poll_ballots`.
- One token per manager is enforced by `primary key (poll_id, manager_id)` plus `ballot_token unique`.
- If you want ballots to be editable until the deadline, use an upsert into `poll_ballots`.
- If you want strict one-and-done voting, reject updates after the first insert.

## Practical recommendation

Use manager-specific ballot links, not a dropdown of names and not a shared passcode.

The dropdown approach is easy to spoof. Shared passcodes are better, but still add friction and support overhead. Unique ballot links are the right tradeoff for a 12-manager league.

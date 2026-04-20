create table if not exists public.polls (
  id text primary key,
  title text not null,
  opens_at timestamptz,
  closes_at timestamptz,
  allow_resubmission boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.poll_voters (
  poll_id text not null references public.polls(id) on delete cascade,
  manager_id text not null,
  manager_name text not null,
  ballot_token text not null unique,
  created_at timestamptz not null default now(),
  primary key (poll_id, manager_id)
);

create table if not exists public.poll_ballots (
  poll_id text not null references public.polls(id) on delete cascade,
  manager_id text not null,
  answers_json jsonb not null,
  submitted_at timestamptz not null default now(),
  primary key (poll_id, manager_id)
);

create index if not exists poll_ballots_poll_id_idx on public.poll_ballots (poll_id);

create or replace view public.poll_results as
select
  b.poll_id,
  q.key as question_id,
  q.value as option_id,
  count(*)::int as vote_count
from public.poll_ballots b
cross join lateral jsonb_each_text(b.answers_json) as q(key, value)
group by b.poll_id, q.key, q.value;

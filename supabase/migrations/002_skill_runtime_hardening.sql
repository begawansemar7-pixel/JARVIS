create table if not exists public.jarvis_skill_idempotency (
  idempotency_key text not null,
  operation text not null,
  sprint_id text not null references public.jarvis_skill_sprints(sprint_id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (idempotency_key, operation)
);

create index if not exists idx_jarvis_skill_idempotency_sprint
  on public.jarvis_skill_idempotency(sprint_id);

create table if not exists public.jarvis_skill_events (
  event_id text primary key,
  event_type text not null,
  sprint_id text references public.jarvis_skill_sprints(sprint_id) on delete set null,
  skill_id text,
  learner_id text,
  idempotency_key text,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index if not exists idx_jarvis_skill_events_sprint
  on public.jarvis_skill_events(sprint_id, occurred_at desc);
create index if not exists idx_jarvis_skill_events_learner
  on public.jarvis_skill_events(learner_id, occurred_at desc);

create table if not exists public.jarvis_tania_capability_gaps (
  gap_id text primary key,
  learner_id text not null,
  capability_id text,
  required_skill_id text not null,
  priority text,
  context jsonb not null default '{}'::jsonb,
  status text not null default 'open',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_jarvis_tania_gaps_learner
  on public.jarvis_tania_capability_gaps(learner_id, status);

create or replace function public.jarvis_tania_gaps_touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;

drop trigger if exists jarvis_tania_gaps_updated_at on public.jarvis_tania_capability_gaps;
create trigger jarvis_tania_gaps_updated_at before update on public.jarvis_tania_capability_gaps
for each row execute function public.jarvis_tania_gaps_touch_updated_at();

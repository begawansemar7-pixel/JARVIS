create table if not exists public.jarvis_skill_sprints (
  sprint_id text primary key,
  skill_id text not null,
  learner_id text not null,
  state text not null,
  hours_completed double precision not null default 0,
  evidence jsonb not null default '[]'::jsonb,
  assessment jsonb,
  version integer not null default 1,
  updated_at timestamptz not null default now()
);
create index if not exists idx_jarvis_skill_sprints_learner on public.jarvis_skill_sprints(learner_id);
create index if not exists idx_jarvis_skill_sprints_skill on public.jarvis_skill_sprints(skill_id);

create or replace function public.jarvis_skill_sprints_touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;

drop trigger if exists jarvis_skill_sprints_updated_at on public.jarvis_skill_sprints;
create trigger jarvis_skill_sprints_updated_at before update on public.jarvis_skill_sprints
for each row execute function public.jarvis_skill_sprints_touch_updated_at();

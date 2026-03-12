-- Run this in Supabase SQL Editor to create tables.

create table if not exists public.candidates (
  id uuid primary key default gen_random_uuid(),
  name text not null default '',
  email text not null default '',
  resume_text text not null default '',
  resume_url text,
  created_at timestamptz not null default now()
);

-- If table already exists, add column: alter table public.candidates add column if not exists resume_url text;
-- Create storage bucket named "resume" in Supabase Dashboard > Storage, set to public if you want direct links.

create table if not exists public.evaluations (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.candidates(id) on delete cascade,
  requirement_id text not null,
  passed boolean not null,
  reason text not null default '',
  created_at timestamptz not null default now()
);

create index if not exists evaluations_candidate_id on public.evaluations(candidate_id);
create index if not exists evaluations_requirement_id on public.evaluations(requirement_id);

-- Requirements: admin can add/edit/delete; agent uses these for evaluation.
create table if not exists public.requirements (
  id text primary key,
  label text not null,
  prompt text not null,
  weight int not null default 1,
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists requirements_sort on public.requirements(sort_order);

-- Seed default requirements (run once)
insert into public.requirements (id, label, prompt, weight, sort_order) values
  ('phd_ml', 'PhD or PhD-level experience with machine learning', 'Does the candidate have a PhD or PhD-level experience with machine learning? Consider equivalent research experience (e.g. first-author top-tier ML papers, years in research).', 1, 0),
  ('generative_sota', 'Research on SOTA generative models (past 3 years)', 'In the past three years, has the candidate done research or impactful innovative work on state-of-the-art generative models, such as LLMs, flow-matching, or diffusion-based models (beyond just applying existing models)?', 1, 1),
  ('built_from_scratch', 'Hands-on experience building generative models from scratch', 'Has the candidate been the main driver in building generative models from scratch (hands-on implementation, not only using existing libraries)?', 1, 2),
  ('multimodal_visual', 'Research on multimodal models including visual (past 3 years)', 'In the past three years, has the candidate done research on multimodal models that include visual modalities?', 1, 3),
  ('audio_experience', 'Experience working with audio', 'Does the candidate have experience working with audio (e.g. speech, music, audio ML)?', 1, 4),
  ('job_stability', 'Reasonable job tenure (~1 year per job minimum)', 'Has the candidate not switched jobs too often? Prefer roughly at least 1 year per role; flag if many very short stints.', 1, 5)
on conflict (id) do nothing;

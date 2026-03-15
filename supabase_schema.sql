-- Job Bucket Redesign schema.
-- Run in Supabase SQL Editor. Drop old tables first if migrating.

-- 1. Job Buckets
create table if not exists public.job_buckets (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  job_description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Per-bucket requirements
create table if not exists public.bucket_requirements (
  id uuid primary key default gen_random_uuid(),
  bucket_id uuid not null references public.job_buckets(id) on delete cascade,
  label text not null,
  prompt text not null,
  weight int not null default 1,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists bucket_requirements_bucket on public.bucket_requirements(bucket_id);

-- 3. Candidates discovered within a bucket
create table if not exists public.bucket_candidates (
  id uuid primary key default gen_random_uuid(),
  bucket_id uuid not null references public.job_buckets(id) on delete cascade,
  name text not null default '',
  headline text not null default '',
  location text not null default '',
  summary text not null default '',
  skills jsonb not null default '[]',
  relevance_percentage int,
  status text not null default 'discovered',
  created_at timestamptz not null default now()
);
create index if not exists bucket_candidates_bucket on public.bucket_candidates(bucket_id);

-- 4. Links associated with a candidate
create table if not exists public.candidate_links (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.bucket_candidates(id) on delete cascade,
  url text not null,
  label text not null default '',
  source text not null default 'discovery',
  created_at timestamptz not null default now()
);
create index if not exists candidate_links_candidate on public.candidate_links(candidate_id);

-- 5. Per-requirement evaluations for a candidate
create table if not exists public.candidate_evaluations (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.bucket_candidates(id) on delete cascade,
  requirement_id uuid not null references public.bucket_requirements(id) on delete cascade,
  passed boolean not null,
  reason text not null default '',
  created_at timestamptz not null default now()
);
create index if not exists candidate_evaluations_candidate on public.candidate_evaluations(candidate_id);
create index if not exists candidate_evaluations_requirement on public.candidate_evaluations(requirement_id);

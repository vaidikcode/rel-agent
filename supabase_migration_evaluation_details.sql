-- Run in Supabase SQL Editor if bucket_candidates already exists without evaluation_details.
alter table public.bucket_candidates add column if not exists evaluation_details jsonb;

# Candidate requirement agent

React frontend + FastAPI backend with a LangGraph agent that evaluates candidates against requirements (yes/no + reason per requirement). **Evaluate**: upload one or more resumes; name/email are extracted from each. **Ranking**: candidates by total score (configurable weight per requirement). **Admin**: add/edit/delete requirements and set weights.

## Stack

- **Frontend**: React (Vite), shadcn/ui (dark), React Router.
- **Backend**: FastAPI in `api/`, LangGraph agent with one node per requirement, Gemini (`gemini-flash-latest`).
- **Resume parsing**: `pdfplumber` (PDF) and `python-docx` (DOCX); name/email extracted from text via LLM.
- **DB**: Supabase (candidates, evaluations, requirements). Run `supabase_schema.sql` in the SQL Editor (creates tables and seeds default requirements). If the table already exists, run: `alter table public.candidates add column if not exists resume_url text;`
- **Storage**: Create a Supabase Storage bucket named **resume** (Dashboard → Storage). Set it to **public** if you want direct “View resume” links. Resumes are uploaded there after evaluation.

## Env

Copy `.env.example` to `.env` and set:

- `GOOGLE_API_KEY` or `GEMINI_API_KEY` – for Gemini.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`) – for saving/ranking.

## Run locally

1. **Backend** (from repo root):
   ```bash
   npm run api
   ```
   Serves FastAPI at http://127.0.0.1:8000.

2. **Frontend** (another terminal):
   ```bash
   npm install
   npm run dev
   ```
   Vite proxies `/api` to the backend.

3. Open the app: **Evaluate** (upload one or more resumes), **Ranking** (click a row to see verdicts; click a verdict to see reason), **Admin** (manage requirements and weights).

## Deploy (Vercel)

- Frontend: build from root; output is `dist`.
- API: `api/index.py` exposes the FastAPI app. The repo includes a rewrite so `/api/*` goes to the API. Ensure env vars are set in the Vercel project for the API (Python runtime).

## Requirements (nodes)

Requirements are stored in Supabase (`requirements` table). Defaults are seeded by `supabase_schema.sql`. Use **Admin** to add, edit, delete, and set weights. Each requirement is one LangGraph node; Gemini returns **Yes/No** and a short **reason**.

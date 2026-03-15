# Mirelo – Job Bucket Agent

React frontend + FastAPI backend. Discover candidates via web search, evaluate them against bucket requirements using AI, and view rich profile details fetched from multiple sources.

## Stack

- **Frontend**: React (Vite), shadcn/ui (dark), React Router.
- **Backend**: FastAPI (`api/`), LangGraph agents (Gemini), Supabase.
- **Discovery**: Serper web search → Gemini extracts structured candidate profiles with multiple links.
- **Evaluation**: Type-aware link fetching → Gemini evaluates against per-requirement prompts.

## Link-type-aware fetching

Each candidate link is classified and fetched with the right tool:

| Link type | Fetcher | Env vars needed |
|-----------|---------|-----------------|
| **GitHub** | Official REST API (user + repos JSON) | `GITHUB_TOKEN` (optional, higher rate limit) |
| **Personal sites & blogs** | Cloudflare Browser Rendering `/crawl` (free tier: 10 min/day) → plain HTTP fallback | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` (optional) |
| **Research papers / PDFs** | Local PDF extraction via pdfplumber | — (built-in) |
| **LinkedIn** | Datablist API → Serper search fallback | `DATABLIST_API_KEY` (optional) |
| **Other websites** | Cloudflare / plain HTTP | — |

Fetched content is **persisted** in `candidate_link_fetches` (Supabase) so it's reused across evaluation runs and displayed to hirers on the candidate detail page.

## DB

Run `supabase_schema.sql` in the Supabase SQL Editor. Tables:

1. `job_buckets` – buckets with title + job description
2. `bucket_requirements` – per-bucket requirements (label, prompt, weight)
3. `bucket_candidates` – discovered/manual candidates
4. `candidate_links` – URLs per candidate (with `link_type`)
5. `candidate_link_fetches` – persisted fetched content per link
6. `candidate_evaluations` – per-requirement pass/fail verdicts

## Env

Copy `.env.example` to `.env` and set:

- `GOOGLE_API_KEY` or `GEMINI_API_KEY` – required (Gemini for discovery + evaluation)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` – required (data persistence)
- `SERPER_API_KEY` – required (candidate discovery web search)
- `GITHUB_TOKEN` – optional (raises GitHub API rate limit from 60 to 5000 req/hr)
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` – optional (Cloudflare crawl for blogs/portfolios)
- `DATABLIST_API_KEY` – optional (LinkedIn profile data without ban risk)

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

3. Open the app → create a bucket with a job description → add requirements → Discover → Evaluate candidates.

## Deploy (Vercel)

- Frontend: build from root; output is `dist`.
- API: `api/index.py` exposes the FastAPI app. The repo includes a rewrite so `/api/*` goes to the API. Ensure env vars are set in the Vercel project.

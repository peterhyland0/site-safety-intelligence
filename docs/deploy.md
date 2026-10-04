# Deploying: Vercel (website) + Modal (API and data)

The React site is static and lives on Vercel. The Python API needs the ~1.2 GB DuckDB warehouse and a nightly
rebuild (about 10 GB of downloads), which don't fit Vercel's serverless limits, so they run on Modal. Vercel
forwards `/api/*` to Modal, so the browser sees one site. The GC's decisions live in a small Postgres
(any provider; Supabase's free tier is plenty).

## One-time setup (account owner)
1. **Modal CLI login**, so this repo can deploy into your workspace:
   `uv run modal setup`
2. **Postgres** for the `app` schema: create a database and copy its connection string (use the pooled URL
   on Supabase). The app creates its tables on first start.
3. **Secrets** (created by you; values never go in the repo):
   ```bash
   uv run modal secret create ssi-db DATABASE_URL='postgresql://...'
   uv run modal secret create ssi-glm SSI_LLM_PROVIDER=openai_compat \
       SSI_LLM_FOREMAN_BASE_URL='https://<workspace>--ep-glm-5-3-server.us-west.modal.direct/v1' \
       SSI_LLM_ADJUDICATOR_BASE_URL='https://<workspace>--ep-deepseek-v4-1-flash-server.us-west.modal.direct/v1' \
       SSI_LLM_MODAL_KEY='wk-...' SSI_LLM_MODAL_SECRET='ws-...'
   uv run modal secret create ssi-langsmith LANGSMITH_API_KEY='...' LANGSMITH_PROJECT=site-safety-intelligence LANGSMITH_TRACING=true
   uv run modal secret create ssi-jev JEV_API_KEY='...'   # from console.typesafe.ai/keys
   uv run modal secret create ssi-tavily TAVILY_API_KEY='...' SSI_PROFILE_BACKEND=tavily   # web check + profiles
   ```
   With `ssi-jev`, Jev adjudicates uncertain matches without red flags and DeepSeek the red-flagged ones
   ([why](adjudicator.md)). `ssi-tavily` runs the web check ([web-check.md](web-check.md)) and company profiles
   ([company-profile.md](company-profile.md)) on Tavily and the adjudicator LLM. For Claude-backed profiles instead
   (~$0.20 each), create `ssi-anthropic` with `ANTHROPIC_API_KEY` and deploy with `SSI_WITH_ANTHROPIC=1` added. Use TypeSafe's own API (`api.typesafe.ai`, the default): lookalike sites resell
   Jev access through their own servers.
4. **Accounts.** Sign-in is invite-only (there is no sign-up page), and accounts live in the app database. Create
   them from your machine against the hosted database; the password is asked for at the prompt:
   ```bash
   DATABASE_URL='postgresql://...' uv run python -m scripts.add_user reviewer@example.com --name "Reviewer"
   ```
   `--reset` sets a new password and `--disable` blocks an account; both sign it out everywhere. Each person's
   foreman chats are private to their account, so reviewers sharing one account share its chats.

## Data on Modal
```bash
# reference files that are downloaded by hand (ITA injury filings, CSLB) go up from your machine
uv run modal volume put ssi-data data/raw/reference/osha_ita/utf8 /raw/reference/osha_ita/utf8
uv run modal volume put ssi-data data/raw/reference/ca_cslb/cslb_master.csv /raw/reference/ca_cslb/cslb_master.csv
# download OSHA + WA/OR licences on Modal and build the warehouse (~10 min the first time)
cd web && npm run build && cd ..
uv run modal run modal_app.py::refresh
```

## Deploy the API (and the nightly refresh)
```bash
make deploy        # builds web/dist, then deploys with ssi-db, ssi-glm, ssi-langsmith, ssi-jev and ssi-tavily
uv run modal run modal_app.py::seed_demo        # demo project against the deployed data
```
Each secret is named by an `SSI_WITH_*` flag (list in [modal_app.py](../modal_app.py)); deploy without one by
overriding the list, e.g. `make deploy SSI_SECRETS="SSI_WITH_DB=1 SSI_WITH_GLM=1"`. `ssi-db` is required: without
it the API has no database. `modal deploy` prints the API URL, e.g.
`https://<workspace>--site-safety-intelligence-web.modal.run`.
Set `SSI_MIN_CONTAINERS=1` on deploy while reviewers are looking, to avoid cold starts.

## Deploy the website on Vercel
1. `web/vercel.json` forwards `/api/*` to `peterhyland101210--site-safety-intelligence-web.modal.run`; another
   workspace puts its own Modal URL there.
2. In the Vercel dashboard: **Add New → Project → import `peterhyland0/site-safety-intelligence`**, set
   **Root Directory = `web`** (framework: Vite). Deploy.
3. Settings → Deployment Protection: turn off Vercel Authentication if reviewers should only see the app's own
   sign-in page.

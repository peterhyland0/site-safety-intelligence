# Site Safety Intelligence — common tasks
.PHONY: setup download build dev api web test eval eval-rules eval-adjudication eval-jev-search seed-demo add-user deploy refresh

setup:            ## Python env, local Postgres databases, web deps
	uv sync
	createdb ssi 2>/dev/null || true
	createdb ssi_test 2>/dev/null || true
	cd web && npm install

download:         ## OSHA enforcement zips + WA/OR licence lists (ITA/CSLB: see README)
	uv run python -m ssi.pipeline.download --osha --licences

build:            ## Build the warehouse (about 1-2 minutes)
	uv run python -m ssi.pipeline.build

api:              ## API on :8000 (serves web/dist if built)
	uv run uvicorn ssi.api.app:app --reload --port 8000

web:              ## Vite dev server on :5173 (proxies /api to :8000)
	cd web && npm run dev

dev:              ## API + web together
	$(MAKE) -j2 api web

test:
	uv run pytest

eval:             ## Matching, per-rule and foreman evals (foreman eval spends API credit)
	uv run python -m eval.matching.run
	uv run python -m eval.rules.run
	uv run python -m eval.foreman.run

eval-rules:       ## Each matching rule graded on its own (about 5 minutes, no model calls)
	uv run python -m eval.rules.run

eval-adjudication: ## Adjudicators compared on uncertain matches, both samples (answers cached; each model needs its key/URL)
	uv run python -m eval.adjudication.run --seed 7 $(EVAL_LLMS)
	uv run python -m eval.adjudication.run --seed 11 $(EVAL_LLMS)

eval-jev-search:  ## Jev as the search: names compared with every record of a small test set (answers cached)
	uv run python -m eval.jev_search.run

EVAL_LLMS = --llm glm-5.3=env:SSI_LLM_FOREMAN_BASE_URL --llm kimi-k3=env:SSI_LLM_ADJUDICATOR_KIMI_3

seed-demo:        ## Create the demo project through the real API
	uv run python -m scripts.seed_demo

add-user:         ## Create a sign-in account: make add-user EMAIL=pat@example.com NAME="Pat Lee"
	uv run python -m scripts.add_user "$(EMAIL)" $(if $(NAME),--name "$(NAME)")

refresh:          ## Download + build on Modal
	cd web && npm run build
	uv run modal run modal_app.py::refresh

deploy:           ## Deploy web app + nightly refresh to Modal
	cd web && npm run build
	uv run modal deploy modal_app.py

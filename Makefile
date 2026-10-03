# Site Safety Intelligence — common tasks
.PHONY: setup download build dev api web test eval seed-demo add-user deploy refresh

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

eval:             ## Matching + foreman evals (foreman eval spends API credit)
	uv run python -m eval.matching.run
	uv run python -m eval.foreman.run

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

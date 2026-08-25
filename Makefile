.PHONY: install demo api web dev clean

install:            ## install backend + frontend deps
	cd backend && uv sync
	cd frontend && npm install

demo:               ## run the whole backend loop end-to-end (no UI needed)
	cd backend && uv run python -m app.demo

api:                ## backend API on :8137
	cd backend && uv run uvicorn app.api:app --port 8137 --reload

web:                ## frontend dev server on :5173 (proxies to :8137)
	cd frontend && npm run dev

dev:                ## run API + web together
	@echo "Starting API on :8137 and web on :5173 …"
	@(cd backend && uv run uvicorn app.api:app --port 8137 >/tmp/creditloop_api.log 2>&1 &) ; \
	 cd frontend && npm run dev

build:              ## build the SPA (served by the API for single-service deploy)
	cd frontend && npm run build

serve:              ## single-service: API serves the built dashboard too (:8137)
	cd backend && uv run uvicorn app.api:app --host 0.0.0.0 --port 8137

clean:
	cd backend && rm -rf data/creditloop.db data/receipts data/*.json

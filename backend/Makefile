.PHONY: install demo api data judge reconcile fail-payout gsp-down clean

install:      ## install backend deps with uv
	uv sync

demo:         ## run the whole loop end-to-end and print the report
	uv run python -m app.demo

fail-payout:  ## demo: inject a payout timeout, then reconcile
	uv run python -m app.demo --fail-payout

gsp-down:     ## demo: run judgment with the GSP offline (PROVISIONAL verdicts)
	uv run python -m app.demo --gsp-down

data:         ## (re)generate the 200-claim synthetic dataset + receipts
	uv run python -m app.synthetic

api:          ## serve the dashboard API on :8137
	uv run uvicorn app.api:app --port 8137 --reload

clean:        ## remove generated data
	rm -rf data/creditloop.db data/receipts data/*.json

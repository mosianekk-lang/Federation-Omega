.PHONY: test eval run compile manifest clean

test:
	pytest -q

eval:
	python evals/run_local.py

run:
	PORT=$${PORT:-8421} python main.py

compile:
	python -m compileall -q modisa_v2 tests scripts evals

manifest:
	python scripts/build_manifest.py

clean:
	rm -rf .pytest_cache **/__pycache__ evals/results/latest.json

SHELL := /bin/bash

.PHONY: help install dev test lint format typecheck build serve run clean

help:
	@echo "AgentGraph - Agent runtime for business outcomes"
	@echo ""
	@echo "Targets:"
	@echo "  install     install workspace + dev deps via uv"
	@echo "  dev         install with all optional extras"
	@echo "  test        run pytest"
	@echo "  lint        run ruff"
	@echo "  format      run ruff --fix + format"
	@echo "  typecheck   run mypy"
	@echo "  serve       launch agentgraph-server on :8080"
	@echo "  run         run an example (usage: make run EXAMPLE=examples/sales_ops/lead_qual.py)"
	@echo "  clean       remove build artifacts and caches"

install:
	uv sync --all-packages

dev:
	uv sync --all-packages --all-extras

test:
	uv run --project packages/runtime pytest -q

lint:
	uv run --project . ruff check .

format:
	uv run --project . ruff check --fix .
	uv run --project . ruff format .

typecheck:
	uv run --project . mypy packages verticals

serve:
	uv run --project packages/server agentgraph-server

run:
	uv run --project . python $(EXAMPLE)

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__ **/*.egg-info dist build

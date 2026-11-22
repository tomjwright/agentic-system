# AGENTS.md

Singapore running and road-cycling route creator (spec: issue #1). Shared standards
live in `tomjwright/home` `AGENTS.md`; this file adds the rules for this repo.

## Layout

- `feasibility/`: the issue #2 feasibility experiment (uv project). Real HeiGIT,
  OneMap and NParks data, no agent or framework. Results in `feasibility/EVIDENCE.md`.

## Rules

- `HEIGIT_API_KEY` stays server side: only `route_feasibility/heigit.py` reads it, only
  as the `Authorization` header to `api.heigit.org`. Never print, log, commit or record
  it; recorded fixtures are response bodies only.
- Tests never call a live provider. They replay recorded real responses through
  `httpx.MockTransport` (`feasibility/tests/test_cli.py`).
- Live runs are manual and bounded: `feasibility/scripts/run_live_cases.sh` makes at
  most 32 HeiGIT requests (free plan: 2000 directions a day, 40 a minute).
- Downloaded datasets go in `feasibility/data/` (git-ignored).

## Checks

```bash
cd feasibility
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
```

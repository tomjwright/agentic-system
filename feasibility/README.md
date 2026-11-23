# Route feasibility (issue #2)

A small experiment that asks: can real HeiGIT routing, OneMap place search and NParks
green data produce a bounded Singapore loop, such as a 60-70 km road ride from Avenue
South Residence with an identifiable green section? No agent, no framework. The
findings and the go / no-go recommendation are in [EVIDENCE.md](EVIDENCE.md).

## What it does

`feasibility route` resolves the start with OneMap (and stops for confirmation when the
match is ambiguous), asks HeiGIT for a bounded list of round-trip candidates with fixed
seeds, and measures each one: distance against the target, loop closure, Singapore
bounds, repeated ground, surfaces, NParks green sections, and contact with expressways,
slip roads, road tunnels and `bicycle=no` ways. It writes a Markdown report and, for
the accepted candidate, GeoJSON and GPX with the same points.

| file | what it holds |
| --- | --- |
| `src/route_feasibility/cli.py` | the commands and the candidate loop |
| `src/route_feasibility/heigit.py` | HeiGIT Directions call and response normalization (the only use of the key) |
| `src/route_feasibility/onemap.py` | OneMap search and the confirmation rule |
| `src/route_feasibility/checks.py` | distance targets, loop and boundary validation, repeated ground |
| `src/route_feasibility/green.py` | NParks Tracks normalization and green-section matching |
| `src/route_feasibility/restrictions.py` | near / on checks against restricted OSM roads |
| `src/route_feasibility/report.py`, `gpx.py` | the report and the GPX |
| `src/route_feasibility/datasets.py` | data.gov.sg downloads |
| `scripts/` | OSM extraction and the live case list |

## Run it

```bash
uv sync
uv run feasibility fetch-data --data-dir data          # data.gov.sg, no key
curl -LO https://download.bbbike.org/osm/bbbike/Singapore/Singapore.osm.pbf
uv run --with osmium python scripts/extract_restricted_ways.py Singapore.osm.pbf data/
export HEIGIT_API_KEY=...                               # never commit or print it
uv run feasibility route --name core-ride-60-70km --activity ride \
    --start "avenue south residence" --distance 60-70 \
    --round-trip --seeds 1,2,3,4,5 --require-green --out evidence
./scripts/run_live_cases.sh                             # every case in EVIDENCE.md
```

`--distance 10` accepts 9-11 km; `--distance 60-70` accepts exactly 60-70 km.
Exit codes: 0 accepted, 1 no candidate met the checks, 2 no key, 3 start needs
confirmation (pass `--confirm "<OneMap name>"`).

## Checks

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
```

Tests replay recorded real HeiGIT, OneMap and NParks responses; they never call a
live provider and need no key.

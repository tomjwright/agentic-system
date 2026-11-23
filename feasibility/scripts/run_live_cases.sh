#!/usr/bin/env bash
# Every live case in EVIDENCE.md. Needs HEIGIT_API_KEY and `feasibility fetch-data`
# (plus data/restricted_ways.geojson, see README). At most 32 HeiGIT requests.
set -u
cd "$(dirname "$0")/.."
run() { uv run feasibility route --out evidence "$@"; }

run --name core-ride-60-70km --activity ride --start "avenue south residence" \
    --distance 60-70 --round-trip --seeds 1,2,3,4,5 --require-green

run --name run-5km-avenue-south --activity run --start "avenue south residence" \
    --distance 5 --round-trip --seeds 1,2,3
run --name run-10km-avenue-south --activity run --start "avenue south residence" \
    --distance 10 --round-trip --seeds 1,2,3
run --name run-5km-east-coast-park --activity run --start "east coast park" \
    --confirm "EAST COAST PARK" --distance 5 --round-trip --seeds 1,2,3
run --name run-10km-bishan-amk-park --activity run --start "bishan-ang mo kio park" \
    --confirm "BISHAN - ANG MO KIO PARK (POND GARDENS)" --distance 10 --round-trip --seeds 1,2,3

run --name ride-20km-marina-barrage --activity ride --start "marina barrage" \
    --distance 20 --round-trip --seeds 1,2,3
run --name ride-20km-east-coast-park --activity ride --start "east coast park" \
    --confirm "EAST COAST PARK" --distance 20 --round-trip --seeds 1,2,3
run --name ride-50km-bishan-amk-park --activity ride --start "bishan-ang mo kio park" \
    --confirm "BISHAN - ANG MO KIO PARK (POND GARDENS)" --distance 50 --round-trip --seeds 1,2,3
run --name ride-50km-jurong-lake-gardens --activity ride --start "jurong lake gardens" \
    --confirm "PASSION WAVE @ JURONG LAKE GARDENS" --distance 50 --round-trip --seeds 1,2,3
run --name ride-50km-pasir-ris-park --activity ride --start "pasir ris park" \
    --confirm "PASIR RIS BEACH PARK" --distance 50 --round-trip --seeds 1,2,3

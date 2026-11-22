#!/usr/bin/env bash
# Every live case in EVIDENCE.md. Needs HEIGIT_API_KEY and `feasibility fetch-data`
# (plus data/restricted_ways.geojson, see README). At most 37 HeiGIT requests.
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

# Follow-ups for the two 50 km misses (5 more requests).
# Jurong: ask round_trip for a shorter loop, since seed 3 overshot 50 km by 5.3 km.
run --name ride-50km-jurong-lake-gardens-shorter-request --activity ride \
    --start "jurong lake gardens" --confirm "PASSION WAVE @ JURONG LAKE GARDENS" \
    --distance 50 --round-trip --seeds 3,4,5 --request-km 45
# Pasir Ris: round_trip points fell in the sea, so use inland via points instead.
run --name ride-50km-pasir-ris-park-via --activity ride --start "pasir ris park" \
    --confirm "PASIR RIS BEACH PARK" --distance 50 \
    --via "103.9105,1.4192;103.8650,1.4160;103.8440,1.3620;103.9250,1.3410" \
    --via "103.9105,1.4192;103.8650,1.4160;103.8440,1.3620;103.9300,1.3050"

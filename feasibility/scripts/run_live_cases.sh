#!/usr/bin/env bash
# Every live case in EVIDENCE.md. Needs HEIGIT_API_KEY and `feasibility fetch-data`
# (plus data/restricted_ways.geojson, see README). At most 38 HeiGIT requests.
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

# Core retry through one long cycling-allowed green track (1 request): East Coast Park
# then Coastal PC, with via points about 1 km apart on the NParks track
# (scripts/rank_green_tracks.py explains the choice), back via Bedok Reservoir Road.
ECP_AND_COASTAL_PC="103.88796,1.29460;103.89701,1.29559;103.90599,1.29817;103.91501,1.30104"
ECP_AND_COASTAL_PC+=";103.92401,1.30360;103.93304,1.30765;103.94197,1.30913;103.95098,1.31144"
ECP_AND_COASTAL_PC+=";103.96005,1.31480;103.96901,1.31633;103.97525,1.31693;103.98311,1.31689"
ECP_AND_COASTAL_PC+=";103.99077,1.31567;103.99902,1.31210;104.01924,1.32608;104.02967,1.35091"
ECP_AND_COASTAL_PC+=";104.01362,1.36608"
run --name core-ride-60-70km-green-track --activity ride --start "avenue south residence" \
    --distance 60-70 --via "$ECP_AND_COASTAL_PC;103.92000,1.34000" --require-green

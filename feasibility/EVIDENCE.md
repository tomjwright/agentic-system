# Issue #2 feasibility evidence

Real HeiGIT, OneMap and data.gov.sg data, collected 2026-11-22 (SGT) with the code in
this folder. Per-case reports with every attempt are in [evidence/](evidence/).
This is route-quality evidence, not legal or safety certification.

## Recommendation for Tom's review: conditional go

The core journey works on real data: a **64.46 km road-cycling loop from Avenue South
Residence** (seed 3) that closes, stays in Singapore, runs on no expressway, slip road,
road tunnel or `bicycle=no` way, and includes **4.1 km of NParks track where
`ALLOW_CYCLING=Y`**, the longest being 0.8 km on Bedok Park Connector and 0.6 km in
East Coast Park Area G ([report](evidence/core-ride-60-70km.md),
[GPX](evidence/core-ride-60-70km.gpx)). 10 of 12 case runs accepted a loop; the two
that did not (Jurong and Pasir Ris, 50 km) were each fixed by one bounded follow-up.

Go only with these conditions carried into the build (each one is evidenced below):

1. **Candidate generation needs more than HeiGIT `round_trip`.** 18 of 28 case
   requests errored (9) or were rejected (9): coastal starts put random round-trip points in the sea
   (Pasir Ris failed 3 of 3), and foot lengths drift up to 74% (10 km asked, 17.35 km
   returned). The generator needs fixed-seed retries, length correction and an
   inland via-point fallback (the via fallback fixed Pasir Ris first time).
2. **Start confirmation is mandatory.** The spec's own wording "Avenue South
   Residences" resolves to Grandeur Park Residences in Bedok, about 13 km away.
3. **OneMap terms gap.** Search works without a token, but every response says the
   token is missing, and the terms require a OneMap developer account. Tom has to
   register before app use; nothing was registered here.
4. **Restriction checks are a proxy.** HeiGIT does not return
   `roadaccessrestrictions` and has no expressway flag in Singapore, so the check
   uses OpenStreetMap tags. Rides still use trunk roads (legal for bicycles, but busy):
   up to 8.85 km per ride. Disclose them rather than call routes safe.
5. **Surfaces are often unknown for running** (up to 58% of run distance) and must be
   shown as unknown, not assumed paved.

Not a no-go: no step was blocked, and every rejection was caught by the checks.

## Verified providers

| provider | endpoint | auth | verified |
| --- | --- | --- | --- |
| HeiGIT openrouteservice | `POST https://api.heigit.org/openrouteservice/v2/directions/{foot-walking,cycling-road}/geojson` | `Authorization: <key>` header, server side only | engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15 |
| OneMap search | `GET https://www.onemap.gov.sg/api/common/elastic/search?searchVal=…&returnGeom=Y&getAddrDetails=Y&pageNum=1` | none sent; response `error`: "Authentication token missing…" | results returned anyway |
| data.gov.sg | `GET https://api-open.data.gov.sg/v1/public/api/datasets/{id}/poll-download` then the signed URL; metadata at `https://api-production.data.gov.sg/v2/public/api/datasets/{id}/metadata` | none | all four datasets downloaded |

`api.openrouteservice.org` is deprecated; only `api.heigit.org` was used.

### HeiGIT contract (sanitized)

Request (round trip): `{"coordinates": [[lon, lat]], "options": {"round_trip":
{"length": m, "points": 3, "seed": n}, "avoid_features": ["ferries"] (run) or
["ferries", "steps"] (ride)}, "extra_info": ["surface", "waytype", "waycategory",
"steepness"], "instructions": true}`. Via loop: `coordinates` = start, via points, start.

Response: a GeoJSON `FeatureCollection` with one `LineString` feature,
coordinates `[lon, lat]` (6 decimals), `properties.summary.distance` (m) and
`duration` (s), `way_points`, `segments[].steps[]` (`name`, `distance`,
`way_points`), `extras.{surface,waytype,waycategory}` (`values` index ranges plus a
`summary` of distance per value) and `warnings`. `metadata` has `attribution`,
`engine`, and echoes the `query`. The response never contains the key; the recorded
fixtures are bodies only. Headers include `x-ratelimit-remaining`.

Failures seen: HTTP 500 "Could not find a valid point after 3 tries, for the point:
lat,lon" (a generated round-trip point fell where nothing is routable) and HTTP 404
"Unable to find a route for point (lon lat)". Both echo coordinates, so an app must
not log provider errors raw (precise locations).

Every response warned `Extra info requested but not available:
roadaccessrestrictions` (seen in the probe that asked for it); `waycategory`
reported no highway, tollway, steps, ferry or ford on any accepted ride.

Geometry check: 1,812 of 1,987 distinct core-route vertices are exact OSM node
positions in the 2026-11-14 BBBike extract, which is what makes the "on a restricted
road" check below precise.

### Usage, quota and terms

- Plan: free Standard, Directions V2 **2,000 a day, 40 a minute**. This work used
  **39** directions requests (quota header 2000 to 1961): 28 in the recorded case
  run, 11 in probes and earlier runs of the same cases. Live
  runs pause 2 s between requests and stop at the first accepted candidate;
  `scripts/run_live_cases.sh` makes at most 37 (28 in the recorded run).
- Hosted limits from the issue's exploration notes (round trip up to 100 km, 50
  waypoints) were not hit; the longest request was 65 km. Not revalidated beyond that.
- HeiGIT terms: results are OSM-based, not guaranteed accurate or reproducible, not
  legal or safety advice; attribution "© openrouteservice by HeiGIT | Data from
  OpenStreetMap" is required and results are CC-BY-SA 4.0. Route geometry is OSM
  derived: ODbL attribution "© OpenStreetMap contributors". Both are written into
  every GeoJSON and GPX.
- Reproducibility: the same seed gave the same 64.46 km route on two runs about an
  hour apart, but HeiGIT does not promise this across graph rebuilds (weekly-ish).
- OneMap: terms need a registered account and acceptance of the developer
  agreement before use in an app; attribution to OneMap/SLA is required.

## Green and boundary data

| dataset | id | features | last updated | used for |
| --- | --- | --- | --- | --- |
| NParks Tracks | `d_306cc1018cb733346681883ee6d73054` | 15,425 (12,289 LineString, 3,136 MultiLineString) | 2026-10-30 | green sections and cycling permission |
| Park Connector Loop | `d_a69ef89737379f231d2ae93fd1c5707f` | 878 | 2026-10-29 | named loops (not needed for matching: the tracks include PCN) |
| NParks Parks and Nature Reserves | `d_77d7ec97be83d44f61b85454f844382f` | 462 polygons | 2026-11-22 | park names (not used for permission) |
| Master Plan 2019 Planning Area Boundary (No Sea) | `d_4765db0e87b9c86336792efe8a1f7a66` | 55 polygons | 2025-12-05 (URA) | Singapore bounds |

All are GeoJSON in WGS84 `[lon, lat]`, Singapore Open Data Licence v1.0: free use
with conspicuous attribution and a link to the licence; no endorsement implied.
Refresh cadence observed: NParks datasets are re-published roughly monthly.

NParks Tracks `ALLOW_CYCLING`: `Y` 9,071, `N` 6,245, null 109. 1,081 `INC_CRC` IDs
repeat; 1,064 duplicate groups are identical apart from `OBJECTID`.

### Normalization rules

- OneMap `LATITUDE`/`LONGITUDE` are strings: parsed to floats, stored `[lon, lat]`.
  A start resolves alone only when every result is one building whose name matches
  the query; otherwise the user must confirm one listed place (`--confirm`).
- NParks: one track per `INC_CRC`; duplicates that disagree on cycling become
  `unknown`. `ALLOW_CYCLING` `Y` is allowed, `N` not allowed, anything else unknown.
  Only allowed counts as green cycling.
- Green section: route sampled every 10 m, matched to a track within 12 m, grouped
  by park and permission, kept when at least 100 m long. Being near a park does not
  count.
- Distance: a single target accepts ±10% (10 km is 9-11 km); a range such as 60-70
  is exact, never widened. Bad, zero, negative and reversed targets are rejected.
- Loop: ends within 30 m of the start; all points finite; inside the planning-area
  boundary, allowing 50 m past the coastline because the boundary is approximate
  (one East Coast seaside point sat 30 m past it).
- Repeated ground: share of 20 m samples within 15 m of route already covered at
  least 300 m earlier (out-and-back and backtracking).

## Restriction inspection

`scripts/extract_restricted_ways.py` takes 13,222 ways from the OSM extract
(BBBike, 2026-11-14): expressways (`motorway`), slip roads (`motorway_link`), trunk
roads, road tunnels and `bicycle=no`. For each route:

- **near**: route length within 8 m of the way (crossings, bridges, parallel paths);
- **on**: route edges whose two ends and middle all lie within 1.5 m of the way.
  HeiGIT vertices are OSM nodes, so this means the route uses that road. A positive
  control (an East Coast Parkway way fed in as a route) reports 384 of 384 m on.

A candidate is rejected when it is on an expressway, slip road or road tunnel (both
activities) or a `bicycle=no` way (rides). Trunk roads are legal for bicycles and
are reported, not rejected.

Results: every accepted ride is **0 m on** expressways, slip roads, road tunnels and
`bicycle=no` ways. They pass near them (the core ride is near expressways at 15
crossings, 306 m in total, and slip roads at 27, 1,009 m) through bridges, underpasses
and junctions, which is the legal crossing case. One candidate was caught: Marina
Barrage seed 1 ran on 11 m of the Kallang-Paya Lebar Expressway and 23 m of a
`bicycle=no` way (and missed the distance), so it was rejected. Runs use some
`bicycle=no` footways (up to 456 m), which is fine on foot.

Trunk road use on accepted rides: core 0 km, Bishan 50 km 3.88 km, Jurong 50 km
8.85 km. HeiGIT's `waytype` calls 30% of the core ride "state road".

## Every case

All round trips use `points: 3`; requested length is the target midpoint unless
noted. "Green" is NParks track with `ALLOW_CYCLING=Y` on the selected route.

| case | start (OneMap) | target | attempts | result | km | green km | repeated | unknown surface | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| core ride | Avenue South Residence | 60-70 | seeds 1-3 | accepted, seed 3 | 64.46 | 4.13 | 2% | 3% | seeds 1, 2: HeiGIT 500/404 at the start; 108 m dead-end spur at Tanah Merah |
| run | Avenue South Residence | 5 | seeds 1-3 | accepted, seed 3 | 4.67 | 0 | 2% | 58% | 6.50, 5.53 missed |
| run | Avenue South Residence | 10 | seeds 1-3 | accepted, seed 3 | 9.41 | 0 | 1% | 48% | 17.35, 14.46 missed |
| run | East Coast Park (confirmed of 4 names) | 5 | seeds 1-3 | accepted, seed 3 | 5.03 | 0.24 | 3% | 11% | 6.09, 5.57 missed |
| run | Bishan-Ang Mo Kio Park (Pond Gardens, confirmed) | 10 | seed 1 | accepted | 10.04 | 0.88 | 1% | 33% | |
| ride | Marina Barrage | 20 | seeds 1-3 | accepted, seed 3 | 20.06 | 5.24 | 7% | 5% | seed 1 on KPE and `bicycle=no`; seed 2 HeiGIT 404 |
| ride | East Coast Park (confirmed) | 20 | seeds 1-3 | accepted, seed 3 | 19.63 | 1.03 | 1% | 2% | seed 1 16.56 km and a point outside Singapore; seed 2 HeiGIT 500 |
| ride | Bishan-Ang Mo Kio Park (confirmed) | 50 | seed 1 | accepted | 49.74 | 0.44 | 9% | 2% | 3.88 km on trunk roads |
| ride | Jurong Lake Gardens (Passion Wave, confirmed) | 50 | seeds 1-3 | **missed** | 55.30 | | 6% | 5% | 0.30 km over 55; seeds 1, 2 HeiGIT 404/500 |
| ride, follow-up | Jurong Lake Gardens | 50, request 45 km | seeds 3-5 | accepted, seed 3 | 54.80 | 2.68 | 8% | 6% | 8.85 km on trunk roads |
| ride | Pasir Ris Beach Park (confirmed) | 50 | seeds 1-3 | **failed** | | | | | all three HeiGIT 500: round-trip points in the sea |
| ride, follow-up | Pasir Ris Beach Park | 50 | 1 via loop (4 inland points) | accepted | 46.54 | 2.66 | 3% | 3% | first via candidate |

Totals: 28 case requests, 19 routes returned, 10 accepted (including both
follow-ups), 9 rejected by the checks, 9 HeiGIT errors. Each report lists the surface, way type and category
tables, every green section with its NParks track IDs, and every restricted road.

Runs stay on footways a lot, where OSM has no surface, so 33-58% unknown surface on
runs is normal and has to be shown as unknown.

## Run it

See [README.md](README.md) for setup. Everything above comes from:

```bash
uv run feasibility fetch-data --data-dir data
uv run --with osmium python scripts/extract_restricted_ways.py Singapore.osm.pbf data/
HEIGIT_API_KEY=... ./scripts/run_live_cases.sh
```

Deterministic checks (no key, recorded responses): see `## Checks` in the README.

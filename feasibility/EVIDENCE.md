# Issue #2 feasibility evidence

Real HeiGIT, OneMap and data.gov.sg data, collected 2026-11-22 (SGT) with the code in
this folder. Per-case reports with every attempt are in [evidence/](evidence/).
This is route-quality evidence, not legal or safety certification.

## Recommendation for Tom's review: conditional go

The start is **Avenue South Residence, 11 Silat Avenue, Kampong Bahru** (Singapore
168877), found by the OneMap query `avenue south residence`.

The core journey works on real data. The retry Tom asked for ("Go, but first retry the
core loop through one longer cycling-allowed green track") gives a **68.25 km
road-cycling loop from Avenue South Residence** through East Coast Park and Coastal
Park Connector. It closes, stays in Singapore, runs on no expressway, slip road, road
tunnel or `bicycle=no` way, and has **one unbroken 10.71 km stretch on NParks track
where `ALLOW_CYCLING=Y`** (East Coast Park Areas B to G), 21.91 km of such track
in total ([report](evidence/core-ride-60-70km-green-track.md),
[GPX](evidence/core-ride-60-70km-green-track.gpx); details in
[Core retry](#core-retry-through-one-long-green-track)). The first core loop (64.46 km,
round-trip seed 3, longest green stretch 0.8 km) is kept for comparison
([report](evidence/core-ride-60-70km.md), [GPX](evidence/core-ride-60-70km.gpx)).
10 of 12 case runs accepted a loop; the two that did not (Jurong and Pasir Ris, 50 km)
were each fixed by one bounded follow-up.

Go only with these conditions carried into the build (each one is evidenced below):

1. **Candidate generation needs more than HeiGIT `round_trip`.** 18 of 28 case
   requests errored (9) or were rejected (9): coastal starts put random round-trip points in the sea
   (Pasir Ris failed 3 of 3), and foot lengths drift up to 74% (10 km asked, 17.35 km
   returned). The generator needs fixed-seed retries, length correction and an
   inland via-point fallback (the via fallback fixed Pasir Ris first time). A long
   green stretch also needs via points placed along the NParks track: `round_trip`
   only brushed parks (longest 0.8 km).
2. **Start confirmation is mandatory.** Avenue South Residence is in Kampong Bahru
   (Silat Avenue). The spec's plural wording "Avenue South Residences" is a OneMap
   search mismatch: it returns only Grandeur Park Residences in Bedok, about 13 km
   away. Only the singular `avenue south residence` returns the right building.
3. **OneMap terms gap.** Search works without a token, but every response says the
   token is missing, and the terms require a OneMap developer account. Tom has to
   register before app use; nothing was registered here.
4. **Restriction checks are a proxy.** HeiGIT does not return
   `roadaccessrestrictions` and has no expressway flag in Singapore, so the check
   uses OpenStreetMap tags. Rides still use trunk roads (legal for bicycles, but busy):
   up to 8.85 km per ride, 1.11 km on the core retry (900 m of Nicoll Highway).
   Disclose them rather than call routes safe.
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
  **42** directions requests (quota header 2000 to 1958): 28 in the recorded case
  run, 11 in probes and earlier runs of the same cases, and 3 for the core retry
  (2 probes, 1 recorded; the retry budget was 15). Live
  runs pause 2 s between requests and stop at the first accepted candidate;
  `scripts/run_live_cases.sh` makes at most 38 (29 in the recorded runs).
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
- Longest contiguous green: the same 10 m samples, on any `ALLOW_CYCLING=Y` track,
  joined across park names (NParks names East Coast Park by area A to H). A gap of up
  to 50 m (a junction, or a crossing where a not-allowed path lies nearer) is bridged
  and reported separately, not counted as green; a longer gap ends the stretch. The
  gap runs from the last sample on an allowed track to the next one, including the
  step back onto the track.
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
| core ride | Avenue South Residence | 60-70 | seeds 1-3 | accepted, seed 3 | 64.46 | 4.13 | 2% | 3% | seeds 1, 2: HeiGIT 500/404 at the start; 108 m dead-end spur at Tanah Merah; longest green 0.80 km |
| core ride, green-track retry | Avenue South Residence | 60-70 | 1 via loop (18 points) | accepted | 68.25 | 21.91 | 6% | 4% | longest green 10.71 km (East Coast Park Areas B-G); 1.11 km on trunk roads; after 2 probes |
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
follow-ups), 9 rejected by the checks, 9 HeiGIT errors. The core retry adds 1
recorded request (accepted) after 2 probes. Each report lists the surface, way type and category
tables, every green section with its NParks track IDs, and every restricted road.

Runs stay on footways a lot, where OSM has no surface, so 33-58% unknown surface on
runs is normal and has to be shown as unknown.

## Core retry through one long green track

Tom's go decision: "Go, but first retry the core loop through one longer
cycling-allowed green track". Same start, same exact 60-70 km range, same checks.

### Choosing the track

`scripts/rank_green_tracks.py` keeps NParks Tracks with `ALLOW_CYCLING=Y` (one per
`INC_CRC`), joins tracks whose ends meet within 15 m, and measures the biggest joined
network of each candidate. A good track for this loop is one a ride can follow for a
long way (span, not the total length of a park's path web), lies within reach of a
60-70 km loop from Kampong Bahru, and suits a road bike.

| candidate | allowed tracks | biggest joined network km | span km | from start km |
| --- | --- | --- | --- | --- |
| East Coast Park + Coastal PC | 321 | 57.9 | 17.6 | 6.6 |
| East Coast Park | 297 | 43.2 | 10.4 | 6.6 |
| Rail Corridor | 13 | 11.0 | 10.5 | 8.3 |
| Punggol Waterway | 366 | 14.0 | 2.8 | 16.6 |
| Bishan-Ang Mo Kio Park | 350 | 10.7 | 1.1 | 9.3 |

Chosen: **East Coast Park then Coastal PC**. It is the longest span (one path along the
coast for 17.6 km) and the nearest to the start, and its spine is NParks `Cycle Track`
(for example `817727C0AE29B96B` in Area B, 3.4 km, and Coastal PC `8785033D32609922`,
13.4 km). The Rail Corridor spans 10.5 km, but its 13 allowed tracks are typed
`Footpath`, `Boardwalk/Trail` and `Service Track/Road`, none `Cycle Track`, so it is a
poor fit for a road bike. Punggol Waterway and Bishan-Ang Mo Kio are dense park
networks with spans under 3 km, so neither gives one long stretch.

### Result

Via points were taken about 1 km apart on the NParks track itself (East Coast Park
Area B to Coastal PC near Changi Beach), then one inland point on Bedok Reservoir Road
to bring the loop back. 3 HeiGIT requests, 2 s apart:

| request | via points | km | outcome | longest green km |
| --- | --- | --- | --- | --- |
| probe 1 | 25 on the track every ~1 km, 3 inland | 82.66 | outside target | 7.04 (Coastal PC), earlier gap rule |
| probe 2 | 17 on the track, 1 inland | 68.25 | accepted | 10.71 |
| recorded | same as probe 2 | 68.25 | accepted | 10.71 |

Probe 1 was too long: it had more points around Changi Beach and three inland return
points, and its longest green stretch was 7.04 km. Probe 2 dropped 8 Changi points and
2 inland points. The recorded run is the case in `scripts/run_live_cases.sh` and gave the
same route as probe 2.

| | first core loop | green-track retry |
| --- | --- | --- |
| how | `round_trip` seed 3 | via loop, 18 points |
| distance | 64.46 km | 68.25 km |
| closes, in Singapore | yes | yes |
| on expressway, slip road, road tunnel, `bicycle=no` | 0 m | 0 m |
| on trunk roads (disclosed) | 0 km | 1.11 km (Nicoll Highway 900 m, an unnamed trunk 206 m) |
| `ALLOW_CYCLING=Y` track | 4.13 km in 12 sections | 21.91 km in 31 sections |
| longest contiguous green | 0.80 km (Bedok PC) | **10.71 km** (East Coast Park Areas B-G) |
| repeated ground | 2% | 6% |
| unknown surface | 3% | 4% |
| way type cycleway | 4% | 29% |
| duration estimate | 183 min | 304 min |

The 10.71 km stretch bridges 199 m of junctions and crossings in total (each gap
50 m or less) and runs on 45 NParks track IDs; the main ones are
`5E53B02ED6171F45` (Area E), `310A6C9D513D0416` and `AE927B4D9B9BFFDF` (Area G) and
`817727C0AE29B96B` (Area B). The full list is in the report. A gap just over 50 m
after Area G ends it; the route's next stretches are 3.02 km (Area H to Coastal PC) and
4.46 km (Coastal PC).

Correction after review: the first version of this evidence reported 13.88 km. It
counted the step back onto a track as green and left it out of the gap, so gaps of up
to about 60 m were bridged. Tom chose the strict 50 m rule, which gives 10.71 km. The
probe 1 figure was measured with the earlier rule and not rerun.

What still falls short: the longest stretch (10.71 km) is less than the 17.6 km span of
the corridor, because the route leaves the NParks track in places for nearby roads,
which `cycling-road` prefers; those parts do not count as green. HeiGIT also labels
1.25 km of the route `construction`. The duration estimate is long
because park paths are slow in the `cycling-road` profile.

## Run it

See [README.md](README.md) for setup. Everything above comes from:

```bash
uv run feasibility fetch-data --data-dir data
uv run --with osmium python scripts/extract_restricted_ways.py Singapore.osm.pbf data/
uv run python scripts/rank_green_tracks.py data/nparks_tracks.geojson
HEIGIT_API_KEY=... ./scripts/run_live_cases.sh
```

Deterministic checks (no key, recorded responses): see `## Checks` in the README.

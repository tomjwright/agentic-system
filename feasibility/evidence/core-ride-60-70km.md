# core-ride-60-70km

Activity: ride

Start query: `avenue south residence` (resolved: single building whose name matches the query)

Start: AVENUE SOUTH RESIDENCE, 11 SILAT AVENUE AVENUE SOUTH RESIDENCE SINGAPORE 168877 (1.27663, 103.82911)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 60-70 km (accepts 60.00-70.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | - | error | HeiGIT returned 500: Could not find a valid point after 3 tries, for the point:1.276629534107344,103.8291052120283 | | |
| 2 | seed 2 | - | error | HeiGIT returned 404: Route could not be found - Unable to find a route for point (103.8291052 1.2766295). | | |
| 3 | seed 3 | 64.46 | accepted | none | 4.13 | 2% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1986

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.8291052120283,
      1.276629534107344
    ]
  ],
  "options": {
    "round_trip": {
      "length": 65000,
      "points": 3,
      "seed": 3
    },
    "avoid_features": [
      "ferries",
      "steps"
    ]
  },
  "extra_info": [
    "surface",
    "waytype",
    "waycategory",
    "steepness"
  ],
  "instructions": true
}
```

## Selected: attempt 3, 64.46 km

- Candidate: seed 3
- Duration estimate: 183 min (cycling-road)
- Vertices: 1996
- Files: `core-ride-60-70km.geojson`, `core-ride-60-70km.gpx` (same points)
- Repeated ground (out-and-back): 2%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 62.23 | 97% |
| unknown | 1.91 | 3% |
| concrete | 0.32 | 1% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 40.76 | 63% |
| state road | 19.18 | 30% |
| cycleway | 2.68 | 4% |
| street | 1.50 | 2% |
| footway | 0.33 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 64.46 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Whampoa Park Connector | allowed | 121 | yes | 797C1382D404F044, 03010384A195AF4C |
| Kallang Park Connector | allowed | 106 | yes | F9BE5A69491F6241, 945D5DA1AF60DA78 |
| Potong Pasir PC | allowed | 204 | yes | 1DDFC762CE7031ED |
| Interim RIR - Jalan Kayu/Sengkang West Wat to Sengkang Riverside Park  | allowed | 542 | yes | BB051B16834A0150 |
| Rowers Bay to TPE | allowed | 350 | yes | 73E9282B777C883C |
| Rowers Bay to TPE | allowed | 113 | yes | 73E9282B777C883C |
| Interim RIR - Jalan Kayu/Sengkang West Wat to Sengkang Riverside Park  | allowed | 125 | yes | BB051B16834A0150 |
| Interim RIR - Jalan Kayu/Sengkang West Wat to Sengkang Riverside Park  | allowed | 136 | yes | BB051B16834A0150 |
| EAST COAST PARK AREA G | allowed | 266 | yes | 310A6C9D513D0416, D6E5D8F2017F05D5 |
| EAST COAST PARK AREA G | allowed | 643 | yes | AE927B4D9B9BFFDF, 110B062C9A3E5D87, 68F845983EBDCA2D (+2) |
| BEDOK PC (LAGUNA GC-ECP (NEAR C/P G) | allowed | 803 | yes | 6747B10736A9158B |
| BEDOK PC (LAGUNA GC-ECP (NEAR C/P G) | allowed | 716 | yes | 6747B10736A9158B, 3222457E64282621 |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 21 | 859 | 0 | Jalan Bukit Merah, -, Jalan Kayu, Tanah Merah Coast Road, Mountbatten Road, Kallang Airport Way |
| major arterial (trunk) | Rochor Canal Road | 1 | 13 | 0 | Selegie Road |
| major arterial (trunk) | Bukit Timah Road | 1 | 13 | 0 | Selegie Road |
| expressway | Pan-Island Expressway | 2 | 74 | 0 | - |
| major arterial (trunk) | unnamed | 8 | 202 | 0 | Bidadari Park Drive, Serangoon Avenue 1, Yio Chu Kang Link, Upper East Coast Road, Mountbatten Road |
| major arterial (trunk) | Bartley Road | 1 | 34 | 0 | Bidadari Park Drive |
| major arterial (trunk) | Ang Mo Kio Underpass | 1 | 30 | 0 | Yio Chu Kang Link |
| major arterial (trunk) | Ang Mo Kio Avenue 3 | 1 | 18 | 0 | Yio Chu Kang Link |
| expressway | Tampines Expressway | 4 | 42 | 0 | Jalan Kayu |
| bicycle=no | unnamed | 4 | 65 | 0 | -, Tanah Merah Coast Road |
| expressway slip road | Kallang-Paya Lebar Expressway | 1 | 40 | 0 | - |
| expressway | Kallang-Paya Lebar Expressway | 3 | 90 | 0 | -, Mountbatten Road, Kallang Airport Way |
| bicycle=no | Sheltered walkway to bus stop | 1 | 10 | 0 | - |
| expressway slip road | Tanah Merah Flyover | 3 | 45 | 0 | - |
| expressway | East Coast Parkway | 4 | 56 | 0 | -, Bedok Park Connector |
| expressway slip road | East Coast Park Service Road | 1 | 44 | 0 | - |
| major arterial (trunk) | Still Road South | 2 | 24 | 0 | Upper East Coast Road |
| major arterial (trunk) | Still Road | 1 | 7 | 0 | Upper East Coast Road |
| major arterial (trunk) | Nicoll Highway | 1 | 30 | 0 | Mountbatten Road |
| bicycle=no | Kampong Bugis | 1 | 11 | 0 | Old Terminal Lane |
| major arterial (trunk) | Ophir Road | 1 | 13 | 0 | - |
| major arterial (trunk) | Rochor Road | 1 | 8 | 0 | - |
| expressway slip road | Jalan Bukit Merah | 1 | 21 | 0 | Jalan Bukit Merah |
| expressway | Central Expressway | 2 | 44 | 0 | Jalan Bukit Merah, - |

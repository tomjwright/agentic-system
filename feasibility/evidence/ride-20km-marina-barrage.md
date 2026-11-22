# ride-20km-marina-barrage

Activity: ride

Start query: `marina barrage` (resolved: single building whose name matches the query)

Start: MARINA BARRAGE, 8 MARINA GARDENS DRIVE MARINA BARRAGE SINGAPORE 018951 (1.27991, 103.87047)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 20 km (accepts 18.00-22.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 29.59 | outside target | on 23 m of bicycle=no unnamed; on 11 m of expressway Kallang-Paya Lebar Expressway | 0.70 | 8% |
| 2 | seed 2 | - | error | HeiGIT returned 404: Route could not be found - Unable to find a route for point (103.8704696 1.2799057). | | |
| 3 | seed 3 | 20.06 | accepted | none | 5.24 | 7% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1975

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.8704696159287,
      1.2799057348975
    ]
  ],
  "options": {
    "round_trip": {
      "length": 20000,
      "points": 3,
      "seed": 1
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

## Rejected: attempt 1, 29.59 km

- Candidate: seed 1
- Duration estimate: 107 min (cycling-road)
- Vertices: 916
- Files: `ride-20km-marina-barrage.attempt-1.geojson`
- Repeated ground (out-and-back): 8%
- Validation problems: outside target; on 23 m of bicycle=no unnamed; on 11 m of expressway Kallang-Paya Lebar Expressway
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 24.14 | 82% |
| unknown | 3.88 | 13% |
| concrete | 1.35 | 5% |
| paved | 0.21 | 1% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 16.67 | 56% |
| state road | 7.58 | 26% |
| path | 2.82 | 10% |
| footway | 1.56 | 5% |
| cycleway | 0.68 | 2% |
| street | 0.28 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 29.59 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Marina Barrage | allowed | 188 | yes | 2E4AA93DB36766FB |
| Marina Barrage | allowed | 325 | yes | 2E4AA93DB36766FB |
| Marina Barrage | allowed | 188 | yes | 2E4AA93DB36766FB |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| bicycle=no | unnamed | 6 | 192 | 23 | -, Telok Blangah Road, Gateway Avenue |
| expressway | Marina Coastal Expressway | 1 | 53 | 0 | Marina East Drive |
| expressway slip road | unnamed | 7 | 209 | 0 | Marina East Drive, Keppel Road, Maxwell Road |
| expressway | East Coast Parkway | 2 | 21 | 0 | Marina East Drive |
| expressway slip road | Kallang Paya Lebar Expressway | 1 | 9 | 0 | - |
| expressway | Kallang-Paya Lebar Expressway | 5 | 437 | 11 | -, Stadium Way, Stadium Walk, Stadium Drive |
| major arterial (trunk) | unnamed | 2 | 112 | 88 | - |
| major arterial (trunk) | Nicoll Highway | 2 | 1896 | 1878 | -, Middle Road |
| expressway | Ayer Rajah Expressway | 1 | 44 | 0 | - |
| bicycle=no | Sentosa Gateway Tunnel | 6 | 289 | 0 | -, Gateway Avenue |
| bicycle=no | West Coast Highway | 3 | 213 | 0 | -, Gateway Avenue |
| major arterial (trunk) | Keppel Road | 5 | 2020 | 1811 | -, Gateway Avenue, Keppel Road |
| major arterial (trunk) | West Coast Highway | 3 | 257 | 239 | -, Gateway Avenue, Keppel Road |
| bicycle=no | Kampong Bahru Road | 1 | 24 | 0 | Telok Blangah Road |
| major arterial (trunk) | Anson Road | 1 | 583 | 583 | Anson Road |
| major arterial (trunk) | Robinson Road | 1 | 6 | 0 | Maxwell Road |
| major arterial (trunk) | Shenton Way | 1 | 11 | 0 | Maxwell Road |

## Selected: attempt 3, 20.06 km

- Candidate: seed 3
- Duration estimate: 96 min (cycling-road)
- Vertices: 615
- Files: `ride-20km-marina-barrage.geojson`, `ride-20km-marina-barrage.gpx` (same points)
- Repeated ground (out-and-back): 7%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 16.28 | 81% |
| concrete | 2.44 | 12% |
| unknown | 0.95 | 5% |
| paved | 0.40 | 2% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 7.51 | 37% |
| cycleway | 5.67 | 28% |
| state road | 3.46 | 17% |
| footway | 1.87 | 9% |
| street | 1.56 | 8% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 20.06 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Marina Barrage | allowed | 188 | yes | 2E4AA93DB36766FB |
| Marina Barrage | allowed | 325 | yes | 2E4AA93DB36766FB |
| EAST COAST PARK AREA C | allowed | 225 | yes | E33A90146C836E9B, D9A79C1F76093153, 087B552372C23E7B |
| EAST COAST PARK AREA B | allowed | 344 | yes | 817727C0AE29B96B |
| EAST COAST PARK AREA B | allowed | 2181 | yes | 817727C0AE29B96B, 81F55AC5E830BE17, 15AFAA8A55F2A1E2 (+3) |
| East Coast Park (Tanjong Rhu to Area C) | allowed | 184 | yes | 00FD57C35A356431 |
| Gardens by the Bay East | allowed | 541 | yes | 440BCCA514100228 |
| Gardens by the Bay East | allowed | 741 | yes | 440BCCA514100228 |
| Marina Barrage | allowed | 325 | yes | 2E4AA93DB36766FB |
| Marina Barrage | allowed | 188 | yes | 2E4AA93DB36766FB |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| bicycle=no | unnamed | 2 | 27 | 0 | - |
| expressway | Marina Coastal Expressway | 1 | 53 | 0 | - |
| expressway slip road | unnamed | 8 | 174 | 0 | - |
| expressway | East Coast Parkway | 5 | 115 | 0 | -, Rhu Cross |
| expressway | Pan-Island Expressway | 3 | 62 | 0 | Lorong 22 Geylang, - |
| expressway slip road | ECP | 1 | 11 | 0 | - |
| expressway slip road | East Coast Parkway | 1 | 13 | 0 | - |
| expressway slip road | Kallang Paya Lebar Expressway | 1 | 9 | 0 | Meyer Road |
| expressway | Kallang-Paya Lebar Expressway | 2 | 40 | 0 | Meyer Road |

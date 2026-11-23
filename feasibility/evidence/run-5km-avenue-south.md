# run-5km-avenue-south

Activity: run

Start query: `avenue south residence` (resolved: single building whose name matches the query)

Start: AVENUE SOUTH RESIDENCE, 11 SILAT AVENUE AVENUE SOUTH RESIDENCE SINGAPORE 168877 (1.27663, 103.82911)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 5 km (accepts 4.50-5.50 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 6.50 | outside target | none | 0.00 | 5% |
| 2 | seed 2 | 5.53 | outside target | none | 0.33 | 0% |
| 3 | seed 3 | 4.67 | accepted | none | 0.00 | 2% |

Provider: HeiGIT openrouteservice `foot-walking`, engine 10.1.1, graph 2026-11-16T00:26:59Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1985

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
      "length": 5000,
      "points": 3,
      "seed": 1
    },
    "avoid_features": [
      "ferries"
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

## Rejected: attempt 1, 6.50 km

- Candidate: seed 1
- Duration estimate: 78 min (foot-walking)
- Vertices: 270
- Files: `run-5km-avenue-south.attempt-1.geojson`
- Repeated ground (out-and-back): 5%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| concrete | 3.19 | 49% |
| unknown | 2.52 | 39% |
| asphalt | 0.78 | 12% |
| paving stones | 0.01 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 4.90 | 75% |
| street | 1.06 | 16% |
| cycleway | 0.39 | 6% |
| state road | 0.11 | 2% |
| steps | 0.03 | 0% |
| road | 0.01 | 0% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 6.47 | 100% |
| steps | 0.03 | 0% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| none | | | | |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| major arterial (trunk) | unnamed | 2 | 88 | 0 | - |
| major arterial (trunk) | Keppel Road | 6 | 701 | 0 | - |
| expressway slip road | unnamed | 3 | 214 | 0 | - |
| expressway | Ayer Rajah Expressway | 2 | 74 | 0 | - |
| bicycle=no | Sentosa Gateway Tunnel | 3 | 237 | 0 | - |
| bicycle=no | West Coast Highway | 3 | 163 | 5 | - |
| major arterial (trunk) | West Coast Highway | 2 | 46 | 46 | - |
| bicycle=no | Kampong Bahru Road | 3 | 132 | 87 | -, Kampong Bahru Road |
| bicycle=no | Telok Blangah Road | 2 | 96 | 71 | Kampong Bahru Road, Telok Blangah Road, - |
| bicycle=no | unnamed | 1 | 44 | 35 | - |

## Rejected: attempt 2, 5.53 km

- Candidate: seed 2
- Duration estimate: 66 min (foot-walking)
- Vertices: 201
- Files: `run-5km-avenue-south.attempt-2.geojson`
- Repeated ground (out-and-back): 0%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| concrete | 3.00 | 54% |
| unknown | 1.42 | 26% |
| asphalt | 0.92 | 17% |
| gravel | 0.10 | 2% |
| grass | 0.09 | 2% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 3.71 | 67% |
| street | 0.62 | 11% |
| cycleway | 0.45 | 8% |
| construction | 0.30 | 5% |
| state road | 0.17 | 3% |
| steps | 0.14 | 3% |
| path | 0.14 | 2% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 5.38 | 97% |
| steps | 0.14 | 3% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| AYE (ALEXANDRA RD TO SOUTH BUONA VISTA RD) | allowed | 333 | yes | F805B359DA7F34D2 |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| major arterial (trunk) | Keppel Road | 7 | 703 | 21 | -, Keppel Road |
| expressway | Ayer Rajah Expressway | 3 | 63 | 0 | - |
| expressway slip road | unnamed | 5 | 415 | 0 | Keppel Road, -, Lower Delta Road |
| major arterial (trunk) | West Coast Highway | 1 | 32 | 0 | - |
| bicycle=no | West Coast Highway | 2 | 209 | 5 | - |
| major arterial (trunk) | unnamed | 1 | 28 | 0 | - |
| bicycle=no | Sentosa Gateway Tunnel | 1 | 36 | 0 | - |
| expressway | Central Expressway | 1 | 34 | 0 | - |

## Selected: attempt 3, 4.67 km

- Candidate: seed 3
- Duration estimate: 56 min (foot-walking)
- Vertices: 224
- Files: `run-5km-avenue-south.geojson`, `run-5km-avenue-south.gpx` (same points)
- Repeated ground (out-and-back): 2%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| unknown | 2.72 | 58% |
| asphalt | 1.09 | 23% |
| concrete | 0.86 | 18% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 3.58 | 77% |
| street | 0.98 | 21% |
| state road | 0.06 | 1% |
| steps | 0.04 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 4.63 | 99% |
| steps | 0.04 | 1% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| none | | | | |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway | Central Expressway | 2 | 63 | 0 | - |
| bicycle=no | unnamed | 1 | 184 | 0 | -, Boon Tiong Road |
| expressway slip road | unnamed | 2 | 36 | 0 | - |

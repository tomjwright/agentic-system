# run-10km-avenue-south

Activity: run

Start query: `avenue south residence` (resolved: single building whose name matches the query)

Start: AVENUE SOUTH RESIDENCE, 11 SILAT AVENUE AVENUE SOUTH RESIDENCE SINGAPORE 168877 (1.27663, 103.82911)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 10 km (accepts 9.00-11.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 17.35 | outside target | none | 0.00 | 16% |
| 2 | seed 2 | 14.46 | outside target | none | 0.00 | 21% |
| 3 | seed 3 | 9.41 | accepted | none | 0.00 | 1% |

Provider: HeiGIT openrouteservice `foot-walking`, engine 10.1.1, graph 2026-11-16T00:26:59Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1982

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
      "length": 10000,
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

## Rejected: attempt 1, 17.35 km

- Candidate: seed 1
- Duration estimate: 208 min (foot-walking)
- Vertices: 628
- Files: `run-10km-avenue-south.attempt-1.geojson`
- Repeated ground (out-and-back): 16%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| unknown | 8.01 | 46% |
| concrete | 7.49 | 43% |
| asphalt | 1.64 | 9% |
| paved | 0.15 | 1% |
| paving stones | 0.06 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 11.66 | 67% |
| path | 2.83 | 16% |
| cycleway | 1.38 | 8% |
| street | 0.89 | 5% |
| road | 0.55 | 3% |
| steps | 0.04 | 0% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 17.31 | 100% |
| steps | 0.04 | 0% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| none | | | | |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| bicycle=no | unnamed | 4 | 225 | 23 | - |
| major arterial (trunk) | Anson Road | 1 | 15 | 0 | - |
| major arterial (trunk) | Shenton Way | 2 | 50 | 0 | - |
| expressway slip road | Marina Coastal Expressway | 4 | 134 | 0 | - |
| major arterial (trunk) | Keppel Road | 9 | 1048 | 0 | - |
| expressway | Ayer Rajah Expressway | 4 | 110 | 0 | - |
| major arterial (trunk) | unnamed | 3 | 56 | 0 | - |
| expressway slip road | unnamed | 3 | 214 | 0 | - |
| bicycle=no | Sentosa Gateway Tunnel | 7 | 473 | 0 | -, Sentosa Gateway |
| bicycle=no | West Coast Highway | 2 | 181 | 0 | - |
| major arterial (trunk) | West Coast Highway | 2 | 48 | 0 | - |
| bicycle=no | Kampong Bahru Road | 1 | 21 | 0 | - |

## Rejected: attempt 2, 14.46 km

- Candidate: seed 2
- Duration estimate: 174 min (foot-walking)
- Vertices: 541
- Files: `run-10km-avenue-south.attempt-2.geojson`
- Repeated ground (out-and-back): 21%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| unknown | 7.09 | 49% |
| concrete | 6.22 | 43% |
| asphalt | 1.09 | 8% |
| paving stones | 0.07 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 8.82 | 61% |
| path | 2.82 | 20% |
| cycleway | 1.15 | 8% |
| street | 1.05 | 7% |
| road | 0.60 | 4% |
| steps | 0.02 | 0% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 14.44 | 100% |
| steps | 0.02 | 0% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| none | | | | |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway | Ayer Rajah Expressway | 3 | 76 | 0 | - |
| major arterial (trunk) | unnamed | 1 | 28 | 0 | - |
| bicycle=no | West Coast Highway | 1 | 61 | 0 | - |
| major arterial (trunk) | West Coast Highway | 2 | 48 | 0 | - |
| bicycle=no | Kampong Bahru Road | 1 | 21 | 0 | - |
| bicycle=no | unnamed | 3 | 211 | 23 | - |
| bicycle=no | Sentosa Gateway Tunnel | 6 | 284 | 0 | -, Sentosa Gateway |

## Selected: attempt 3, 9.41 km

- Candidate: seed 3
- Duration estimate: 113 min (foot-walking)
- Vertices: 393
- Files: `run-10km-avenue-south.geojson`, `run-10km-avenue-south.gpx` (same points)
- Repeated ground (out-and-back): 1%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| unknown | 4.56 | 48% |
| concrete | 2.15 | 23% |
| asphalt | 1.84 | 20% |
| paving stones | 0.76 | 8% |
| paved | 0.11 | 1% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 7.41 | 79% |
| street | 1.34 | 14% |
| cycleway | 0.51 | 5% |
| road | 0.09 | 1% |
| steps | 0.07 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 9.35 | 99% |
| steps | 0.07 | 1% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| none | | | | |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | College Road | 1 | 24 | 0 | College Road, - |
| expressway | Central Expressway | 1 | 34 | 0 | - |
| expressway slip road | unnamed | 2 | 26 | 0 | - |
| bicycle=no | unnamed | 1 | 477 | 456 | - |
| major arterial (trunk) | Robinson Road | 1 | 55 | 0 | - |

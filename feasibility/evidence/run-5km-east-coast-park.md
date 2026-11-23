# run-5km-east-coast-park

Activity: run

Start query: `east coast park` (resolved: confirmed by the user as EAST COAST PARK)

Start: EAST COAST PARK, 38 THIRD STREET EAST COAST PARK SINGAPORE 455513 (1.31327, 103.92457)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 5 km (accepts 4.50-5.50 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 6.09 | outside target | none | 1.72 | 3% |
| 2 | seed 2 | 5.57 | outside target | none | 1.26 | 3% |
| 3 | seed 3 | 5.03 | accepted | none | 0.24 | 3% |

Provider: HeiGIT openrouteservice `foot-walking`, engine 10.1.1, graph 2026-11-16T00:26:59Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1979

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.924568894436,
      1.313266240371461
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

## Rejected: attempt 1, 6.09 km

- Candidate: seed 1
- Duration estimate: 73 min (foot-walking)
- Vertices: 239
- Files: `run-5km-east-coast-park.attempt-1.geojson`
- Repeated ground (out-and-back): 3%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| concrete | 4.33 | 71% |
| asphalt | 1.08 | 18% |
| unknown | 0.65 | 11% |
| paving stones | 0.03 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 4.51 | 74% |
| cycleway | 1.30 | 21% |
| street | 0.21 | 4% |
| steps | 0.05 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 6.03 | 99% |
| steps | 0.05 | 1% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Play Corridor | allowed | 206 | yes | 3F5F73B41C71FB65 |
| EAST COAST PARK AREA E | allowed | 161 | yes | 89538159580F588B, E786E88120F73B00, 4DF6AA45789F3A5E (+1) |
| EAST COAST PARK AREA D | allowed | 190 | yes | FA1633E2B75F65CB |
| EAST COAST PARK AREA D | allowed | 163 | yes | FA1633E2B75F65CB, A29C2016E646F4DE |
| EAST COAST PARK AREA D | allowed | 120 | yes | 5EFF0A7AB6DFAAF8, FA1633E2B75F65CB |
| EAST COAST PARK AREA C | allowed | 446 | yes | 290EF78444F217A1 |
| EAST COAST PARK AREA D | allowed | 437 | yes | 0447C764A3F5B5C3, 9267974C09F963BD, 172180E210961B4B (+3) |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 5 | 281 | 0 | - |
| bicycle=no | unnamed | 1 | 44 | 29 | - |
| expressway | East Coast Parkway | 3 | 32 | 0 | - |
| expressway slip road | Siglap Road | 1 | 50 | 0 | - |

## Rejected: attempt 2, 5.57 km

- Candidate: seed 2
- Duration estimate: 67 min (foot-walking)
- Vertices: 196
- Files: `run-5km-east-coast-park.attempt-2.geojson`
- Repeated ground (out-and-back): 3%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| concrete | 3.01 | 54% |
| unknown | 1.30 | 23% |
| asphalt | 0.96 | 17% |
| paved | 0.25 | 5% |
| gravel | 0.06 | 1% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 3.14 | 56% |
| cycleway | 1.77 | 32% |
| construction | 0.35 | 6% |
| street | 0.32 | 6% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 5.57 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| EAST COAST PARK AREA E | allowed | 113 | yes | E786E88120F73B00, 9CFD7DAD6F69725A |
| EAST COAST PARK AREA E | allowed | 161 | yes | E786E88120F73B00, 085C005C41B067EE, 9F37310CCC502CDA (+1) |
| EAST COAST PARK AREA D | allowed | 166 | yes | FA1633E2B75F65CB, A29C2016E646F4DE |
| EAST COAST PARK AREA D | allowed | 120 | yes | 5EFF0A7AB6DFAAF8, FA1633E2B75F65CB |
| EAST COAST PARK AREA D | allowed | 256 | yes | DADD6401F4865936, 275488F94404C049 |
| MARINE PARADE ROAD (STILL ROAD STH - BSA 1) | allowed | 267 | yes | 74C97F33ED8FCADA, BDBC6BE9E705CA5F |
| MARINE PARADE ROAD (STILL ROAD STH - BSA 1) | allowed | 177 | yes | 74C97F33ED8FCADA |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | Siglap Link | 2 | 46 | 0 | - |
| expressway | East Coast Parkway | 3 | 40 | 0 | Play Corridor Park Connector, - |
| expressway slip road | unnamed | 3 | 99 | 0 | Play Corridor Park Connector, - |
| bicycle=no | Marine Vista | 1 | 10 | 0 | - |

## Selected: attempt 3, 5.03 km

- Candidate: seed 3
- Duration estimate: 60 min (foot-walking)
- Vertices: 202
- Files: `run-5km-east-coast-park.geojson`, `run-5km-east-coast-park.gpx` (same points)
- Repeated ground (out-and-back): 3%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| concrete | 3.36 | 67% |
| unknown | 0.87 | 17% |
| asphalt | 0.68 | 14% |
| paved | 0.08 | 2% |
| paving stones | 0.04 | 1% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 4.25 | 84% |
| street | 0.44 | 9% |
| cycleway | 0.34 | 7% |
| steps | 0.00 | 0% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 5.03 | 100% |
| steps | 0.00 | 0% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Play Corridor | allowed | 238 | yes | 3F5F73B41C71FB65 |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| none | | | | | |

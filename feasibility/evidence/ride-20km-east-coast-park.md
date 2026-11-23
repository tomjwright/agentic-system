# ride-20km-east-coast-park

Activity: ride

Start query: `east coast park` (resolved: confirmed by the user as EAST COAST PARK)

Start: EAST COAST PARK, 38 THIRD STREET EAST COAST PARK SINGAPORE 455513 (1.31327, 103.92457)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 20 km (accepts 18.00-22.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 16.56 | outside target | 1 of 433 points are outside Singapore | 6.64 | 6% |
| 2 | seed 2 | - | error | HeiGIT returned 500: Could not find a valid point after 3 tries, for the point:1.313266240371461,103.924568894436 | | |
| 3 | seed 3 | 19.63 | accepted | none | 1.03 | 1% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1972

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

## Rejected: attempt 1, 16.56 km

- Candidate: seed 1
- Duration estimate: 84 min (cycling-road)
- Vertices: 433
- Files: `ride-20km-east-coast-park.attempt-1.geojson`
- Repeated ground (out-and-back): 6%
- Validation problems: outside target; 1 of 433 points are outside Singapore
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 15.60 | 94% |
| concrete | 0.41 | 2% |
| unknown | 0.29 | 2% |
| paved | 0.26 | 2% |

Way types:

| value | km | share |
| --- | --- | --- |
| cycleway | 6.94 | 42% |
| road | 6.32 | 38% |
| state road | 1.78 | 11% |
| street | 0.85 | 5% |
| footway | 0.66 | 4% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 16.56 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Play Corridor | allowed | 387 | yes | 3F5F73B41C71FB65 |
| EAST COAST PARK AREA E | allowed | 119 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA G | allowed | 266 | yes | 310A6C9D513D0416, D6E5D8F2017F05D5 |
| EAST COAST PARK AREA G | allowed | 1383 | yes | AE927B4D9B9BFFDF, 110B062C9A3E5D87, 68F845983EBDCA2D (+2) |
| EAST COAST PARK AREA E | allowed | 266 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA F | allowed | 146 | yes | 550299B2A8F5071B |
| EAST COAST PARK AREA E | allowed | 197 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA E | allowed | 604 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA E | allowed | 197 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA E | allowed | 395 | yes | 5E53B02ED6171F45, F67130B67E15BC6D, D669277C6DDE8817 (+1) |
| EAST COAST PARK AREA D | allowed | 190 | yes | FA1633E2B75F65CB |
| EAST COAST PARK AREA D | allowed | 163 | yes | FA1633E2B75F65CB, A29C2016E646F4DE |
| EAST COAST PARK AREA D | allowed | 116 | yes | 5EFF0A7AB6DFAAF8, FA1633E2B75F65CB, 7C3FB49460D7497C |
| EAST COAST PARK AREA D | allowed | 746 | yes | 9267974C09F963BD, FA1633E2B75F65CB, 4F86406B9A97BC3D (+3) |
| EAST COAST PARK AREA C | allowed | 465 | yes | 5F3D6CC6CA25A27E, 01D7E8CEF74BC011, 2097D2332D556C8C (+2) |
| EAST COAST PARK AREA B | allowed | 784 | yes | 817727C0AE29B96B |
| EAST COAST PARK AREA C | allowed | 217 | yes | D9A79C1F76093153, E33A90146C836E9B |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 7 | 162 | 0 | Bedok South Avenue 1, East Coast Park Service Road |
| expressway | East Coast Parkway | 3 | 52 | 0 | Bedok South Avenue 1, - |
| expressway slip road | East Coast Parkway | 1 | 11 | 0 | East Coast Park Service Road |
| expressway slip road | ECP | 1 | 11 | 0 | - |
| major arterial (trunk) | Still Road South | 1 | 27 | 0 | Marine Parade Road |

## Selected: attempt 3, 19.63 km

- Candidate: seed 3
- Duration estimate: 75 min (cycling-road)
- Vertices: 617
- Files: `ride-20km-east-coast-park.geojson`, `ride-20km-east-coast-park.gpx` (same points)
- Repeated ground (out-and-back): 1%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 16.41 | 84% |
| concrete | 2.85 | 15% |
| unknown | 0.37 | 2% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 7.89 | 40% |
| state road | 7.28 | 37% |
| footway | 2.95 | 15% |
| street | 1.50 | 8% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 19.63 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Play Corridor | allowed | 647 | yes | 3F5F73B41C71FB65 |
| TAMPINES PC (BEDOK RES PK-TAMPINES AVE1) | allowed | 122 | yes | 97A1EA00DC9752D1 |
| UPPER EAST COAST RD (BEDOK STH AVE 1-BEDOK RD) | allowed | 256 | yes | B1562C70CF67CFB3, 58838EE848FA8B7F, 8EFC839D2E84261C (+3) |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 7 | 193 | 0 | -, Tampines Avenue 5 |
| expressway | Pan-Island Expressway | 2 | 44 | 0 | -, Tampines Avenue 5 |
| expressway slip road | Tampines Avenue 5 | 1 | 21 | 0 | Tampines Avenue 5 |

# ride-50km-bishan-amk-park

Activity: ride

Start query: `bishan-ang mo kio park` (resolved: confirmed by the user as BISHAN - ANG MO KIO PARK (POND GARDENS))

Start: BISHAN - ANG MO KIO PARK (POND GARDENS), BISHAN - ANG MO KIO PARK (POND GARDENS) (1.36517, 103.83630)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 50 km (accepts 45.00-55.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 49.74 | accepted | none | 0.44 | 9% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1969

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.8362982266298,
      1.365170695914691
    ]
  ],
  "options": {
    "round_trip": {
      "length": 50000,
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

## Selected: attempt 1, 49.74 km

- Candidate: seed 1
- Duration estimate: 140 min (cycling-road)
- Vertices: 1511
- Files: `ride-50km-bishan-amk-park.geojson`, `ride-50km-bishan-amk-park.gpx` (same points)
- Repeated ground (out-and-back): 9%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 48.48 | 97% |
| unknown | 1.01 | 2% |
| concrete | 0.25 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 23.45 | 47% |
| state road | 21.57 | 43% |
| street | 4.05 | 8% |
| footway | 0.63 | 1% |
| cycleway | 0.03 | 0% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 49.74 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Bishan-Ang Mo Kio Park (Pond Gardens) | allowed | 159 | yes | A25328AE38B1018B, 953E5D59A7A2210F, 6E014F7948DBE512 (+4) |
| BEDOK PC (BEDOK RESERVOIR MRT - PIE) | allowed | 129 | yes | 6D999F8451AEC2A5 |
| Bishan-Ang Mo Kio Park (Pond Gardens) | allowed | 157 | yes | 24CDA6BBCE6D85C5, D0126F533B6E2BC7, 3515C10F920278AC (+3) |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 29 | 646 | 0 | Ang Mo Kio Avenue 1, Bartley Road East, Bedok North Avenue 3, -, Republic Avenue, Marina Boulevard, Marina Coastal Drive, Thomson Road |
| expressway | Central Expressway | 3 | 60 | 0 | Ang Mo Kio Avenue 1, Marina Coastal Drive |
| major arterial (trunk) | unnamed | 17 | 572 | 104 | Serangoon Avenue 1, Bartley Road, -, Bartley Road East, Nicoll Highway, Republic Avenue, Balmoral Road |
| major arterial (trunk) | Bartley Road | 3 | 845 | 841 | Serangoon Avenue 1, Bartley Road, - |
| road tunnel | Upper Paya Lebar Underpass | 1 | 11 | 0 | Bartley Road East |
| road tunnel | Upper Paya Lebar Road | 1 | 15 | 0 | Bartley Road East |
| major arterial (trunk) | Bartley Viaduct | 5 | 600 | 58 | Bartley Road East |
| major arterial (trunk) | Hougang Avenue 3 | 1 | 26 | 0 | Bartley Road East |
| expressway | Kallang-Paya Lebar Expressway | 2 | 20 | 0 | Bartley Road East |
| expressway slip road | Airport Road | 1 | 10 | 0 | Bartley Road East |
| major arterial (trunk) | Bartley Road East | 3 | 830 | 357 | Bartley Road East, Kaki Bukit Avenue 4, -, Kaki Bukit Avenue 3, Kaki Bukit Road 4 |
| major arterial (trunk) | Kaki Bukit Avenue 4 | 1 | 219 | 208 | Bartley Road East, Kaki Bukit Avenue 4 |
| bicycle=no | unnamed | 2 | 21 | 0 | Bedok Reservoir Road, - |
| expressway | Pan-Island Expressway | 5 | 74 | 0 | Bedok North Avenue 3, -, Thomson Road |
| major arterial (trunk) | Eunos Link | 1 | 25 | 0 | - |
| expressway slip road | Paya Lebar Way | 1 | 18 | 0 | - |
| major arterial (trunk) | Nicoll Highway | 2 | 1731 | 1731 | Guillemard Road, Nicoll Highway |
| major arterial (trunk) | Republic Avenue | 1 | 12 | 0 | - |
| expressway | East Coast Parkway | 2 | 65 | 0 | Republic Avenue |
| major arterial (trunk) | East Coast Parkway | 1 | 11 | 0 | Republic Avenue |
| expressway slip road | Marina Boulevard | 1 | 22 | 0 | Marina Boulevard |
| expressway slip road | Marina Costal Expressway | 1 | 11 | 0 | Marina Boulevard |
| expressway | Marina Coastal Expressway | 2 | 28 | 0 | Marina Boulevard, Marina Coastal Drive |
| expressway slip road | Marina Link | 1 | 13 | 0 | Marina Coastal Drive |
| major arterial (trunk) | Raffles Quay | 1 | 16 | 0 | Marina Coastal Drive |
| major arterial (trunk) | Robinson Road | 1 | 8 | 0 | Marina Coastal Drive |
| bicycle=no | OG Bridge | 1 | 10 | 0 | Marina Coastal Drive |
| expressway slip road | Central Expressway | 1 | 13 | 0 | Marina Coastal Drive |
| expressway slip road | CTE | 1 | 39 | 0 | Clemenceau Avenue North |
| major arterial (trunk) | Dunearn Road | 2 | 27 | 0 | -, Balmoral Road |
| major arterial (trunk) | Bukit Timah Road | 2 | 567 | 578 | - |
| major arterial (trunk) | MacRitchie Viaduct | 2 | 90 | 0 | Thomson Road |
| major arterial (trunk) | Lornie Viaduct | 2 | 100 | 0 | Thomson Road |

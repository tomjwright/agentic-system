# ride-50km-pasir-ris-park-via

Activity: ride

Start query: `pasir ris park` (resolved: confirmed by the user as PASIR RIS BEACH PARK)

Start: PASIR RIS BEACH PARK, 2 PASIR RIS LANE PASIR RIS BEACH PARK SINGAPORE 519170 (1.38100, 103.94713)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 50 km (accepts 45.00-55.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | via 4 points | 46.54 | accepted | none | 2.66 | 3% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1961

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.9471253158095,
      1.380999388858507
    ],
    [
      103.9105,
      1.4192
    ],
    [
      103.865,
      1.416
    ],
    [
      103.844,
      1.362
    ],
    [
      103.925,
      1.341
    ],
    [
      103.9471253158095,
      1.380999388858507
    ]
  ],
  "options": {
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

## Selected: attempt 1, 46.54 km

- Candidate: via 4 points
- Duration estimate: 130 min (cycling-road)
- Vertices: 1263
- Files: `ride-50km-pasir-ris-park-via.geojson`, `ride-50km-pasir-ris-park-via.gpx` (same points)
- Repeated ground (out-and-back): 3%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 44.95 | 97% |
| unknown | 1.44 | 3% |
| wood | 0.14 | 0% |
| paved | 0.01 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 31.74 | 68% |
| state road | 12.97 | 28% |
| cycleway | 0.66 | 1% |
| footway | 0.60 | 1% |
| street | 0.58 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 46.54 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Rowers Bay to TPE | allowed | 676 | yes | 73E9282B777C883C |
| Rowers Bay to TPE | allowed | 530 | yes | 73E9282B777C883C |
| Rowers Bay to TPE | allowed | 505 | yes | 73E9282B777C883C |
| MARYMOUNT ROAD | allowed | 357 | yes | 07E34A2A72CC1939 |
| BEDOK RESERVOIR PK | allowed | 243 | yes | 5DDFDF05D07838E1, F81550CAB9ACA54D |
| BEDOK RESERVOIR PK | allowed | 223 | yes | F81550CAB9ACA54D, 5DDFDF05D07838E1 |
| TAMPINES PC (BEDOK RES PK-TAMPINES AVE1) | allowed | 122 | yes | 97A1EA00DC9752D1 |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 21 | 749 | 0 | Pasir Ris Industrial Drive 1, -, Yio Chu Kang Road, Bishan Street 11, Bartley Road East, Tampines Avenue 12 |
| expressway slip road | Halus Link | 1 | 11 | 0 | Pasir Ris Industrial Drive 1 |
| expressway | Tampines Expressway | 3 | 53 | 0 | -, Tampines Avenue 12 |
| expressway | Central Expressway | 1 | 11 | 0 | Yio Chu Kang Road |
| major arterial (trunk) | unnamed | 10 | 485 | 155 | Bishan Street 11, Braddell Road, -, Bartley Road East |
| major arterial (trunk) | Braddell Road | 3 | 1147 | 1120 | Bishan Street 11 |
| major arterial (trunk) | Woodleigh Underpass | 2 | 46 | 0 | Bishan Street 11, Braddell Road |
| major arterial (trunk) | Bartley Road | 3 | 1230 | 1220 | Braddell Road, -, Bartley Road |
| road tunnel | Upper Paya Lebar Underpass | 1 | 11 | 0 | Bartley Road East |
| road tunnel | Upper Paya Lebar Road | 1 | 15 | 0 | Bartley Road East |
| major arterial (trunk) | Bartley Viaduct | 5 | 600 | 58 | Bartley Road East |
| major arterial (trunk) | Hougang Avenue 3 | 1 | 26 | 0 | Bartley Road East |
| expressway | Kallang-Paya Lebar Expressway | 2 | 20 | 0 | Bartley Road East |
| expressway slip road | Airport Road | 1 | 10 | 0 | Bartley Road East |
| major arterial (trunk) | Bartley Road East | 3 | 830 | 357 | Bartley Road East, Kaki Bukit Avenue 4, -, Kaki Bukit Avenue 3, Kaki Bukit Road 4 |
| major arterial (trunk) | Kaki Bukit Avenue 4 | 1 | 219 | 208 | Bartley Road East, Kaki Bukit Avenue 4 |
| bicycle=no | unnamed | 1 | 10 | 0 | Bedok Reservoir Road |
| expressway slip road | Tampines Avenue 12 | 1 | 10 | 0 | Tampines Avenue 12 |
| expressway slip road | Tampines Expressway | 3 | 51 | 0 | Tampines Avenue 12 |
| expressway slip road | Pasir Ris Drive 8 | 1 | 11 | 0 | Tampines Avenue 12 |

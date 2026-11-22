# ride-50km-jurong-lake-gardens

Activity: ride

Start query: `jurong lake gardens` (resolved: confirmed by the user as PASSION WAVE @ JURONG LAKE GARDENS)

Start: PASSION WAVE @ JURONG LAKE GARDENS, 100 YUAN CHING ROAD PASSION WAVE @ JURONG LAKE GARDENS SINGAPORE 618662 (1.33936, 103.72730)

Target: 50 km (accepts 45.00-55.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | - | error | HeiGIT returned 404: Route could not be found - Unable to find a route for point (103.7272995 1.3393596). | | |
| 2 | seed 2 | - | error | HeiGIT returned 500: Could not find a valid point after 3 tries, for the point:1.2292908,103.7762599,7.333000183105469 | | |
| 3 | seed 3 | 55.30 | outside target | none | 2.68 | 6% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1966

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.7272994620431,
      1.339359562086737
    ]
  ],
  "options": {
    "round_trip": {
      "length": 50000,
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

Target not met after 3 attempts. No GPX was written.

## Rejected: attempt 3, 55.30 km

- Candidate: seed 3
- Duration estimate: 152 min (cycling-road)
- Vertices: 1439
- Files: `ride-50km-jurong-lake-gardens.attempt-3.geojson`
- Repeated ground (out-and-back): 6%
- Validation problems: outside target
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 52.57 | 95% |
| unknown | 2.72 | 5% |
| concrete | 0.01 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 26.92 | 49% |
| state road | 26.63 | 48% |
| street | 0.88 | 2% |
| footway | 0.54 | 1% |
| cycleway | 0.33 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 55.30 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| JLG: Lakeside Garden | allowed | 394 | yes | 8C9BFCBD884E6A30, DF2723CF695CB647, F57422B60E0DF6B0 (+3) |
| YUAN CHING ROAD | allowed | 130 | yes | 0A1C22CC8857D10F, C88706AEF59C67D6, DEA108259B41E1CF (+2) |
| Bukit Batok Park Connector | allowed | 112 | yes | DB4DED7CBE1FB0C4, E95CB0BC10383B64, B382A43CA5177B87 (+3) |
| Bukit Batok Park Connector | allowed | 178 | yes | 88C50C975D7E858F |
| Adam PC | allowed | 307 | yes | AE162D7DBBA2B8FB, C2A44104893D91D5, 6B8F13A8D762099B (+2) |
| Adam PC | allowed | 319 | yes | 7AAD94A6F26F3707, D4DE0B63223BD4C3, 86B234712A32EEA5 |
| Bukit Timah PC (btwn King Albert Park - Adam Rd) | allowed | 210 | yes | F7E7F8F843450384 |
| Bukit Timah PC (btwn King Albert Park - Adam Rd) | allowed | 364 | yes | 52D4E7B47F8B3AFF, 416A458FDB2A0DF0, 66A30E76DE69A5BF (+4) |
| Bukit Timah PC (btwn King Albert Park - Adam Rd) | allowed | 361 | yes | 774C7F8F775A8757, C8E221A59581EC1E |
| JLG: Lakeside Garden | allowed | 170 | yes | F57422B60E0DF6B0, DF2723CF695CB647 |
| JLG: Lakeside Garden | allowed | 133 | yes | DF2723CF695CB647, 8C9BFCBD884E6A30 |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway | Pan-Island Expressway | 2 | 62 | 0 | Jurong East Central, Bukit Batok East Avenue 6 |
| expressway slip road | Pan-Island Expressway | 2 | 31 | 0 | Jurong East Central, Bukit Batok East Avenue 6 |
| expressway slip road | unnamed | 12 | 292 | 0 | -, Upper Thomson Road, Bukit Timah Road |
| expressway | Kranji Expressway | 1 | 43 | 0 | - |
| bicycle=no | Jalan Wak Selat | 1 | 10 | 0 | Kranji Road |
| bicycle=no | unnamed | 1 | 11 | 0 | - |
| bicycle=no | Mandai Road Track 16 | 1 | 14 | 0 | - |
| expressway slip road | Mandai Road | 3 | 55 | 0 | - |
| expressway | Bukit Timah Expressway | 2 | 34 | 0 | - |
| expressway slip road | Bukit Timah Expressway | 1 | 11 | 0 | - |
| expressway slip road | Seletar Expressway | 2 | 54 | 0 | - |
| expressway | Seletar Expressway | 1 | 44 | 0 | Mandai Road |
| expressway slip road | Upper Thomson Road | 1 | 10 | 0 | Upper Thomson Road |
| major arterial (trunk) | MacRitchie Viaduct | 2 | 1162 | 1154 | -, MacRitchie Viaduct |
| major arterial (trunk) | Lornie Viaduct | 1 | 11 | 0 | MacRitchie Viaduct |
| major arterial (trunk) | Lornie Road | 1 | 185 | 196 | MacRitchie Viaduct |
| major arterial (trunk) | Lornie Highway | 4 | 1528 | 1550 | MacRitchie Viaduct |
| major arterial (trunk) | unnamed | 6 | 82 | 0 | MacRitchie Viaduct, Adam Road, Bukit Timah Road, Jalan Jurong Kechil |
| major arterial (trunk) | Adam Road | 3 | 1392 | 1410 | MacRitchie Viaduct, Adam Road |
| major arterial (trunk) | Dunearn Road | 1 | 6 | 0 | Adam Road |
| major arterial (trunk) | Bukit Timah Road | 3 | 4162 | 4192 | Bukit Timah Road |
| major arterial (trunk) | Farrer Road | 1 | 11 | 0 | Bukit Timah Road |
| major arterial (trunk) | Jalan Anak Bukit | 1 | 9 | 0 | Bukit Timah Road |
| major arterial (trunk) | Upper Bukit Timah Road | 3 | 437 | 351 | Bukit Timah Road |
| expressway slip road | Pan Island Expressway | 1 | 10 | 0 | Bukit Timah Road |

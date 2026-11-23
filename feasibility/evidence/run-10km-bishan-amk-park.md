# run-10km-bishan-amk-park

Activity: run

Start query: `bishan-ang mo kio park` (resolved: confirmed by the user as BISHAN - ANG MO KIO PARK (POND GARDENS))

Start: BISHAN - ANG MO KIO PARK (POND GARDENS), BISHAN - ANG MO KIO PARK (POND GARDENS) (1.36517, 103.83630)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 10 km (accepts 9.00-11.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | repeated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seed 1 | 10.04 | accepted | none | 0.88 | 1% |

Provider: HeiGIT openrouteservice `foot-walking`, engine 10.1.1, graph 2026-11-16T00:26:59Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1976

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

## Selected: attempt 1, 10.04 km

- Candidate: seed 1
- Duration estimate: 120 min (foot-walking)
- Vertices: 397
- Files: `run-10km-bishan-amk-park.geojson`, `run-10km-bishan-amk-park.gpx` (same points)
- Repeated ground (out-and-back): 1%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| concrete | 4.71 | 47% |
| unknown | 3.28 | 33% |
| asphalt | 1.97 | 20% |
| paving stones | 0.08 | 1% |

Way types:

| value | km | share |
| --- | --- | --- |
| footway | 6.72 | 67% |
| cycleway | 2.36 | 24% |
| street | 0.78 | 8% |
| steps | 0.11 | 1% |
| state road | 0.06 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 9.89 | 99% |
| steps | 0.11 | 1% |
| ford | 0.06 | 1% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| Bishan-Ang Mo Kio Park (Pond Gardens) | allowed | 286 | yes | A25328AE38B1018B, 536A6AA9CBF55B87, 2DA4A7CB364CCAAC (+6) |
| Bishan-Ang Mo Kio Park (Pond Gardens) | allowed | 596 | yes | 1B527CA038BCCF05, 3515C10F920278AC, 9E7A933321A51B29 (+3) |

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| major arterial (trunk) | unnamed | 1 | 17 | 0 | - |
| major arterial (trunk) | Braddell Road | 1 | 23 | 0 | - |
| major arterial (trunk) | Lornie Viaduct | 1 | 33 | 0 | Marymount Road |
| bicycle=no | unnamed | 1 | 29 | 7 | - |

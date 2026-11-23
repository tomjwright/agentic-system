# core-ride-60-70km-green-track

Activity: ride

Start query: `avenue south residence` (resolved: single building whose name matches the query)

Start: AVENUE SOUTH RESIDENCE, 11 SILAT AVENUE AVENUE SOUTH RESIDENCE SINGAPORE 168877 (1.27663, 103.82911)

OneMap notice: Authentication token missing. Please create an account and generate or renew your API Token.

Target: 60-70 km (accepts 60.00-70.00 km)

## Attempts

| attempt | candidate | km | outcome | problems | allowed green km | longest green km | repeated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | via 18 points | 68.25 | accepted | none | 21.91 | 10.71 | 6% |

Provider: HeiGIT openrouteservice `cycling-road`, engine 10.1.1, graph 2026-11-15T22:56:27Z, OSM 2026-11-15T00:00:00Z

Attribution: openrouteservice.org | OpenStreetMap contributors

HeiGIT x-ratelimit-remaining: 1958

First measured request body (the key is only in the Authorization header):

```json
{
  "coordinates": [
    [
      103.8291052120283,
      1.276629534107344
    ],
    [
      103.88796,
      1.2946
    ],
    [
      103.89701,
      1.29559
    ],
    [
      103.90599,
      1.29817
    ],
    [
      103.91501,
      1.30104
    ],
    [
      103.92401,
      1.3036
    ],
    [
      103.93304,
      1.30765
    ],
    [
      103.94197,
      1.30913
    ],
    [
      103.95098,
      1.31144
    ],
    [
      103.96005,
      1.3148
    ],
    [
      103.96901,
      1.31633
    ],
    [
      103.97525,
      1.31693
    ],
    [
      103.98311,
      1.31689
    ],
    [
      103.99077,
      1.31567
    ],
    [
      103.99902,
      1.3121
    ],
    [
      104.01924,
      1.32608
    ],
    [
      104.02967,
      1.35091
    ],
    [
      104.01362,
      1.36608
    ],
    [
      103.92,
      1.34
    ],
    [
      103.8291052120283,
      1.276629534107344
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

## Selected: attempt 1, 68.25 km

- Candidate: via 18 points
- Duration estimate: 304 min (cycling-road)
- Vertices: 1685
- Files: `core-ride-60-70km-green-track.geojson`, `core-ride-60-70km-green-track.gpx` (same points)
- Repeated ground (out-and-back): 6%
- Validation problems: none
- Provider warnings: Extra info requested but not available: roadaccessrestrictions

Surfaces (HeiGIT extra_info):

| value | km | share |
| --- | --- | --- |
| asphalt | 64.39 | 94% |
| unknown | 3.03 | 4% |
| concrete | 0.75 | 1% |
| paved | 0.08 | 0% |

Way types:

| value | km | share |
| --- | --- | --- |
| road | 21.93 | 32% |
| state road | 20.89 | 31% |
| cycleway | 19.90 | 29% |
| footway | 3.46 | 5% |
| construction | 1.25 | 2% |
| street | 0.82 | 1% |

Way categories:

| value | km | share |
| --- | --- | --- |
| none of these | 68.25 | 100% |

Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):

| park | cycling | m | counts | NParks track IDs |
| --- | --- | --- | --- | --- |
| EAST COAST PARK AREA B | allowed | 2007 | yes | C94DDE625F08166D, 817727C0AE29B96B, A24C2B98C0492A18 (+3) |
| EAST COAST PARK AREA B | allowed | 399 | yes | 817727C0AE29B96B |
| EAST COAST PARK AREA B | allowed | 784 | yes | 817727C0AE29B96B |
| EAST COAST PARK AREA C | allowed | 465 | yes | 34AEAA48C0BA65E2, A2C2FD9A71FC2D5D, 5F3D6CC6CA25A27E (+2) |
| EAST COAST PARK AREA D | allowed | 746 | yes | 83541BBA9A24E4A4, 0447C764A3F5B5C3, 2C5CCE66DD452653 (+3) |
| EAST COAST PARK AREA D | allowed | 116 | yes | FA1633E2B75F65CB, 7C3FB49460D7497C, 5EFF0A7AB6DFAAF8 |
| EAST COAST PARK AREA D | allowed | 163 | yes | FA1633E2B75F65CB, A29C2016E646F4DE |
| EAST COAST PARK AREA D | allowed | 190 | yes | FA1633E2B75F65CB |
| EAST COAST PARK AREA E | allowed | 488 | yes | 5E53B02ED6171F45, 4DF6AA45789F3A5E, E786E88120F73B00 (+1) |
| EAST COAST PARK AREA E | allowed | 395 | yes | 5E53B02ED6171F45, 0F212808465C9D9D, D669277C6DDE8817 (+1) |
| EAST COAST PARK AREA E | allowed | 197 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA E | allowed | 604 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA E | allowed | 197 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA F | allowed | 146 | yes | 550299B2A8F5071B |
| EAST COAST PARK AREA E | allowed | 266 | yes | 5E53B02ED6171F45 |
| EAST COAST PARK AREA G | allowed | 1203 | yes | 310A6C9D513D0416, 9052965FE6F0FAD7, AE927B4D9B9BFFDF |
| EAST COAST PARK AREA G | allowed | 1573 | yes | 310A6C9D513D0416, D6E5D8F2017F05D5, AE927B4D9B9BFFDF |
| COASTAL PC | allowed | 1122 | yes | 8785033D32609922, F9F04CBD2C2D108C, 581FFF3F17ACFB85 |
| COASTAL PC | allowed | 491 | yes | 8785033D32609922 |
| COASTAL PC | allowed | 1384 | yes | 8785033D32609922 |
| COASTAL PC | allowed | 197 | yes | 8785033D32609922 |
| COASTAL PC | allowed | 130 | yes | 8785033D32609922 |
| COASTAL PC | allowed | 4458 | yes | 8785033D32609922 |
| COASTAL PC | allowed | 292 | yes | 8785033D32609922 |
| COASTAL PC | allowed | 322 | yes | 8785033D32609922 |
| LOYANG PC | allowed | 875 | yes | 803D063DC7D0EACC, 3643CA3A4E7E48B8 |
| LOYANG PC | allowed | 436 | yes | 5EFBEA2493079DA9, E6B159D4595DDBBE |
| LOYANG PC | allowed | 632 | yes | CA7654BB8ABAE9C7, 88DB255C42F32E98 |
| TAMPINES AVE 2 NR BLK285 (OHB3) | allowed | 165 | yes | 90957337B15C9E12 |
| BEDOK RESERVOIR PK | allowed | 1250 | yes | 5DDFDF05D07838E1, 9D975430C1D51596 |
| Kallang Riverside Park | allowed | 218 | yes | D1AD3A8EBA846C77, 5CD838D8AA7F4E3E, C4D05D57D10E98E8 (+2) |

Longest contiguous cycling-allowed green: 10.71 km (plus 199 m of junctions and crossings bridged; EAST COAST PARK AREA B, EAST COAST PARK AREA C, EAST COAST PARK AREA D, EAST COAST PARK AREA E, EAST COAST PARK AREA F, EAST COAST PARK AREA G; NParks track IDs: C94DDE625F08166D, 817727C0AE29B96B, A24C2B98C0492A18, BBCD0C988B84B2C0, 15AFAA8A55F2A1E2, 81F55AC5E830BE17, AFCEE630DCEEAF16, D9A79C1F76093153, 34AEAA48C0BA65E2, A2C2FD9A71FC2D5D, 5F3D6CC6CA25A27E, 2097D2332D556C8C, 01D7E8CEF74BC011, 290EF78444F217A1, C2C2A13BBFAACFFC, 32D8993F8598F5A9, 83541BBA9A24E4A4, 0447C764A3F5B5C3, 2C5CCE66DD452653, FA1633E2B75F65CB, 4F86406B9A97BC3D, 9267974C09F963BD, AA365F5AA89A5E85, 7C3FB49460D7497C, 5EFF0A7AB6DFAAF8, A29C2016E646F4DE, 9757927ED95973A1, DFF13B6A9865B58C, 5E53B02ED6171F45, 4DF6AA45789F3A5E, E786E88120F73B00, 89538159580F588B, 0F212808465C9D9D, D669277C6DDE8817, F67130B67E15BC6D, 56C3BDC13EF797D1, CA58050BFDEDD28B, CDF43DD5987BA799, 5561E227A2657F3B, 550299B2A8F5071B, 7A0E7B44D27AB73E, 310A6C9D513D0416, 9052965FE6F0FAD7, AE927B4D9B9BFFDF, D6E5D8F2017F05D5)

Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);
on = route edges lying on the road itself (routing along it):

| kind | OSM name | contacts | near m | on m | HeiGIT step names there |
| --- | --- | --- | --- | --- | --- |
| expressway slip road | unnamed | 18 | 497 | 0 | Jalan Bukit Merah, Stadium Drive, Stadium Way, Fort Road, Loyang Avenue, -, Geylang Road |
| major arterial (trunk) | Rochor Road | 2 | 21 | 0 | Coleman Street, - |
| major arterial (trunk) | Ophir Road | 2 | 26 | 0 | Coleman Street, - |
| major arterial (trunk) | Nicoll Highway | 2 | 941 | 900 | Java Road, - |
| major arterial (trunk) | unnamed | 5 | 269 | 206 | -, Stadium Drive, Bedok Reservoir Road |
| expressway | Kallang-Paya Lebar Expressway | 5 | 496 | 0 | Stadium Drive, Stadium Walk, Stadium Way, Geylang Road |
| expressway | East Coast Parkway | 2 | 19 | 0 | Fort Road |
| expressway slip road | East Coast Parkway | 1 | 10 | 0 | Fort Road |
| bicycle=no | Tanah Merah Coast Road | 1 | 31 | 0 | Tanah Merah Coast Road |
| bicycle=no | unnamed | 6 | 129 | 0 | Tanah Merah Coast Road, Changi Coast Road, Bedok Reservoir Road |
| expressway slip road | Tampines Viaduct | 1 | 21 | 0 | Loyang Avenue |
| expressway | Tampines Expressway | 1 | 11 | 0 | Loyang Avenue |
| major arterial (trunk) | Eunos Link | 1 | 25 | 0 | Bedok Reservoir Road |
| expressway slip road | Paya Lebar Way | 1 | 18 | 0 | - |
| expressway | Pan-Island Expressway | 1 | 14 | 0 | - |
| bicycle=no | Kampong Bugis | 1 | 11 | 0 | Geylang Road |

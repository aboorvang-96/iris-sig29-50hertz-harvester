# Fixture manifest

All HTML pages were saved manually in a browser on **28 October 2026** from
`https://www.50hertz.com` (English offshore-project pages). The copies in this
directory are unmodified raw page saves and are used by the offline tests.

| Page | Source URL | Fixture | Bytes | SHA-256 |
|---|---|---|---|---|
| OST-6-1 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/GridconnectionOST-6-1 | `OST-6-1.html` | 163708 | `D590F89CEF8D630635AEA4EAD94F11C26C269E0A08E47553D9FCD79055345A5F` |
| Ostwind 2 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind2 | `Ostwind 2.html` | 167026 | `784300370737E379226C7AA09AB040C9802AD31F732AB9960A356DB71E9A557D` |
| Ostwind 3 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind3 | `Ostwind 3.html` | 200556 | `69E81F3699E1DE3DA290A47AD823C76611BB35FF6F081C14FD031079148C2FF6` |
| Ostwind 4 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind4 | `Ostwind 4.html` | 179682 | `4F4F4E7463C8FC2CD38ACB41B135E5CE8BBD96D5053C8D95D24CE15D4962CC1B` |

## robots.txt

`robots.txt` was saved from `https://www.50hertz.com/robots.txt` on the same
date. Size: 4365 bytes. SHA-256:
`E609D2C20F8B6D3B58E3F8D8D851C1145E7429AED7F723CD369D7DF2EF9E57E3`.

The wildcard (`User-agent: *`) rules disallow paths such as `/admin/`,
`/images/` and `/DesktopModules/`; they do not disallow
`/en/Grid/Griddevelopement/Offshoreprojects/...`.

## Gazetteer

`gazetteer.csv` is a small curated lookup, not an external geocoding service:

- **Lubmin** — village centre, approximate; the substation was not found by
  name in OpenStreetMap. Coordinate supplied with the project fixture.
- **Gnewitz** — village centre, approximate; the under-construction Gnewitz
  substation was not resolved by name. Coordinate obtained from the
  OpenStreetMap Nominatim query recorded in the CSV.
- **Stilow** — village centre, approximate; the planned Stilow substation was
  not resolved by name. Coordinate obtained from the OpenStreetMap Nominatim
  query recorded in the CSV.

All three entries are marked `precision=approximate`, so the harvester records
`geom_status='approximate'`. The source column in the CSV contains the exact
OpenStreetMap attribution and query URL, accessed 2026-10-28.

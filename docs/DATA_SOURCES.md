# Indore data-source research and inventory

Research/retrieval: **17 September 2026 UTC**. Pilot map extent: 75.850–75.865 E, 22.710–22.725 N (Rajwada and central Indore). OSM map API returns full geometries crossing the requested box and referenced objects, so the stored feature extent can extend beyond it. District context covers a much larger area.

The exact retrieval timestamps, checksums, request URL, format derivatives and source fields are in [`data/inventory.json`](../data/inventory.json). Raw source responses are retained under `data/raw`; Docker only needs the prepared extracts. Sources were researched before implementation; access gaps are intentional and visible in the interface.

| Source / dataset | Access and licence | CRS / epoch | Use and limitation |
|---|---|---|---|
| OpenStreetMap building ways | Downloaded via OSM map API; ODbL 1.0 | WGS84 EPSG:4326; current downloaded state; actual survey dates unknown | 8,826 building polygons. Edit timestamps retained, not represented as survey dates. These are **not parcels**. |
| OpenStreetMap highway ways | Same API and licence | Original EPSG:4326; demonstration GeoPackage EPSG:3857 | 601 road features. Centreline geometry, not rights of way. No coordinate perturbation. |
| OpenStreetMap amenity nodes | Same API and licence | Longitude/latitude EPSG:4326; CSV derivative | 275 points. Point-to-footprint relationships are candidates only; no title linkage. |
| OpenStreetMap waterway ways | Same API and licence | EPSG:4326 | 3 lines; contextual hydrography, not legal setback lines. |
| Historical OSM building `way/702251646`, version 1 | Read-only OSM history API; ODbL 1.0 | EPSG:4326; edit epoch 7 July 2019 | One earlier footprint reconstructed using node versions at that epoch. Compared to the real current version, never synthetically shifted. Same source family, not an independent survey. |
| geoBoundaries gbOpen IND ADM2, release commit `9469f09` | Downloaded from public release; metadata states Open Data Commons Open Database License 1.0 | EPSG:4326; boundary year represented **2021**, source update **19 Jan 2023**, build **12 Dec 2023** | One simplified Indore district feature. Credits Pathways Data Pvt. Ltd. and lgdirectory.gov.in. Third-party administrative context, not official cadastral geometry. |
| MP Bhulekh | Official land-record portal; no open bulk geometry reuse licence verified | Product dependent / unverified | No automated download. Authorized anonymized officer-supplied extracts can be imported. |
| MP Directorate of Town & Country Planning | Public Indore Development Plan 2021 and land-use maps listed | Plan horizon **2021**; not a collection date. Download CRS unverified | No redistribution licence or usable parcel-vector feed verified. Planning evidence must not be relabelled as title evidence. Not bundled. |
| District Indore GIS | Official district page describes public infrastructure and land-use viewer | Unverified | Bulk export and reuse permission not verified. Viewer not scraped. |
| ISRO/NRSC Bhuvan | General terms restrict bulk extraction, derivative works and redistribution without authorization | Product dependent | Not bundled or scraped. Product-specific permissions are required before integration. |
| Survey of India Online Maps | FAQ lists free PDFs/selected boundaries and category-dependent vector access | Product dependent; topographic maps often UTM/WGS84 | No verified licensed Indore cadastral download. General topographic products do not establish parcel title. |
| data.gov.in | Searched for Indore geospatial/ward/parcel resources | No qualifying dataset verified | No openly licensed downloadable parcel fabric identified in this search. This does not establish that no such dataset exists. |

## Source references

- [OSM copyright and licence](https://www.openstreetmap.org/copyright) and [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [Actual bounded OSM map request](https://api.openstreetmap.org/api/0.6/map?bbox=75.850,22.710,75.865,22.725)
- [geoBoundaries IND ADM2 metadata](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/) and [API documentation](https://www.geoboundaries.org/api.html)
- [Indore T&CP planning inventory](https://www.mptownplan.gov.in/plan_Indore.html)
- [Indore Development Plan publication summary](https://mptownplan.gov.in/New_Folder_%282%29/summary.htm)
- [District Indore GIS description](https://indore.nic.in/en/indore-gis/)
- [Bhuvan terms](https://bhuvan.nrsc.gov.in/terms.php)
- [Survey of India FAQ](https://onlinemaps.surveyofindia.gov.in/FAQs.aspx)
- [MP Bhulekh](https://mpbhulekh.gov.in/)
- [Official district reference to MP Bhulekh](https://sidhi.nic.in/service/%E0%A4%AD%E0%A5%82%E0%A4%AE%E0%A4%BF-%E0%A4%B0%E0%A4%BF%E0%A4%95%E0%A5%89%E0%A4%B0%E0%A5%8D%E0%A4%A1%E0%A5%8D%E0%A4%B8/)
- [Open Government Data platform](https://www.data.gov.in/)

## Acquisition and transformations

The attempted Overpass queries returned 406/429/504. The official OSM map API successfully returned the bounded extract. Full raw XML is preserved; prepared features contain a whitelist of descriptive mapping tags and OSM feature identifiers. OSM usernames are not part of the canonical schema or processed features. No private landowner information was requested.

OSM buildings/roads/waterways are derived from simple ways, not multipolygon relations. Amenity extraction uses nodes only. This deliberately bounded extraction is incomplete. Large buildings represented solely by multipolygon relations may be absent. The API's selected ways can extend outside the request box. The code neither invents parcels nor fills missing urban coverage.

`prepare_demo.py` reprojects the roads into Web Mercator GeoPackage and serializes amenities into CSV. Original WGS84 GeoJSONs stay available. This demonstrates format/CRS harmonization without inventing a second survey or artificially displacing a boundary. All processing measurements use WGS84 / UTM 43N, EPSG:32643; display uses Web Mercator, and portable GeoJSON/CSV exports use WGS84.

These six thematic/reference datasets represent **two source families**, not six independent surveying authorities. There is no surveyed accuracy claim. Similarity and topology observations require officer review and, where needed, field verification.

The historical example is deliberately limited to one matching OSM identifier. Its source metadata declares `comparison_scope_ids`, so unrelated current buildings are not falsely called unmatched against this one-feature historical sample. [The public way history](https://www.openstreetmap.org/way/702251646/history) records changed vertices in version 4 (28 February 2021). The saved node histories verify the version-1 coordinates as of 7 July 2019. Contact tags are excluded from the prepared dataset.

# Verified real-data demonstration

This demonstration was run against the working React/OpenLayers frontend and FastAPI/PostGIS backend. Final packaged checks used Docker Compose. No source geometry was artificially displaced to create a result.

## Loaded data

Six reference datasets, **9,707 records**:

| Dataset | Records | Input format | Input CRS |
|---|---:|---|---|
| Current OSM building footprints | 8,826 | GeoJSON | EPSG:4326 |
| OSM roads | 601 | GeoPackage derivative | EPSG:3857 |
| OSM amenity points | 275 | CSV derivative | EPSG:4326 |
| OSM waterways | 3 | GeoJSON | EPSG:4326 |
| Indore district reference | 1 | GeoJSON | EPSG:4326 |
| Real historical OSM footprint | 1 | GeoJSON reconstructed from version history | EPSG:4326 |

PostGIS confirmed **9,707** non-null stored projected geometries with SRID **32643**, using PostGIS **3.4**. Alembic migration **001** was applied. Prepared data files, exact identifiers, licences, collection limitations and checksums are in `data/inventory.json`.

## Genuine discrepancy

The feature is [OSM way 702251646](https://www.openstreetmap.org/way/702251646/history), whose current public label is **Neelkamal Matching Centre (Fabric Mall)**. The historical version-1 footprint was reconstructed at **2019-07-07 14:59:10 UTC** using the way's original node references and the node versions valid at that time. Version 4, dated **2021-02-28 12:12:11 UTC**, changes the vertex sequence and footprint extent. The current extract retains that later geometry.

All measurements were calculated in EPSG:32643:

| Evidence | Observed value |
|---|---:|
| Intersection over union | 0.32290 |
| Centroid distance | 5.855 m |
| Area difference | 111.772 m² |
| Difference relative to larger footprint | 67.71% |
| Maximum boundary displacement (Hausdorff) | 10.795 m |
| Deterministic similarity score | 43.0 / 100 |

Score contributions: IoU **19.7** points, centroid proximity **17.9** points and area agreement **5.4** points. Names and parcel references were absent in one or both records and therefore omitted from the normalized score. This is a similarity ranking, **not a probability or measured survey accuracy**.

This is an observed **temporal mapping discrepancy**. The history demonstrates changed mapped geometry, not necessarily physical construction, legal parcel change or an encroachment.

## Completed review and exports

The actual browser review action was **Accept**, by the local label **Pilot reviewer**, at **2026-09-17T16:08:51.356588+00:00**. The stored note limits acceptance to the historical/current mapping observation and explicitly retains both geometries without a cadastral or real-world accuracy determination. The database restart and transition from the development server to the Docker stack preserved the decision.

Reviewed exports were generated in **GeoJSON, CSV and GeoPackage**. Each contains the two reviewed features plus a validation report, licence information and the audit trail. The exported GeoPackage was reopened with GeoPandas: **2 features**, CRS **EPSG:32643**, **0 invalid exported geometries**. Embedded file SHA-256 values matched the report in all three formats.

Saved evidence:

- [`artifacts/demo/verification.json`](../artifacts/demo/verification.json): actual persisted decision, measurements, dataset counts and export checksums.
- [`artifacts/demo/indore-reviewed-geojson.zip`](../artifacts/demo/indore-reviewed-geojson.zip)
- [`artifacts/demo/indore-reviewed-csv.zip`](../artifacts/demo/indore-reviewed-csv.zip)
- [`artifacts/demo/indore-reviewed-gpkg.zip`](../artifacts/demo/indore-reviewed-gpkg.zip)
- [`artifacts/demo/validation-report.json`](../artifacts/demo/validation-report.json)
- [`artifacts/demo/audit.json`](../artifacts/demo/audit.json)

The existing development project retains **102 superseded findings** from an earlier classification rule. That rule incorrectly treated building/amenity vocabulary differences as conflicts; it was corrected and regression-tested. They remain explicitly superseded in history rather than being silently deleted. A fresh import under the corrected rule generates **463 candidate relationships, one boundary-displacement finding and one area-difference finding**. One of those is accepted in the delivered project; unresolved candidate matches are deliberately left for human review.

## Verification

- Production frontend build passes with TypeScript checking and separate OpenLayers bundle.
- **18 tests pass inside the Linux Docker API container**, including actual historical-data geometry regression, coordinate transforms, format ingestion, invalid geometries, topology, scores, review versioning, hostile input, raster preview and all export formats.
- Windows local tests also pass. The suites use isolated temporary databases; test geometries are not demo data.
- The real browser flow loaded data, inspected source evidence, accepted the historical discrepancy and exercised export. Final UI checks include layer controls, comparisons, filters, source catalogue, dialogs and a narrow viewport.
- The final 390 × 844 responsive check showed no horizontal document overflow and kept the finding and source evidence reachable. Desktop checks corrected a compressed layer list and short-screen overflow. Visible text contrast was sampled against computed backgrounds; this is not a claim of a complete accessibility certification. The final browser console had no captured errors.
- Remaining dependency deprecation warnings are documented by test output; there are no failing tests.

To reproduce on a new database, start Compose, load the reference pack, choose **Boundary displacement** in the review queue, inspect its source evidence and record your own decision. A preaccepted decision is not hardcoded into application source.

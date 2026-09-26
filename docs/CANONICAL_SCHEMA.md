# Canonical schema v1

Feature geometry is separate from attributes. Coordinates are transformed to EPSG:32643 for processing and stored as WKT plus a generated PostGIS Geometry; WGS84 geometry supports map transfer. Original input geometry is retained in its source CRS.

| Canonical field | Meaning | Missing values / conversion |
|---|---|---|
| `record_id` | Source record identifier | Alias mapping from source_id/id/osm_id/shapeID; no invented legal identifier |
| `parcel_ref` | Khasra/survey/plot reference supplied by a legitimate dataset | Null when missing; OSM object IDs are never relabelled as Khasra numbers |
| `name` | Public feature label | Null permitted; not an ownership field |
| `land_use` | Source classification such as building, amenity or landuse | Source classification, not a certified land-use designation |
| `recorded_area_m2` | Area explicitly supplied in square metres | Must be finite and nonnegative; invalid values create a warning and are not guessed |
| `survey_date` | Actual observation/survey date when supplied | OSM edit timestamp is not auto-mapped to survey date |
| `observation_accuracy_m` | Reported horizontal positional accuracy for a GNSS or ground-truth observation | Must be a nonnegative metre value; it adjusts only the review tolerance, never source coordinates |
| `elevation_m` | Supplied point elevation | Must be finite; it is preserved as evidence and is not an inferred terrain value |
| `utility_type` | Source-provided network/asset classification | Null when absent; it does not disclose protected network detail by itself |
| `survey_method` | Source-provided survey instrument or fix method | Null when absent; it is not a quality certification |

The UI shows the selected source field for each canonical field. Automatic suggestions use explicit case-insensitive aliases only. Reviewers can replace each mapping. No LLM is used. Changing mappings is audited and supersedes affected pending evidence. The full source attribute dictionary remains separate.

`area_parse_warning` is a diagnostic field, not a source attribute. `measured_area_m2` is calculated from the current projected geometry and appears in inspection/export; it is distinct from recorded area.

## Tables

- `datasets`: UUID, name, role, status, source JSON, inspection JSON, field_mapping JSON, original_path, sha256, created_at.
- `features`: UUID, dataset_id, source_id, original_geometry JSON, geometry JSON (WGS84), geom_wkt (UTM43N), attributes JSON, canonical JSON. PostGIS migration adds generated `geom_utm` and a GiST index.
- `issues`: UUID, unique revision-sensitive fingerprint, check kind, severity, title, feature_ids JSON, explainable evidence JSON, proposed_geometry, status, version, created_at.
- `decisions`: UUID, issue_id, action, reviewer label, required note, timestamp, before JSON and after JSON. Append only through the application.
- `events`: monotonic sequence, UTC timestamp, action and detail JSON. Import/mapping/analysis/review/export provenance.
- `jobs`: UUID, kind, status, progress, message, result, created_at and updated_at.

Dataset roles: building, parcel, road, utility, amenity, waterway, boundary, survey_point, ground_truth, gnss, record, coverage, raster, orthophoto, DSM and DTM. GeoTIFF roles are stored as raster data with their declared role in provenance. A district boundary is `boundary`, never automatically expected parcel `coverage`.

Issue states: pending, accepted, rejected, edited, superseded. A human decision needs the expected version and pending state. There is no irreversible writeback to an official source or certification system.

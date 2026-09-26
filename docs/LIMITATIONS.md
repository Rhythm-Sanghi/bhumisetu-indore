# Known limits and deployment conditions

## Data and interpretation

- No verified licensed cadastral parcel fabric, official survey control points, ownership register or high-resolution imagery for Indore is bundled. Officer-provided legally accessible anonymized records can be imported. No fabricated integration is claimed.
- Building, road and amenity datasets come from OSM and share source lineage. geoBoundaries district context is a separate third-party administrative source. These are not multiple independent parcel surveys.
- OSM timestamps record edits, not survey collection dates. Completeness, positional accuracy and vertical tags vary. The simple-way/node extract omits multipolygon relations. Administrative boundaries are simplified and may be dated.
- A real geometric discrepancy is not proof of a real-world error, encroachment, title conflict or unlawful land use. Accepting a finding acknowledges it for this local review; it does not certify it.
- No accuracy figure, machine-learning performance or confidence calibration has been evaluated. Deterministic score components are inspectable; weights and thresholds are pilot engineering defaults requiring local validation.

## Implemented scope

- CRS harmonization relies on declared/georeferenced coordinates. DSM/DTM elevation statistics and a hillshade preview are available, but rubber-sheet registration, datum-shift estimation, control-point fitting, imagery extraction, raster change detection and ML are not implemented. No AI is added for presentation.
- KML supports Point, LineString and Polygon placemarks including polygon holes. MultiGeometry is explicitly rejected; KMZ, network links and remote resources are not fetched.
- Shapefiles must be supplied in a ZIP with .shp/.shx/.dbf; missing .prj requires an explicit CRS. One Shapefile per archive. GeoPackages with multiple layers require the desired layer name.
- CSV recognizes longitude/latitude, lon/lat, x/y or easting/northing. Projected columns require a CRS declaration. Nonspatial records match by exact identifier; ambiguous/freeform address geocoding is not supplied.
- `recorded_area_m2` must already be square metres. Hectare/bigha/local unit conversion is not inferred. Null means missing evidence, not zero.
- Matching uses candidate ranking, not globally unique assignment or legally meaningful identifier reconciliation. At most three candidates per source feature are shown. Dated compatible vectors can create a temporal-change finding when displacement exceeds the documented threshold; resolve ambiguity using source evidence.
- Gaps require explicit expected parcel coverage. Sparse building coverage never creates a fake parcel-gap result.
- GeoTIFF preview is a normalized first band. GeoTIFF data are reprojected and retained but are not merged into the reviewed vector export. Derived raster path is retained in project storage.
- The bounded upload limits and in-process queue suit a local pilot; large-city/large-raster processing requires isolated workers, chunked storage and server-side tiled rendering.

## Security and provenance

- Local trusted-operator use only. Reviewer text is not authenticated identity. No SSO, role-based access, legal signature, trusted timestamp service, encrypted backups or production monitoring is claimed.
- Known personal-field names are dropped from processed data, but this is not a general anonymization engine. Submit only anonymized datasets. Original files are preserved exactly and may contain any information supplied by the uploader.
- Application event/decision history has no update/delete endpoint, but database administrators can modify storage. It is not a tamper-proof legal chain of custody.
- Python spatial libraries parse native data formats. Size/path/XML limits reduce risks, but hostile public uploads require a separate restricted ingestion process with CPU/memory/time/network limits before Internet deployment.
- One API worker is required. The lightweight serialized queue is not crash-resumable inside a file; failed imports must be resubmitted. The demo resumes completed sources by inventory identifier.
- OSM/geoBoundaries-derived exports retain per-source attribution and ODbL obligations. A public website is not permission to copy official restricted planning or land-record content.

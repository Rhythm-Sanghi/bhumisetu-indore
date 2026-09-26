# Advanced SIH 26013 workflows

Bhumi Setu accepts authorized datasets from the agencies named in the problem statement without implying that any connector is a live government integration. Every upload keeps the original file, SHA-256, provider, licence, collection epoch and source CRS.

## Dataset intake profiles

| Profile | Roles | Accepted formats | What the platform does |
|---|---|---|---|
| Municipal GIS | building, road, boundary, utility | GeoPackage, GeoJSON, Shapefile ZIP | Reprojects, maps fields, checks geometry and cross-layer conflicts. |
| Revenue / cadastral | parcel, record, coverage | GeoPackage, GeoJSON, CSV | Keeps identifiers separate from title evidence; checks supplied coverage and parcel topology. |
| GNSS / CORS / ground truth | gnss, ground_truth, survey_point | CSV, GeoPackage, GeoJSON | Uses supplied accuracy to set a review tolerance against the nearest mapped footprint. It never moves source coordinates. |
| Drone / ORI / terrain | orthophoto, DSM, DTM | GeoTIFF | Inspects georeferencing, bands, nodata and resolution; normalizes to UTM 43N. DSM/DTM store elevation statistics and can render a hillshade preview. |
| Utility network | utility | GeoPackage, GeoJSON, Shapefile ZIP, CSV | Identifies a line crossing a mapped footprint interior after a 0.5 m inward buffer. It does not determine depth, easements or network safety. |

## Change and conflict findings

When two compatible vector datasets have distinct declared collection dates, Bhumi Setu creates a **Temporal geometry change detected** finding when a matching feature has more than 2 m boundary displacement. The finding includes source epochs, IoU, area difference and deterministic similarity components. It is evidence for review, not proof of construction, encroachment, survey error or title change.

The platform also adds survey displacement and utility-to-footprint checks when the relevant authorized datasets are supplied. Raster change detection, control-point adjustment, orthophoto feature extraction and ML model inference are intentionally not represented as implemented. Those need approved imagery, training/validation data, survey-control policy and a separate model governance process.

## Operational expansion boundary

The service exposes `GET /api/connector-profiles` so a future institutional client can use the same documented intake profiles. It does not poll public agency systems or claim access to restricted portals. A production deployment still needs agency-approved credentials, RBAC/SSO, isolated asynchronous workers, encrypted storage, retention policy, tile services and signed audit infrastructure.

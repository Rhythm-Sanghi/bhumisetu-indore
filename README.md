# BhumiSetu — Indore land-data harmonization workbench

A working local geospatial application for SIH Problem Statement **26013**, “Automated Integration and Intelligent Harmonization of Multi-source Geospatial Data for Urban Land Record Management.”

React + TypeScript + OpenLayers; FastAPI + GeoPandas/Shapely/Rasterio/PyProj; PostgreSQL/PostGIS; Docker Compose.

**This project contains reference map data, not legally authoritative cadastral evidence.** No private owner records or invented parcel dataset is included. Building footprints are explicitly classified as buildings. Four OSM thematic datasets share one producer; the administrative boundary comes from a separate third-party source. No independent cadastral survey has been verified or bundled.

## Start with Docker

Requires Docker Desktop / Docker Engine with Compose and roughly 3 GB free disk space for images and dependencies. The first build downloads Python spatial wheels, Node dependencies, and container images.

```sh
docker compose up --build -d
```

Open **http://localhost:8080**. API documentation: **http://localhost:8000/docs**.

1. Click **Load Indore reference data**. On an interrupted import, **Load / resume reference pack** resumes missing datasets without importing completed sources again.
2. Wait for processing to finish. Inspect the **Data catalogue**, then select a review finding.
3. Inspect original/current geometry, source identifiers, measurements and score components. Filter the queue by type or status; pagination makes every finding reachable.
4. Enter a reviewer name and a decision note. **Accept** acknowledges the proposed relationship or finding; **Reject** records disagreement. **Edit** can revise feature A's geometry or canonical fields. Drag vertices or use the GeoJSON editor.
5. **Export** downloads a ZIP containing GeoJSON, CSV or GeoPackage plus `validation-report.json`, `audit.json` and attribution notes. Only features linked to accepted/edited findings enter the reviewed data file. Pending/rejected findings remain visible in the report.

Stop services without deleting data:

```sh
docker compose stop
```

The `postgis_data` and `project_files` volumes preserve the database, original uploads, normalized rasters and export bundles. Back up both volumes together. Do not use `docker compose down -v` unless you intend to erase the project.

## Local development on Windows

Python 3.11 and Node 22+ are recommended. Use an isolated environment so unrelated system Python/Node plugins cannot affect the project.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
docker compose up -d db
$env:DATABASE_URL='postgresql+psycopg://landreview:local-pilot-only@127.0.0.1:5433/harmonization'
Set-Location backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. The Vite dev server proxies `/api` to FastAPI. For an offline database fallback, omit `DATABASE_URL`; SQLite stores the same records under `runtime/workbench.db`. SQLite has no PostGIS spatial column or index. Run Alembic against each new database.

Use **one API process / worker**. This bounded pilot uses an in-process, serialized background queue with durable job states, not a distributed worker fleet. Restarted jobs become failed and can be resubmitted. GeoPandas/Shapely perform spatial analysis; PostGIS stores and indexes the projected geometry.

## Verify

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
Set-Location backend
python -m pytest tests -q
Set-Location ../frontend
npm.cmd run build
```

Or use the exact container dependencies:

```sh
docker compose exec api python -m pytest tests -q
docker compose ps
```

Tests cover UTM round trips and metre distances, CRS failure, invalid geometry repair, overlap versus shared edges, explicit coverage gaps, score monotonicity and components, attribute disagreement, nonspatial identifiers, zipped Shapefile, multilayer GeoPackage, KML, CSV, GeoTIFF reprojection, hostile ZIP/XML/JSON input, review concurrency/versioning, provenance preservation, and all export formats. Synthetic test fixtures are kept separate from the genuine demonstration datasets.

## Refresh the reference pack

The repository includes the fetched extract, so demo loading needs no external data service. Network access is required only to refresh data or use the optional OSM basemap.

```sh
python scripts/fetch_data.py
python scripts/prepare_demo.py
python scripts/fetch_history.py
```

These scripts reuse saved raw downloads. To deliberately retrieve a new snapshot, move the old raw files and inventory to an archive first; do not overwrite an audit dataset silently. Rebuild containers after changing bundled data. Existing imported datasets are immutable snapshots; the resume action does not replace them.

The mixed-format derivatives are genuine observations re-encoded into another format/CRS. Their transformations are explicitly recorded in `data/inventory.json`; they are not claimed to be independent surveys.

## Project organization

```text
backend/app/
  ingestion.py       format validation, original preservation, inspections
  transformation.py  coordinate transformations and canonical mapping
  matching.py        deterministic, explainable similarity
  validation.py      topology, discrepancy detection and candidate generation
  review.py          human decisions, edits and optimistic version checks
  database.py        source, feature, decision, job and provenance models
  exporting.py       reviewed data, validation report and audit bundles
  main.py            FastAPI orchestration and bounded job execution
backend/migrations/  Alembic schema and PostGIS generated geometry/index
backend/tests/       spatial, ingestion, review and export tests
frontend/src/        map-led React review interface
data/                licensed reference extracts and machine-readable inventory
docs/                architecture, schema, source research and limitations
scripts/             repeatable acquisition and format preparation
```

See [data sources](docs/DATA_SOURCES.md), [architecture](docs/ARCHITECTURE.md), [canonical schema](docs/CANONICAL_SCHEMA.md), [limitations](docs/LIMITATIONS.md) and [demonstration results](docs/DEMONSTRATION.md).

The [advanced workflow guide](docs/ADVANCED_WORKFLOWS.md) documents intake profiles for authorized municipal, revenue, GNSS/ground-truth, utility and drone/terrain data, plus the implemented temporal vector change check.

## Deployment boundary

This is a **local trusted-operator pilot**, bound to loopback. The reviewer name is a recorded label, not an authenticated identity. No production SSO, signed audit ledger, backup service or fine-grained authorization is fabricated. Before a multi-user operational deployment, add institutional identity, authorization, isolated ingestion workers and an approved storage/retention policy. The bundled password is a local demonstration default; set `POSTGRES_PASSWORD` through `.env` for your installation.

## Licences

Application source: MIT (see `LICENSE`). Geospatial data retain their own licences and attribution; the software licence does not relicense data. OSM themes: © OpenStreetMap contributors, ODbL 1.0. The specific geoBoundaries IND ADM2 release reports **ODbL 1.0** and credits Pathways Data Pvt. Ltd. / lgdirectory.gov.in; do not substitute the general geoBoundaries CC-BY description for this release's metadata.

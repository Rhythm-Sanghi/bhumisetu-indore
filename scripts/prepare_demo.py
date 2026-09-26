"""Create format/CRS derivatives without changing the source observations."""
import csv
import hashlib
import json
from pathlib import Path
import geopandas as gpd

root=Path(__file__).resolve().parents[1]/'data'
inv=json.loads((root/'inventory.json').read_text(encoding='utf-8'))
for source in inv['sources']:
    if source['id'].startswith('osm_'):
        source['download_url']='https://api.openstreetmap.org/api/0.6/map?bbox=75.850,22.710,75.865,22.725'
        source['collection_date']='Unknown survey dates; per-feature edited_at retained'
        source['snapshot_at']=inv['retrieved_at']
    if source['id']=='osm_roads':
        path=root/'osm_roads_3857.gpkg'
        if path.exists(): path.unlink()
        gpd.read_file(root/'osm_roads.geojson').to_crs('EPSG:3857').to_file(path,driver='GPKG',layer='roads')
        source.update(file=path.name,crs='EPSG:3857',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),derivation='Unmodified OSM road observations reprojected from EPSG:4326 to EPSG:3857 and encoded as GeoPackage for mixed-CRS ingestion demonstration. Original WGS84 GeoJSON preserved.')
    if source['id']=='osm_amenities':
        path=root/'osm_amenities.csv'
        features=json.loads((root/'osm_amenities.geojson').read_text(encoding='utf-8'))['features']
        keys=sorted({k for f in features for k in f['properties']})
        with path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=keys+['longitude','latitude']);writer.writeheader()
            for feature in features:
                writer.writerow({**feature['properties'],'longitude':feature['geometry']['coordinates'][0],'latitude':feature['geometry']['coordinates'][1]})
        source.update(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),derivation='OSM point observations serialized as longitude/latitude CSV for tabular ingestion. No coordinate perturbation or independent survey implied.')
inv['download_method']='OSM map API bbox; Overpass endpoints returned 406/429/504 during initial retrieval'
inv['overpass_query_attempted']=inv.pop('overpass_query',None)
inv['source_note']='Four OSM thematic datasets share a producer; geoBoundaries is a separate third-party administrative reference. No independent parcel survey is bundled.'
(root/'inventory.json').write_text(json.dumps(inv,indent=2),encoding='utf-8')
print('Mixed-format reference pack ready: GeoJSON / EPSG:4326, GeoPackage / EPSG:3857, CSV / EPSG:4326')

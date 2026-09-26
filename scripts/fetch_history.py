"""Reconstruct one real earlier OSM building state, with historical node evidence."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import requests
from defusedxml import ElementTree as ET

root=Path(__file__).resolve().parents[1]/'data'
raw=root/'raw'
way_id='702251646'
history=raw/'building-history.xml'
if not history.exists():
    r=requests.get(f'https://api.openstreetmap.org/api/0.6/way/{way_id}/history',timeout=40);r.raise_for_status();history.write_bytes(r.content)
way=ET.parse(history).getroot().find('way')
epoch=way.get('timestamp');refs=[n.get('ref') for n in way.findall('nd')]
coords={};node_evidence=[]
for ref in dict.fromkeys(refs):
    path=raw/f'node-{ref}-history.xml'
    if not path.exists():
        r=requests.get(f'https://api.openstreetmap.org/api/0.6/node/{ref}/history',timeout=40);r.raise_for_status();path.write_bytes(r.content)
    versions=[n for n in ET.parse(path).getroot().findall('node') if n.get('timestamp')<=epoch and n.get('visible')=='true']
    if not versions: raise RuntimeError(f'No historical coordinate at epoch for node {ref}')
    node=max(versions,key=lambda n:n.get('timestamp'))
    coords[ref]=[float(node.get('lon')),float(node.get('lat'))]
    node_evidence.append({'id':ref,'version':node.get('version'),'timestamp':node.get('timestamp'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
props={t.get('k'):t.get('v') for t in way.findall('tag') if t.get('k') in {'building','name','building:levels'}}
props.update(source_id=f'way/{way_id}',edited_at=epoch,osm_version=way.get('version'),historical_epoch=epoch)
path=root/'osm_building_history_2019.geojson'
path.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Polygon','coordinates':[[coords[r] for r in refs]]},'properties':props}]},indent=2),encoding='utf-8')
source={'id':'osm_building_history_2019','name':'Building history · OSM 2019','kind':'building','file':path.name,'provider':'OpenStreetMap contributors · version history','url':f'https://www.openstreetmap.org/way/{way_id}/history','download_url':f'https://api.openstreetmap.org/api/0.6/way/{way_id}/history','license':'ODbL-1.0','license_url':'https://opendatacommons.org/licenses/odbl/1-0/','collection_date':f'OSM version 1 edited {epoch}; actual survey date unknown','retrieved_at':datetime.now(timezone.utc).isoformat(),'crs':'EPSG:4326','feature_count':1,'status':'available','comparison_scope_ids':[f'way/{way_id}'],'limitations':'One genuine historical OSM building state. Node versions reconstructed as of the way edit timestamp. Same producer as current OSM: temporal difference, not independent survey evidence. A later mapper expanded the footprint and changed classification; neither state certifies parcel boundaries.','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'history_evidence':{'way_version':way.get('version'),'way_sha256':hashlib.sha256(history.read_bytes()).hexdigest(),'node_versions':node_evidence}}
inv=json.loads((root/'inventory.json').read_text(encoding='utf-8'))
inv['sources']=[s for s in inv['sources'] if s['id']!=source['id']]+[source]
(root/'inventory.json').write_text(json.dumps(inv,indent=2),encoding='utf-8')
print(json.dumps(source,indent=2))

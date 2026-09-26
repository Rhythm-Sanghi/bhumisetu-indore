"""Download small public reference extracts. No cadastral records or owner data."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1] / 'data'
RAW = ROOT / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
BBOX = [75.850, 22.710, 75.865, 22.725]
now = datetime.now(timezone.utc).isoformat()
query = '[out:json][timeout:90];(way["building"](22.700,75.845,22.735,75.885);way["highway"](22.700,75.845,22.735,75.885);node["amenity"](22.700,75.845,22.735,75.885);way["waterway"](22.700,75.845,22.735,75.885););out meta geom;'
raw_file = RAW / 'osm-overpass.json'
api_file=RAW/'osm-api.xml'
if not api_file.exists() and not raw_file.exists():
    response=requests.get('https://api.openstreetmap.org/api/0.6/map',params={'bbox':','.join(str(x) for x in BBOX)},headers={'User-Agent':'BhumiSetu-Indore-Pilot/1.0'},timeout=120)
    response.raise_for_status()
    api_file.write_bytes(response.content)
if api_file.exists() and not raw_file.exists():
    from defusedxml import ElementTree as ET
    root=ET.parse(api_file).getroot()
    nodes={n.get('id'):n for n in root.findall('node')}
    elements=[]
    for el in list(root.findall('node'))+list(root.findall('way')):
        tags={t.get('k'):t.get('v') for t in el.findall('tag')}
        if not any(k in tags for k in ['building','highway','amenity','waterway']): continue
        if el.tag=='node' and 'amenity' not in tags: continue
        item={'type':el.tag,'id':int(el.get('id')),'timestamp':el.get('timestamp'),'tags':tags}
        if el.tag=='node': item.update(lon=float(el.get('lon')),lat=float(el.get('lat')))
        else:
            refs=[nodes.get(n.get('ref')) for n in el.findall('nd')]
            if any(n is None for n in refs): continue
            item['geometry']=[{'lon':float(n.get('lon')),'lat':float(n.get('lat'))} for n in refs]
        elements.append(item)
    raw_file.write_text(json.dumps({'osm3s':{'timestamp_osm_base':now},'download_method':'OSM map API bbox','elements':elements}),encoding='utf-8')
if not raw_file.exists():
    for endpoint in ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']:
        try:
            response = requests.post(endpoint, data={'data':query}, timeout=120)
            response.raise_for_status()
            payload=response.json()
            if 'remark' in payload:
                raise RuntimeError(payload['remark'])
            raw_file.write_text(json.dumps(payload), encoding='utf-8')
            break
        except Exception as exc:
            print(f'{endpoint}: {exc}', flush=True)
    else:
        raise RuntimeError('Public Overpass endpoints unavailable; retry later')
payload=json.loads(raw_file.read_text(encoding='utf-8'))
groups={k:[] for k in ['buildings','roads','amenities','waterways']}
allow={'name','name:en','building','highway','amenity','waterway','layer','bridge','tunnel','covered','area','ref','height','building:levels'}
for item in payload['elements']:
    tags=item.get('tags',{})
    props={k:v for k,v in tags.items() if k in allow}
    props.update(source_id=f"{item['type']}/{item['id']}", edited_at=item.get('timestamp'))
    if item['type']=='node':
        geom={'type':'Point','coordinates':[item['lon'],item['lat']]}
        key='amenities'
    else:
        coords=[[p['lon'],p['lat']] for p in item.get('geometry',[])]
        if len(coords)<2: continue
        key='buildings' if 'building' in tags else 'roads' if 'highway' in tags else 'waterways'
        if key=='waterways' and 'waterway' not in tags: continue
        if key=='buildings':
            if len(coords)<4 or coords[0]!=coords[-1]: continue
            geom={'type':'Polygon','coordinates':[coords]}
        else: geom={'type':'LineString','coordinates':coords}
    groups[key].append({'type':'Feature','geometry':geom,'properties':props})

sources=[]
for key,features in groups.items():
    path=ROOT/f'osm_{key}.geojson'
    path.write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False),encoding='utf-8')
    sources.append({'id':f'osm_{key}','name':f'OpenStreetMap · {key.title()}','file':path.name,'kind':key[:-1] if key!='amenities' else 'amenity','provider':'OpenStreetMap contributors','url':'https://www.openstreetmap.org/copyright','download_url':'https://overpass-api.de/api/interpreter','license':'ODbL-1.0','license_url':'https://opendatacommons.org/licenses/odbl/1-0/','collection_date':payload.get('osm3s',{}).get('timestamp_osm_base','Unknown'),'retrieved_at':now,'crs':'EPSG:4326','feature_count':len(features),'limitations':'Community mapping; incomplete coverage and variable observation dates. Edit timestamp is not survey date. No ownership or legal parcel authority. Ways only; multipolygon relations are not included. Shared source with other OSM themes.','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'available'})
    print(key,len(features),flush=True)

metadata_path=RAW/'geoboundaries-metadata.json'
if not metadata_path.exists():
    r=requests.get('https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/',timeout=50); r.raise_for_status(); metadata_path.write_text(r.text,encoding='utf-8')
meta=json.loads(metadata_path.read_text(encoding='utf-8'))
boundary_path=ROOT/'indore_district.geojson'
if not boundary_path.exists():
    url=meta['simplifiedGeometryGeoJSON'].replace('github.com/wmgeolab/geoBoundaries/raw/','media.githubusercontent.com/media/wmgeolab/geoBoundaries/')
    r=requests.get(url,timeout=120);r.raise_for_status()
    features=[f for f in r.json()['features'] if f['properties'].get('shapeName','').lower()=='indore']
    if not features: raise RuntimeError('Indore boundary not found')
    boundary_path.write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8')
sources.append({'id':'indore_district','name':'Indore district · geoBoundaries','file':boundary_path.name,'kind':'boundary','provider':meta['boundarySource']+' via geoBoundaries','url':'https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/','download_url':meta['simplifiedGeometryGeoJSON'],'license':meta['boundaryLicense'],'license_url':'https://opendatacommons.org/licenses/odbl/1-0/','collection_date':meta['boundaryYearRepresented'],'retrieved_at':now,'crs':'EPSG:4326','feature_count':1,'limitations':'Simplified district boundary representing 2021. Third-party administrative reference, not municipal wards, parcel limits or a legal boundary determination.','sha256':hashlib.sha256(boundary_path.read_bytes()).hexdigest(),'status':'available'})
gaps=[
('mp_bhulekh','MP Bhulekh · cadastral records','https://mpbhulekh.gov.in/','No open bulk reuse licence verified. Authorized officer-supplied anonymized extracts required; no owner records downloaded.'),
('indore_tcp','Indore Development Plan 2021','https://www.mptownplan.gov.in/plan_Indore.html','Public planning PDFs listed; no licensed vector cadastral download verified. Plan horizon is not a collection date. Not bundled.'),
('indore_gis','Indore GIS · district portal','https://indore.nic.in/en/indore-gis/','Official viewer described, but bulk download and redistribution licence not verified. Not scraped.'),
('bhuvan','ISRO Bhuvan · imagery / land use','https://bhuvan.nrsc.gov.in/terms.php','General terms restrict derivative works, redistribution and bulk extraction without authorization. Product-specific permission required; not bundled.'),
('soi','Survey of India · topographic reference','https://onlinemaps.surveyofindia.gov.in/FAQs.aspx','PDFs and selected administrative products available; vector access depends on registration/product terms. No licensed Indore cadastral feed verified.'),
('data_gov','data.gov.in · Indore search','https://www.data.gov.in/','No openly licensed, downloadable parcel geometry identified in this research. Catalogue search is not proof of absence.')]
for key,name,url,lim in gaps:
    sources.append({'id':key,'name':name,'url':url,'provider':name.split(' · ')[0],'license':'Not verified for redistribution','collection_date':'Unknown','retrieved_at':now,'crs':'Unknown / product-dependent','limitations':lim,'status':'gap'})
(ROOT/'inventory.json').write_text(json.dumps({'pilot':'Indore, Madhya Pradesh','bbox':BBOX,'project_crs':'EPSG:32643','retrieved_at':now,'overpass_query':query,'raw_sha256':hashlib.sha256(raw_file.read_bytes()).hexdigest(),'sources':sources},indent=2),encoding='utf-8')
print('Inventory saved',flush=True)

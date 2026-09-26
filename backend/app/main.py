import hashlib
import io
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,BackgroundTasks,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field
from shapely.geometry import box,mapping
from .database import Base,engine,Session,Dataset,Feature,Issue,Decision,Event,Job,DATA,uid,now,serialize,event
from .ingestion import ingest
from .transformation import canonicalize,SCHEMA
from .validation import analyze
from .review import review_issue
from .exporting import export_bundle

REPO=Path(__file__).resolve().parents[2]
INVENTORY=REPO/'data'/'inventory.json'
processing_lock=threading.Lock()
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with Session() as s:
        for job in s.query(Job).filter(Job.status.in_(['queued','running'])):
            job.status='failed';job.message='Server restarted during processing; resubmit this job';job.updated_at=now()
        s.commit()
    yield

app=FastAPI(title='BhumiSetu · Indore harmonization',version='1.0.0',lifespan=lifespan)
local_origins={f'http://{h}:{p}' for h in ['localhost','127.0.0.1'] for p in ['5173','8000','8080']}
public_origins={origin.strip() for origin in os.getenv('ALLOWED_ORIGINS','').split(',') if origin.strip()}
allowed_origins=local_origins | public_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_credentials=False,
    allow_methods=['GET','POST','PUT','DELETE','OPTIONS'],
    allow_headers=['Content-Type'],
)

CONNECTOR_PROFILES=[
    {'id':'municipal_gis','label':'Municipal GIS','roles':['building','road','boundary','utility'],'formats':['GeoPackage','GeoJSON','Shapefile ZIP'],'required':['licence','collection_date','CRS'],'note':'Import an authorized extract; no municipal endpoint is assumed.'},
    {'id':'revenue_records','label':'Revenue / land records','roles':['parcel','record','coverage'],'formats':['GeoPackage','GeoJSON','CSV'],'required':['licence','collection_date','CRS or identifier mapping'],'note':'Only anonymized, legally accessible records may be imported.'},
    {'id':'survey_control','label':'GNSS / CORS / ground truth','roles':['gnss','ground_truth','survey_point'],'formats':['CSV','GeoPackage','GeoJSON'],'required':['survey epoch','CRS','accuracy where available'],'note':'Coordinates are checked against mapped evidence; this is not a survey adjustment engine.'},
    {'id':'imagery','label':'Drone / ORI / terrain','roles':['orthophoto','dsm','dtm'],'formats':['GeoTIFF'],'required':['licence','capture date','georeferencing'],'note':'Raster georeferencing is preserved and inspected. Extraction and registration remain human-reviewed extensions.'},
    {'id':'utility_network','label':'Utility network','roles':['utility'],'formats':['GeoPackage','GeoJSON','Shapefile ZIP','CSV'],'required':['licence','collection date','CRS'],'note':'Lines can be checked against mapped footprints; protected infrastructure detail must follow agency policy.'},
]

@app.middleware('http')
async def headers(request,call_next):
    # Local trusted-operator application. Prevent cross-origin browser writes.
    origin=request.headers.get('origin')
    if request.method not in {'GET','HEAD','OPTIONS'} and origin and origin not in allowed_origins:
        return Response('Cross-origin writes are disabled',status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    return response

@app.get('/api/health')
def health():
    from sqlalchemy import text
    with engine.connect() as c: c.execute(text('SELECT 1'))
    return {'status':'ok','database':engine.dialect.name,'project_crs':'EPSG:32643'}

@app.get('/api/inventory')
def inventory():
    if not INVENTORY.exists(): raise HTTPException(404,'Run scripts/fetch_data.py to download public reference data')
    return json.loads(INVENTORY.read_text(encoding='utf-8'))

@app.get('/api/connector-profiles')
def connector_profiles():
    return CONNECTOR_PROFILES

@app.get('/api/workspace')
def workspace():
    with Session() as s:
        datasets=[]
        for d in s.query(Dataset).order_by(Dataset.created_at):
            row=serialize(d);row.pop('original_path');row['inspection']={k:v for k,v in row['inspection'].items() if k!='processed_raster'};datasets.append(row)
        issues=[serialize(i) for i in s.query(Issue).order_by(Issue.created_at)]
        return {'datasets':datasets,'issues':issues,'jobs':[serialize(j) for j in s.query(Job).order_by(Job.created_at.desc()).limit(10)],'decisions':[serialize(d) for d in s.query(Decision).order_by(Decision.timestamp.desc())],'project_crs':'EPSG:32643','feature_count':s.query(Feature).count()}

@app.get('/api/datasets/{dataset_id}/features')
def dataset_features(dataset_id:str):
    with Session() as s:
        ds=s.get(Dataset,dataset_id)
        if not ds: raise HTTPException(404,'Dataset not found')
        return {'type':'FeatureCollection','features':[{'type':'Feature','id':f.id,'geometry':f.geometry,'properties':{**f.canonical,'feature_id':f.id,'dataset_id':f.dataset_id,'source_id':f.source_id,'kind':ds.kind}} for f in s.query(Feature).filter_by(dataset_id=dataset_id) if f.geometry]}

@app.get('/api/features/{feature_id}')
def feature_detail(feature_id:str):
    with Session() as s:
        f=s.get(Feature,feature_id)
        if not f: raise HTTPException(404,'Feature not found')
        row=serialize(f);ds=s.get(Dataset,f.dataset_id)
        from shapely import wkt
        g=wkt.loads(f.geom_wkt) if f.geom_wkt else None
        row.update(dataset_name=ds.name,source=ds.source,source_crs=ds.inspection['source_crs'],measured_area_m2=round(g.area,3) if g else None,length_m=round(g.length,3) if g else None)
        from .transformation import reproject,to_wgs
        row['original_wgs84']=to_wgs(reproject(f.original_geometry,ds.inspection['source_crs'])) if f.original_geometry else None
        return row

def run_job(job_id,fn):
    with processing_lock:
        with Session() as s:
            j=s.get(Job,job_id);j.status='running';j.progress=15;j.message='Processing spatial data';j.updated_at=now();s.commit()
        try:
            with Session() as s: result=fn(s)
            with Session() as s:
                j=s.get(Job,job_id);j.status='complete';j.progress=100;j.message='Completed';j.result=result;j.updated_at=now();s.commit()
        except Exception as exc:
            with Session() as s:
                j=s.get(Job,job_id);j.status='failed';j.message=f'{type(exc).__name__}: {str(exc)[:500]}';j.updated_at=now();s.commit()

def enqueue(background,kind,fn):
    with Session() as s:
        job=Job(id=uid(),kind=kind);s.add(job);s.commit();out=serialize(job)
    background.add_task(run_job,out['id'],fn);return out

@app.post('/api/demo')
def load_demo(background:BackgroundTasks):
    inv=inventory()
    def work(s):
        loaded=[]
        existing={d.source.get('inventory_id') for d in s.query(Dataset)}
        for source in inv['sources']:
            if source['status']!='available' or source['id'] in existing: continue
            path=REPO/'data'/source['file']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']: raise ValueError('Bundled dataset checksum mismatch')
            source={**source,'inventory_id':source['id']}
            # Preserve source files; import three original WGS84 themes and admin boundary.
            ds=ingest(s,path,source['name'],source['kind'],source)
            loaded.append(ds.id)
        return {'loaded':loaded,**analyze(s)}
    return enqueue(background,'demo',work)

@app.post('/api/import')
async def upload(background:BackgroundTasks,file:UploadFile=File(...),name:str=Form(...),kind:str=Form(...),source_name:str=Form(...),source_url:str=Form(''),license:str=Form(...),collection_date:str=Form('Unknown'),crs:str=Form(''),layer:str=Form(''),anonymized:bool=Form(False)):
    if not anonymized: raise HTTPException(422,'Confirm the uploaded file contains no private owner information')
    if kind not in {'building','parcel','road','amenity','waterway','boundary','survey_point','record','coverage','raster','utility','ground_truth','gnss','orthophoto','dsm','dtm'}: raise HTTPException(422,'Unsupported dataset role')
    if not name.strip() or not source_name.strip() or not license.strip(): raise HTTPException(422,'Name, source and licence are required')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in {'.geojson','.json','.zip','.gpkg','.kml','.csv','.tif','.tiff'}: raise HTTPException(422,'Use GeoJSON, zipped Shapefile, GeoPackage, KML, CSV or GeoTIFF')
    folder=DATA/'uploads'/uid();folder.mkdir(parents=True)
    path=folder/('original'+suffix);size=0
    with path.open('wb') as out:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>30*1024*1024:
                out.close();path.unlink();raise HTTPException(413,'Maximum upload size is 30 MB')
            out.write(chunk)
    source={'provider':source_name[:200],'url':source_url[:2000],'license':license[:300],'collection_date':collection_date[:100],'retrieved_at':now(),'dataset_role':kind,'limitations':'User-supplied anonymized reference. Licence and accuracy asserted by uploader; not independently verified.','original_filename':Path(file.filename).name}
    return enqueue(background,'import',lambda s:{'dataset_id':ingest(s,path,name[:200],kind,source,crs or None,layer or None).id})

@app.post('/api/analyze')
def analysis(background:BackgroundTasks): return enqueue(background,'analysis',analyze)

class MappingRequest(BaseModel):
    mapping:dict[str,str]
@app.put('/api/datasets/{dataset_id}/mapping')
def map_fields(dataset_id:str,request:MappingRequest):
    with processing_lock,Session() as s:
        ds=s.get(Dataset,dataset_id)
        if not ds: raise HTTPException(404,'Dataset not found')
        if set(request.mapping)-set(SCHEMA) or any(v and v not in ds.inspection['columns'] for v in request.mapping.values()): raise HTTPException(422,'Unknown schema key or source field')
        ds.field_mapping=request.mapping
        ids=set()
        for f in s.query(Feature).filter_by(dataset_id=dataset_id): f.canonical=canonicalize(f.attributes,request.mapping);ids.add(f.id)
        for issue in s.query(Issue).filter_by(status='pending'):
            if ids.intersection(issue.feature_ids): issue.status='superseded';issue.version+=1
        event(s,'field_mapping',dataset_id=dataset_id,mapping=request.mapping);s.commit()
        return {'status':'saved','message':'Schema updated; run analysis to refresh evidence'}

class ReviewRequest(BaseModel):
    action:Literal['accepted','rejected','edited']
    reviewer:str=Field(min_length=2,max_length=100)
    note:str=Field(min_length=3,max_length=2000)
    version:int=Field(ge=1)
    geometry:dict|None=None
    attributes:dict|None=None
@app.post('/api/issues/{issue_id}/review')
def review(issue_id:str,request:ReviewRequest):
    with processing_lock,Session() as s:
        try: return review_issue(s,issue_id,**request.model_dump())
        except LookupError as e: raise HTTPException(404,str(e))
        except RuntimeError as e: raise HTTPException(409,str(e))
        except ValueError as e: raise HTTPException(422,str(e))

@app.get('/api/audit')
def audit():
    with Session() as s: return [serialize(e) for e in s.query(Event).order_by(Event.sequence.desc())]

@app.get('/api/export/{fmt}')
def export(fmt:Literal['geojson','csv','gpkg']):
    with processing_lock,Session() as s:
        try: path=export_bundle(s,fmt)
        except ValueError as e: raise HTTPException(422,str(e))
    return FileResponse(path,filename=f'indore-reviewed-{fmt}.zip',media_type='application/zip')

@app.get('/api/datasets/{dataset_id}/raster-preview')
def raster_preview(dataset_id:str, product:Literal['normalized','hillshade']=Query('normalized')):
    import numpy as np
    import rasterio
    from rasterio.vrt import WarpedVRT
    from PIL import Image
    with Session() as s:
        ds=s.get(Dataset,dataset_id)
        if not ds or ds.kind!='raster': raise HTTPException(404,'Raster not found')
        with rasterio.open(ds.inspection['processed_raster']) as src, WarpedVRT(src,crs='EPSG:4326') as vrt:
            height=max(1,round(768*vrt.height/vrt.width));height=min(768,height)
            width=max(1,round(height*vrt.width/vrt.height))
            arr=vrt.read(1,out_shape=(height,width),masked=True)
            valid=arr.compressed();valid=valid[np.isfinite(valid)]
            lo,hi=np.percentile(valid,[2,98]) if len(valid) else (0,1)
            if product=='hillshade' and ds.inspection.get('raster_role') in {'dsm','dtm'}:
                x,y=np.gradient(arr.filled(float(lo)))
                slope=np.pi/2-np.arctan(np.hypot(x,y));aspect=np.arctan2(-x,y)
                azimuth=np.deg2rad(315);altitude=np.deg2rad(45)
                shade=np.sin(altitude)*np.sin(slope)+np.cos(altitude)*np.cos(slope)*np.cos(azimuth-aspect)
                grey=np.clip(255*(shade+1)/2,0,255).astype('uint8')
            else:
                grey=np.nan_to_num(np.clip((arr.filled(float(lo))-lo)/max(float(hi-lo),1e-9)*255,0,255)).astype('uint8')
            rgba=np.dstack([grey,grey,grey,(~np.ma.getmaskarray(arr)*255).astype('uint8')]);buf=io.BytesIO();Image.fromarray(rgba).save(buf,format='PNG')
    return Response(buf.getvalue(),media_type='image/png')

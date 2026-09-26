import io
import json
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import main
from app.database import Base

@pytest.fixture
def client(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'api.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main,'Session',sessionmaker(bind=engine,expire_on_commit=False))
    monkeypatch.setattr(main,'engine',engine)
    monkeypatch.setattr(main,'DATA',tmp_path)
    with TestClient(main.app) as client: yield client
    engine.dispose()

def metadata(**extra):return {'name':'API test','kind':'parcel','source_name':'Synthetic test fixture','license':'CC0','anonymized':'true',**extra}

def test_api_upload_review_and_failures(client):
    assert client.get('/api/health').status_code==200
    assert client.post('/api/analyze',headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.post('/api/import',data=metadata(anonymized='false'),files={'file':('a.geojson',b'{}')}).status_code==422
    bad=client.post('/api/import',data=metadata(),files={'file':('a.geojson',b'not json')})
    assert bad.status_code==200
    assert client.get('/api/workspace').json()['jobs'][0]['status']=='failed'
    feature={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[75.85,22.71],[75.851,22.71],[75.851,22.711],[75.85,22.711],[75.85,22.71]]]},'properties':{'source_id':'test','recorded_area_m2':1}}
    upload=client.post('/api/import',data=metadata(),files={'file':('a.geojson',json.dumps({'type':'FeatureCollection','features':[feature]}).encode())})
    assert upload.status_code==200
    client.post('/api/analyze')
    ws=client.get('/api/workspace').json();issue=ws['issues'][0];ds=ws['datasets'][0]
    assert client.get(f"/api/datasets/{ds['id']}/features").json()['features']
    payload={'action':'accepted','reviewer':'API reviewer','note':'Synthetic API test decision','version':1}
    assert client.post(f"/api/issues/{issue['id']}/review",json=payload).status_code==200
    assert client.post(f"/api/issues/{issue['id']}/review",json=payload).status_code==409
    assert client.get('/api/export/geojson').status_code==200

def test_raster_preview(client,tmp_path):
    path=tmp_path/'raster.tif'
    with rasterio.open(path,'w',driver='GTiff',height=10,width=10,count=1,dtype='uint8',crs='EPSG:4326',transform=from_origin(75.85,22.72,.0001,.0001),nodata=0) as dst:dst.write(np.arange(100,dtype='uint8').reshape(10,10),1)
    client.post('/api/import',data=metadata(kind='raster'),files={'file':('raster.tif',path.read_bytes())})
    ws=client.get('/api/workspace').json();assert ws['jobs'][0]['status']=='complete',ws['jobs']
    result=client.get(f"/api/datasets/{ws['datasets'][0]['id']}/raster-preview")
    assert result.status_code==200
    assert result.content.startswith(b'\x89PNG')

def test_connector_profiles_and_dsm_hillshade(client,tmp_path):
    profiles=client.get('/api/connector-profiles').json()
    assert {p['id'] for p in profiles}>={'municipal_gis','survey_control','imagery','utility_network'}
    path=tmp_path/'dsm.tif'
    with rasterio.open(path,'w',driver='GTiff',height=10,width=10,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(75.85,22.72,.0001,.0001)) as dst:
        dst.write(np.arange(100,dtype='float32').reshape(10,10),1)
    uploaded=client.post('/api/import',data=metadata(kind='dsm'),files={'file':('dsm.tif',path.read_bytes())})
    assert uploaded.status_code==200
    dataset=client.get('/api/workspace').json()['datasets'][0]
    assert dataset['inspection']['raster_role']=='dsm'
    hillshade=client.get(f"/api/datasets/{dataset['id']}/raster-preview?product=hillshade")
    assert hillshade.status_code==200 and hillshade.content.startswith(b'\x89PNG')

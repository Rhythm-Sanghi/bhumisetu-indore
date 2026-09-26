import csv
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import pytest
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import mapping,box,Point,LineString
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base,Feature,Issue,Dataset,Decision
from app.ingestion import ingest,read_vector
from app.validation import analyze
from app.review import review_issue
from app.exporting import export_bundle,safe_cell

@pytest.fixture
def session(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'test.db'))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s: yield s
    engine.dispose()

def write_geojson(path,features):
    path.write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8');return path
def feature(g,**props): return {'type':'Feature','geometry':mapping(g),'properties':props}
SOURCE={'provider':'Synthetic test fixture only','license':'CC0','url':'','collection_date':'Test','limitations':'Not demo data'}

def test_import_validate_review_export_and_stale_review(session,tmp_path):
    path=write_geojson(tmp_path/'parcels.geojson',[feature(box(75.85,22.71,75.851,22.711),source_id='A',area_m2=1),feature(box(75.8505,22.71,75.8515,22.711),source_id='B')])
    ds=ingest(session,path,'Test parcels','parcel',SOURCE)
    original=session.query(Feature).first().original_geometry
    assert ds.inspection['count']==2 and ds.inspection['source_crs']=='EPSG:4326'
    result=analyze(session);assert result['checks']['overlap']==1
    issue=session.query(Issue).filter_by(kind='overlap').one()
    review_issue(session,issue.id,'accepted','Test reviewer','Measured geometric overlap only',1)
    assert session.query(Decision).count()==1
    with pytest.raises(RuntimeError): review_issue(session,issue.id,'rejected','Test reviewer','Stale attempt',1)
    for fmt in ['geojson','csv','gpkg']:
        bundle=export_bundle(session,fmt)
        with zipfile.ZipFile(bundle) as z:
            report=json.loads(z.read('validation-report.json'))
            assert report['feature_count']==2
            assert report['pending_findings']>=1
            assert len(report['decisions'])==1
            assert 'audit.json' in z.namelist()
            if fmt=='gpkg':
                z.extract('reviewed.gpkg',tmp_path)
                output=gpd.read_file(tmp_path/'reviewed.gpkg')
                assert output.crs.to_epsg()==32643 and len(output)==2
    assert session.query(Feature).first().original_geometry==original
    assert analyze(session)['created']==0

def test_edit_preserves_original_and_reanalysis(session,tmp_path):
    path=write_geojson(tmp_path/'a.geojson',[feature(box(75.85,22.71,75.851,22.711),source_id='A',area_m2=1)])
    ingest(session,path,'A','parcel',SOURCE);analyze(session)
    f=session.query(Feature).one();original=f.original_geometry;issue=session.query(Issue).one()
    review_issue(session,issue.id,'edited','Reviewer','Corrected recorded area from evidence',1,attributes={'recorded_area_m2':1.5})
    assert f.original_geometry==original
    assert analyze(session)['created']>=1

def test_missing_crs_and_multilayer_gpkg(tmp_path):
    path=tmp_path/'multi.gpkg'
    gpd.GeoDataFrame({'name':['one']},geometry=[Point(75.85,22.71)],crs='EPSG:4326').to_file(path,layer='one',driver='GPKG')
    gpd.GeoDataFrame({'name':['two']},geometry=[Point(75.86,22.72)],crs='EPSG:4326').to_file(path,layer='two',driver='GPKG')
    with pytest.raises(ValueError,match='Select a GeoPackage'):read_vector(path)
    rows,crs,meta=read_vector(path,layer='two');assert len(rows)==1 and len(meta['layers'])==2

def test_shapefile_kml_csv_and_raster(session,tmp_path):
    shp=tmp_path/'shape';shp.mkdir()
    gpd.GeoDataFrame({'ref':['S1']},geometry=[Point(75.85,22.71)],crs='EPSG:4326').to_file(shp/'point.shp')
    archive=tmp_path/'shape.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for p in shp.iterdir():z.write(p,p.name)
    assert ingest(session,archive,'Survey','survey_point',SOURCE).inspection['count']==1
    kml=tmp_path/'point.kml';kml.write_text('<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Survey</name><Point><coordinates>75.85,22.71,0</coordinates></Point></Placemark></Document></kml>')
    assert ingest(session,kml,'KML','survey_point',SOURCE).inspection['count']==1
    csv_path=tmp_path/'points.csv';csv_path.write_text('source_id,longitude,latitude\nP1,75.85,22.71\nP2,,\n')
    assert ingest(session,csv_path,'CSV','record',SOURCE).inspection['missing_geometry']==1
    raster=tmp_path/'terrain.tif'
    with rasterio.open(raster,'w',driver='GTiff',height=8,width=8,count=1,dtype='uint8',crs='EPSG:4326',transform=from_origin(75.85,22.72,.0001,.0001)) as dst:dst.write(np.arange(64,dtype='uint8').reshape(8,8),1)
    ds=ingest(session,raster,'Raster','raster',SOURCE)
    with rasterio.open(ds.inspection['processed_raster']) as src:assert src.crs.to_epsg()==32643

def test_dated_change_survey_and_utility_checks(session,tmp_path):
    older={**SOURCE,'collection_date':'2024-01-01'}
    newer={**SOURCE,'collection_date':'2025-01-01'}
    a=write_geojson(tmp_path/'older.geojson',[feature(box(75.8500,22.7100,75.8510,22.7110),source_id='B1')])
    b=write_geojson(tmp_path/'newer.geojson',[feature(box(75.85005,22.7100,75.85105,22.7110),source_id='B1')])
    control=write_geojson(tmp_path/'control.geojson',[feature(Point(75.85125,22.7105),source_id='GT1',accuracy_m=0.5)])
    utility=write_geojson(tmp_path/'utility.geojson',[feature(LineString([(75.8505,22.7097),(75.8505,22.7113)]),source_id='U1',utility='water')])
    ingest(session,a,'Older buildings','building',older)
    ingest(session,b,'Newer buildings','building',newer)
    ingest(session,control,'Ground truth','ground_truth',newer)
    ingest(session,utility,'Utility','utility',newer)
    analyze(session)
    kinds={i.kind for i in session.query(Issue)}
    assert 'change_detected' in kinds
    assert 'survey_displacement' in kinds
    assert 'utility_footprint_conflict' in kinds

def test_dsm_role_has_elevation_statistics(session,tmp_path):
    raster=tmp_path/'dsm.tif'
    with rasterio.open(raster,'w',driver='GTiff',height=4,width=4,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(75.85,22.72,.0001,.0001)) as dst:
        dst.write(np.arange(16,dtype='float32').reshape(4,4),1)
    ds=ingest(session,raster,'DSM','dsm',SOURCE)
    assert ds.kind=='raster'
    assert ds.inspection['raster_role']=='dsm'
    assert ds.inspection['raster_statistics']['elevation_max_m']==15

def test_hostile_archive_xml_json_and_csv(tmp_path):
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as z:z.writestr('../escape.shp','bad')
    with pytest.raises(ValueError,match='Unsafe'):read_vector(bad)
    badxml=tmp_path/'bad.kml';badxml.write_text('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><kml>&xxe;</kml>')
    with pytest.raises(Exception):read_vector(badxml)
    badjson=tmp_path/'bad.geojson';badjson.write_text('{"type":"FeatureCollection","features":[NaN]}')
    with pytest.raises(ValueError):read_vector(badjson)
    assert safe_cell('=SUM(A1:A2)').startswith("'")
    assert safe_cell('Museum')=='Museum'

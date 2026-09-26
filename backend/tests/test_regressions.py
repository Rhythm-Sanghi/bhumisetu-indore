import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point,box,mapping
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base,Issue
from app.ingestion import ingest,read_vector
from app.validation import analyze

def test_geopackage_timestamp_serializes(tmp_path):
    path=tmp_path/'dated.gpkg'
    gpd.GeoDataFrame({'source_id':['1'],'edited_at':[pd.Timestamp('2021-02-28T12:12:11Z')]},geometry=[Point(75.85,22.71)],crs='EPSG:4326').to_file(path,driver='GPKG')
    rows,crs,_=read_vector(path)
    assert '2021-02-28' in rows[0]['properties']['edited_at']

def test_cross_role_classifications_not_false_conflicts(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'state.db'));Base.metadata.create_all(engine)
    source={'provider':'test','license':'CC0'}
    with Session(engine) as session:
        for name,kind,geometry,props in [('b','building',box(75.85,22.71,75.851,22.711),{'building':'yes'}),('p','amenity',Point(75.8505,22.7105),{'amenity':'restaurant'})]:
            path=tmp_path/(name+'.geojson');path.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':props,'geometry':mapping(geometry)}]}))
            ingest(session,path,name,kind,source)
        analyze(session)
        assert session.query(Issue).filter_by(kind='match').count()==1
        assert session.query(Issue).filter_by(kind='attribute_conflict').count()==0

def test_genuine_historical_geometry_changes():
    from pathlib import Path
    from shapely.geometry import shape
    from app.transformation import reproject
    from app.matching import score_match
    root=Path(__file__).resolve().parents[2]/'data'
    assert (root/'osm_building_history_2019.geojson').exists(), 'Bundled real-data regression fixture is required'
    old=json.loads((root/'osm_building_history_2019.geojson').read_text())['features'][0]
    current=next(f for f in json.loads((root/'osm_buildings.geojson').read_text(encoding='utf-8'))['features'] if f['properties']['source_id']=='way/702251646')
    a=reproject(current['geometry'],'EPSG:4326');b=reproject(old['geometry'],'EPSG:4326')
    score=score_match(a,b,{}, {})
    assert score['metrics']['boundary_displacement_m']>2
    assert score['metrics']['area_difference_m2']>50
    assert 25<score['score']<100

import math
import pytest
from shapely.geometry import Polygon,Point,box,mapping
from shapely import make_valid
from app.transformation import reproject,to_wgs,canonicalize,suggest_mapping
from app.matching import score_match
from app.validation import overlap_area,internal_gaps

def test_indore_utm_roundtrip_and_metres():
    original=Point(75.8575,22.7175)
    projected=reproject(mapping(original),'EPSG:4326')
    assert 580000<projected.x<600000
    assert 2500000<projected.y<2530000
    assert Point(to_wgs(projected)['coordinates']).distance(original)<1e-9
    nearby=reproject(mapping(Point(75.8576,22.7175)),'EPSG:4326')
    assert 9<projected.distance(nearby)<12

def test_axis_order_and_invalid_crs():
    with pytest.raises(Exception): reproject(mapping(Point(75,22)),'EPSG:999999')
    with pytest.raises(Exception): reproject(mapping(Point(75,122)),'EPSG:4326')

def test_invalid_geometry_is_detected_and_repair_is_separate():
    bowtie=Polygon([(0,0),(2,2),(0,2),(2,0),(0,0)])
    assert not bowtie.is_valid
    repaired=make_valid(bowtie)
    assert repaired.is_valid and repaired.area==2
    assert not bowtie.is_valid
    assert overlap_area(bowtie,box(0,0,3,3)) is None

def test_topology_touch_overlap_and_explicit_gaps():
    assert overlap_area(box(0,0,10,10),box(10,0,20,10))==0
    assert overlap_area(box(0,0,10,10),box(9,0,20,10))==10
    assert internal_gaps([box(0,0,10,10)]) is None
    assert internal_gaps([box(0,0,10,10)],box(0,0,20,10)).area==100

def test_confidence_monotonic_and_components_explain_score():
    a=box(0,0,10,10)
    exact=score_match(a,a,{},{});shift=score_match(a,box(2,0,12,10),{},{});far=score_match(a,box(100,0,110,10),{},{})
    assert exact['score']==100
    assert exact['score']>shift['score']>far['score']
    assert abs(sum(c['contribution'] for c in shift['components'])-shift['score'])<.2
    assert shift['metrics']['boundary_displacement_m']==2
    assert 'name' in shift['missing_evidence']
    assert 'probability' in shift['score_type']

def test_attribute_disagreement_decreases_score():
    a=box(0,0,10,10)
    agree=score_match(a,a,{'parcel_ref':'12','name':'Museum'},{'parcel_ref':'12','name':'Museum'})
    disagree=score_match(a,a,{'parcel_ref':'12','name':'Museum'},{'parcel_ref':'99','name':'Hospital'})
    assert agree['score']>disagree['score']

def test_point_and_nonspatial_records():
    assert score_match(Point(5,5),box(0,0,10,10),{}, {})['score']==100
    assert score_match(None,Point(0,0),{'record_id':'x'},{'record_id':'x'})['score']==100
    assert score_match(None,Point(0,0),{'record_id':'x'},{'record_id':'z'})['score']==0

def test_schema_mapping_does_not_invent_owner_or_area():
    mapping=suggest_mapping(['KHASRA_NO','area_sqm','NAME'])
    result=canonicalize({'KHASRA_NO':'82','area_sqm':'invalid','NAME':'Survey block'},mapping)
    assert result['parcel_ref']=='82'
    assert result['recorded_area_m2'] is None
    assert 'area_parse_warning' in result
    assert 'owner' not in result

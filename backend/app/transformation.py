import math
from functools import lru_cache
from difflib import SequenceMatcher
from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform

PROJECT_CRS='EPSG:32643'
@lru_cache(maxsize=64)
def get_transformer(source,target):
    return Transformer.from_crs(CRS.from_user_input(source),CRS.from_user_input(target),always_xy=True)
SCHEMA = {
    'record_id':['record_id','source_id','id','osm_id','shapeid'],
    'parcel_ref':['parcel_ref','khasra','khasra_no','survey_no','plot_no'],
    'name':['name','name:en','shapename','label'],
    'land_use':['land_use','landuse','building','amenity','highway','waterway'],
    'recorded_area_m2':['recorded_area_m2','area_m2','area_sqm'],
    'survey_date':['survey_date','observation_date'],
    'observation_accuracy_m':['accuracy_m','horizontal_accuracy','h_accuracy','accuracy'],
    'elevation_m':['elevation_m','elevation','height_m','z'],
    'utility_type':['utility_type','utility','network_type','asset_type'],
    'survey_method':['survey_method','method','fix_type','instrument'],
}
def suggest_mapping(columns):
    lower={str(c).lower():str(c) for c in columns}
    return {target:next((lower[a] for a in aliases if a in lower), '') for target,aliases in SCHEMA.items()}

def canonicalize(attrs, field_mapping):
    out={key:attrs.get(field_mapping.get(key,'')) for key in SCHEMA}
    if out.get('recorded_area_m2') not in (None,''):
        try:
            v=float(out['recorded_area_m2'])
            if not math.isfinite(v) or v<0: raise ValueError()
            out['recorded_area_m2']=v
        except (ValueError,TypeError):
            out['recorded_area_m2']=None
            out['area_parse_warning']='Recorded area is not a non-negative number in square metres'
    if out.get('observation_accuracy_m') not in (None,''):
        try:
            value=float(out['observation_accuracy_m'])
            if not math.isfinite(value) or value < 0: raise ValueError()
            out['observation_accuracy_m']=value
        except (ValueError,TypeError):
            out['observation_accuracy_m']=None
            out['accuracy_parse_warning']='Observation accuracy is not a non-negative value in metres'
    if out.get('elevation_m') not in (None,''):
        try:
            value=float(out['elevation_m'])
            if not math.isfinite(value): raise ValueError()
            out['elevation_m']=value
        except (ValueError,TypeError):
            out['elevation_m']=None
            out['elevation_parse_warning']='Elevation is not a finite value in metres'
    return out

def reproject(geom, source, target=PROJECT_CRS):
    if geom is None: return None
    transformer=get_transformer(str(source),str(target))
    result=transform(lambda x,y,z=None: transformer.transform(x,y,errcheck=True),shape(geom))
    if result.is_empty: return result
    if not all(math.isfinite(v) for v in result.bounds):
        raise ValueError('Coordinate transformation produced non-finite coordinates')
    return result

def to_wgs(geom):
    return mapping(transform(get_transformer(PROJECT_CRS,'EPSG:4326').transform,geom))

def name_similarity(a,b):
    if a in (None,'') or b in (None,''): return None
    return SequenceMatcher(None,str(a).strip().casefold(),str(b).strip().casefold()).ratio()

import csv
import hashlib
import json
import math
import zipfile
from pathlib import Path
import geopandas as gpd
import pyogrio
from defusedxml import ElementTree as ET
from shapely.geometry import mapping, box
from shapely.validation import explain_validity
from .database import Dataset,Feature,event,DATA,uid
from .transformation import suggest_mapping,canonicalize,reproject,to_wgs,PROJECT_CRS

MAX_FEATURES=15000
MAX_UNPACKED=100*1024*1024
PRIVATE_FIELDS={'owner','owner_name','ownername','proprietor','occupant','aadhaar','aadhar','phone','mobile','email','user','uid'}
def clean_props(props):
    return {str(k):v for k,v in props.items() if str(k).lower().replace(' ','_') not in PRIVATE_FIELDS}

def read_kml(path):
    root=ET.parse(path).getroot()
    ns={'k':'http://www.opengis.net/kml/2.2'}
    result=[]
    def coords(el):
        if el is None or not el.text: raise ValueError('KML geometry has no coordinates')
        return [[float(n) for n in p.split(',')[:2]] for p in el.text.split()]
    for mark in root.findall('.//k:Placemark',ns):
        props={'name':mark.findtext('k:name',default='',namespaces=ns)}
        for d in mark.findall('.//k:Data',ns): props[d.get('name','field')]=d.findtext('k:value',namespaces=ns)
        for d in mark.findall('.//k:SimpleData',ns): props[d.get('name','field')]=d.text
        geom=None
        point=mark.find('k:Point',ns); line=mark.find('k:LineString',ns); poly=mark.find('k:Polygon',ns)
        if point is not None: geom={'type':'Point','coordinates':coords(point.find('k:coordinates',ns))[0]}
        elif line is not None: geom={'type':'LineString','coordinates':coords(line.find('k:coordinates',ns))}
        elif poly is not None:
            outer=coords(poly.find('k:outerBoundaryIs/k:LinearRing/k:coordinates',ns))
            holes=[coords(e) for e in poly.findall('k:innerBoundaryIs/k:LinearRing/k:coordinates',ns)]
            geom={'type':'Polygon','coordinates':[outer]+holes}
        elif mark.find('k:MultiGeometry',ns) is not None:
            raise ValueError('KML MultiGeometry is not supported; split placemarks before upload')
        result.append({'geometry':geom,'properties':props})
    return result,'EPSG:4326',{'layers':['Placemarks']}

def read_vector(path, crs_override=None, layer=None):
    suffix=path.suffix.lower()
    meta={}
    if suffix=='.zip':
        folder=path.parent/'unpacked';folder.mkdir(exist_ok=True)
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            if len(infos)>100 or sum(i.file_size for i in infos)>MAX_UNPACKED: raise ValueError('Archive exceeds 100 files / 100 MB expanded limit')
            for i in infos:
                target=(folder/i.filename).resolve()
                if not target.is_relative_to(folder.resolve()) or ':' in i.filename or '\\' in i.filename: raise ValueError('Unsafe archive path')
                if (i.external_attr >> 16)&0o170000==0o120000: raise ValueError('Archive links are not allowed')
                if not i.is_dir() and Path(i.filename).suffix.lower() not in {'.shp','.shx','.dbf','.prj','.cpg','.sbn','.sbx'}: raise ValueError('Shapefile ZIP contains an unsupported member')
            archive.extractall(folder)
        shapes=list(folder.rglob('*.shp'))
        if len(shapes)!=1: raise ValueError('Provide exactly one Shapefile per ZIP')
        path=shapes[0]
        if not path.with_suffix('.dbf').exists() or not path.with_suffix('.shx').exists(): raise ValueError('Shapefile requires .shp, .shx and .dbf')
        suffix='.shp'
    if suffix in {'.geojson','.json'}:
        data=json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
        if data.get('type')!='FeatureCollection' or not isinstance(data.get('features'),list): raise ValueError('Expected a GeoJSON FeatureCollection')
        crs=crs_override or data.get('crs',{}).get('properties',{}).get('name') or 'EPSG:4326'
        rows=data['features'];meta={'layers':['features']}
    elif suffix=='.kml':
        rows,crs,meta=read_kml(path)
        crs=crs_override or crs
    elif suffix=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f); rows=[]
            for i,row in enumerate(reader):
                if i>=MAX_FEATURES: raise ValueError('CSV exceeds feature limit')
                cols={k.lower():k for k in row if k}
                x=next((cols[k] for k in ['longitude','lon','x','easting'] if k in cols),None)
                y=next((cols[k] for k in ['latitude','lat','y','northing'] if k in cols),None)
                geom=None
                if x and y and row[x] and row[y]: geom={'type':'Point','coordinates':[float(row[x]),float(row[y])]}
                if (x or y) and not (x and y): raise ValueError('CSV needs both coordinate columns')
                rows.append({'geometry':geom,'properties':row})
        crs=crs_override or ('EPSG:4326' if x in ['longitude','lon'] else None) if rows else crs_override
        if not crs and any(r['geometry'] for r in rows): raise ValueError('Declare a source CRS for CSV x/y or easting/northing')
        crs=crs or 'EPSG:4326';meta={'layers':['records'],'geometry_note':'Rows without coordinates retained for identifier matching'}
    elif suffix in {'.gpkg','.shp'}:
        layers=pyogrio.list_layers(path).tolist();meta={'layers':[l[0] for l in layers]}
        if len(layers)>1 and not layer: raise ValueError('Select a GeoPackage layer: '+', '.join(meta['layers']))
        if layer and layer not in meta['layers']: raise ValueError('Selected layer not found')
        frame=gpd.read_file(path,layer=layer or layers[0][0],rows=MAX_FEATURES+1)
        crs=crs_override or (frame.crs.to_string() if frame.crs else None)
        if not crs: raise ValueError('Missing CRS. Supply a source EPSG code; it will be recorded as an override')
        rows=json.loads(frame.to_json(default=str))['features']
    else: raise ValueError('Unsupported vector format')
    if len(rows)>MAX_FEATURES: raise ValueError(f'Maximum {MAX_FEATURES} records per upload')
    if not rows: raise ValueError('Dataset has no records')
    return rows,crs,meta

def ingest(session,path,name,kind,source,crs_override=None,layer=None):
    if path.suffix.lower() in {'.tif','.tiff'}: return ingest_raster(session,path,name,kind,source,crs_override)
    rows,crs,meta=read_vector(path,crs_override,layer)
    attrs=[clean_props(r.get('properties') or {}) for r in rows]
    columns=sorted(set(k for row in attrs for k in row))
    mapping_fields=suggest_mapping(columns)
    features=[];types={};invalid=0;missing=0;bounds=[];validity=[]
    dataset_id=uid()
    for index,(row,props) in enumerate(zip(rows,attrs)):
        original=row.get('geometry');geom=reproject(original,crs)
        if geom is not None and not geom.is_empty:
            wgs=to_wgs(geom)
            from shapely.geometry import shape
            w=shape(wgs)
            if not (-180<=w.bounds[0]<=180 and -180<=w.bounds[2]<=180 and -90<=w.bounds[1]<=90 and -90<=w.bounds[3]<=90): raise ValueError('Coordinates fall outside the declared CRS domain')
            types[geom.geom_type]=types.get(geom.geom_type,0)+1;bounds.append(w.bounds)
            if not geom.is_valid:
                invalid+=1
                if len(validity)<20: validity.append({'row':index+1,'reason':explain_validity(geom)})
        else: wgs=None;missing+=1
        can=canonicalize(props,mapping_fields)
        features.append(Feature(id=uid(),dataset_id=dataset_id,source_id=str(can.get('record_id') or index+1),original_geometry=original,geometry=wgs,geom_wkt=geom.wkt if geom is not None and not geom.is_empty else None,attributes=props,canonical=can))
    inspection={**meta,'count':len(rows),'source_crs':crs,'project_crs':PROJECT_CRS,'crs_override':crs_override,'geometry_types':types,'invalid_count':invalid,'missing_geometry':missing,'validity_examples':validity,'columns':columns,'completeness':{c:round(100*sum(r.get(c) not in (None,'') for r in attrs)/len(rows),1) for c in columns},'bbox':[min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)] if bounds else None,'privacy':'Common personal fields excluded from processed records. Submit only anonymized files; original uploads are preserved.'}
    dataset=Dataset(id=dataset_id,name=name,kind=kind,source=source,inspection=inspection,field_mapping=mapping_fields,original_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    session.add(dataset);session.add_all(features);event(session,'import',dataset_id=dataset_id,name=name,sha256=dataset.sha256,count=len(rows),source_crs=crs)
    session.commit();return dataset

def ingest_raster(session,path,name,role,source,crs_override):
    import rasterio
    from rasterio.warp import calculate_default_transform,reproject as warp,Resampling,transform_bounds
    with rasterio.open(path) as src:
        if src.driver!='GTiff': raise ValueError('Only GeoTIFF rasters are accepted')
        crs=crs_override or src.crs
        if not crs: raise ValueError('Raster has no CRS; declare source CRS')
        if src.width*src.height*src.count>30_000_000: raise ValueError('Raster exceeds 30 million band-pixels')
        transform,width,height=calculate_default_transform(crs,PROJECT_CRS,src.width,src.height,*src.bounds)
        if width*height*src.count>30_000_000: raise ValueError('Reprojected raster exceeds pixel limit')
        out=path.parent/'processed.tif';profile=src.profile.copy();profile.update(crs=PROJECT_CRS,transform=transform,width=width,height=height,driver='GTiff')
        with rasterio.open(out,'w',**profile) as dst:
            for band in range(1,src.count+1): warp(source=rasterio.band(src,band),destination=rasterio.band(dst,band),src_crs=crs,src_transform=src.transform,dst_crs=PROJECT_CRS,dst_transform=transform,resampling=Resampling.nearest)
        bbox=transform_bounds(crs,'EPSG:4326',*src.bounds,densify_pts=21)
        role = role if role in {'orthophoto','dsm','dtm'} else 'raster'
        raster_stats={}
        if role in {'dsm','dtm'}:
            data=src.read(1,masked=True).compressed()
            finite=data[__import__('numpy').isfinite(data)]
            if len(finite):
                raster_stats={'elevation_min_m':round(float(finite.min()),3),'elevation_max_m':round(float(finite.max()),3),'elevation_mean_m':round(float(finite.mean()),3)}
        product_note='Hillshade preview is available for DSM/DTM; it is a visual aid, not a survey validation.' if role in {'dsm','dtm'} else 'Preview is a normalized first-band display.'
        inspection={'count':1,'source_crs':str(crs),'project_crs':PROJECT_CRS,'width':src.width,'height':src.height,'bands':src.count,'dtype':src.dtypes,'nodata':str(src.nodata),'resolution':list(src.res),'bbox':list(bbox),'geometry_types':{'Raster footprint':1},'columns':[],'invalid_count':0,'missing_geometry':0,'processed_raster':str(out),'raster_role':role,'raster_statistics':raster_stats,'note':f'Nearest-neighbour reprojection. Raster values are not parcel boundaries. {product_note}'}
    source={**source,'dataset_role':role}
    ds=Dataset(id=uid(),name=name,kind='raster',source=source,inspection=inspection,field_mapping={},original_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    session.add(ds);event(session,'import_raster',dataset_id=ds.id,sha256=ds.sha256,source_crs=str(crs));session.commit();return ds

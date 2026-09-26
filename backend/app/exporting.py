import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import shape
from .database import Feature,Dataset,Issue,Decision,Event,DATA,uid,now,event,serialize

def safe_cell(value):
    s='' if value is None else str(value)
    return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s

def export_bundle(session,fmt):
    issues=session.query(Issue).all()
    reviewed=[i for i in issues if i.status in {'accepted','edited'}]
    ids={fid for i in reviewed for fid in i.feature_ids}
    features=session.query(Feature).filter(Feature.id.in_(ids)).all() if ids else []
    if not features: raise ValueError('Accept or edit a finding before exporting reviewed features')
    datasets={d.id:d for d in session.query(Dataset)}
    folder=DATA/'exports'/uid();folder.mkdir(parents=True)
    output=[]
    for f in features:
        ds=datasets[f.dataset_id]
        decisions=[i for i in reviewed if f.id in i.feature_ids]
        props={**f.canonical,'feature_id':f.id,'source_id':f.source_id,'dataset':ds.name,'source_url':ds.source.get('url'),'license':ds.source.get('license','Unknown'),'source_sha256':ds.sha256,'review_status':','.join(sorted({i.status for i in decisions})),'review_issue_ids':','.join(i.id for i in decisions),'measured_area_m2':None}
        if f.geom_wkt:
            from shapely import wkt
            props['measured_area_m2']=round(wkt.loads(f.geom_wkt).area,3)
        output.append({'type':'Feature','id':f.id,'geometry':f.geometry,'properties':props})
    if fmt=='geojson':
        result=folder/'reviewed.geojson';result.write_text(json.dumps({'type':'FeatureCollection','features':output},ensure_ascii=False,indent=2),encoding='utf-8')
    elif fmt=='csv':
        result=folder/'reviewed.csv'
        columns=list(output[0]['properties'])+['geometry_wkt_epsg4326']
        with result.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
            for f in output: writer.writerow({k:safe_cell(v) for k,v in {**f['properties'],'geometry_wkt_epsg4326':shape(f['geometry']).wkt if f['geometry'] else ''}.items()})
    else:
        result=folder/'reviewed.gpkg'
        spatial=[f for f in output if f['geometry']]
        if not spatial: raise ValueError('No spatial reviewed features available for GeoPackage export; use CSV')
        frame=gpd.GeoDataFrame.from_features(spatial,crs='EPSG:4326').to_crs('EPSG:32643')
        for geom_type in frame.geometry.geom_type.unique():
            frame[frame.geometry.geom_type==geom_type].to_file(result,layer=geom_type.lower(),driver='GPKG')
        nonspatial=[f for f in output if not f['geometry']]
        if nonspatial: (folder/'nonspatial-records.json').write_text(json.dumps(nonspatial,indent=2),encoding='utf-8')
    report={'generated_at':now(),'project':'Indore reference-data harmonization','output_format':fmt,'output_crs':'EPSG:32643' if fmt=='gpkg' else 'EPSG:4326','feature_count':len(output),'reviewed_findings':len(reviewed),'pending_findings':sum(i.status=='pending' for i in issues),'status_counts':{s:sum(i.status==s for i in issues) for s in ['pending','accepted','rejected','edited','superseded']},'scope':'Only features referenced by accepted/edited findings; accepting a relationship or discrepancy does not certify geometry or title. Source originals are retained separately.','sources':[{'name':d.name,'source':d.source,'sha256':d.sha256,'inspection':{k:v for k,v in d.inspection.items() if k!='processed_raster'},'mapping':d.field_mapping} for d in datasets.values() if d.id in {f.dataset_id for f in features}],'findings':[serialize(i) for i in issues],'decisions':[serialize(d) for d in session.query(Decision).order_by(Decision.timestamp)],'limitations':['Not cadastral evidence. No title, owner, survey accuracy or encroachment determination.','Scores are deterministic similarity heuristics, not probabilities.','OpenStreetMap themes are one common source; partial coverage does not imply cadastral gaps.','GeoTIFFs are normalized with nearest-neighbour resampling; no imagery boundary extraction.'],'validation':{'invalid_export_geometries':sum(bool(f['geometry']) and not shape(f['geometry']).is_valid for f in output),'missing_geometry':sum(not f['geometry'] for f in output)},'output_sha256':hashlib.sha256(result.read_bytes()).hexdigest()}
    (folder/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    event(session,'export',format=fmt,feature_count=len(output),output_sha256=report['output_sha256']);session.commit()
    audit=[serialize(e) for e in session.query(Event).order_by(Event.sequence)]
    (folder/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'README.txt').write_text('Indore reviewed reference data\nNOT A CERTIFIED LAND RECORD\n\n© OpenStreetMap contributors where indicated. ODbL 1.0: https://opendatacommons.org/licenses/odbl/1-0/\nRetain per-source attribution and applicable licence obligations when distributing.\nGeoJSON/CSV coordinates: longitude, latitude WGS84. GeoPackage: EPSG:32643 metres.\nReview acceptance acknowledges a finding or relationship; it does not certify geometry.\nValidation report includes unresolved findings and complete decision history.\n',encoding='utf-8')
    archive=folder/'reviewed-bundle.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.iterdir():
            if p!=archive: z.write(p,p.name)
    return archive

"""Deterministic similarity; score is a ranking heuristic, never a probability."""
from .transformation import name_similarity

def score_match(a,b,ca,cb,radius=30.0):
    components=[];metrics={}
    def add(name,value,weight,explanation):
        if value is not None: components.append({'name':name,'value':round(max(0,min(1,value)),5),'weight':weight,'explanation':explanation})
    if a is not None and b is not None:
        distance=a.centroid.distance(b.centroid)
        metrics['centroid_distance_m']=round(distance,3)
        if a.geom_type in {'Polygon','MultiPolygon'} and b.geom_type in {'Polygon','MultiPolygon'}:
            union=a.union(b).area
            iou=a.intersection(b).area/union if union else 0
            area_ratio=min(a.area,b.area)/max(a.area,b.area) if max(a.area,b.area) else 0
            metrics.update(iou=round(iou,5),area_difference_m2=round(abs(a.area-b.area),3),area_difference_pct=round(100*(1-area_ratio),2),boundary_displacement_m=round(a.hausdorff_distance(b),3))
            add('Intersection over union',iou,.55,'Shared area divided by combined area')
            add('Centroid proximity',max(0,1-distance/radius),.20,f'1 − centroid distance / {radius:g} m, clipped at zero')
            add('Area agreement',area_ratio,.15,'Smaller area divided by larger area')
        elif a.geom_type=='Point' or b.geom_type=='Point':
            distance=a.distance(b);metrics['geometry_distance_m']=round(distance,3)
            add('Containment / coincidence',1 if distance==0 else 0,.6,'Point lies in polygon or coincides with reference point')
            add('Spatial proximity',max(0,1-distance/radius),.3,f'1 − geometry distance / {radius:g} m')
        else:
            d=a.hausdorff_distance(b);metrics['boundary_displacement_m']=round(d,3)
            add('Boundary proximity',max(0,1-d/radius),.9,f'1 − Hausdorff distance / {radius:g} m')
    ref_a,ref_b=ca.get('parcel_ref'),cb.get('parcel_ref')
    if ref_a and ref_b: add('Parcel reference',1 if str(ref_a).strip()==str(ref_b).strip() else 0,.25,'Exact normalized reference equality; mismatch is retained as evidence')
    add('Name agreement',name_similarity(ca.get('name'),cb.get('name')),.1,'Case-insensitive string similarity; missing names are omitted')
    if a is None or b is None:
        ra=ca.get('parcel_ref') or ca.get('record_id');rb=cb.get('parcel_ref') or cb.get('record_id')
        add('Record identifier',1 if ra and rb and str(ra)==str(rb) else 0,.9,'Exact identifier match; no spatial evidence for nonspatial record')
    weight=sum(c['weight'] for c in components)
    score=round(100*sum(c['value']*c['weight'] for c in components)/weight,1) if weight else 0
    for c in components: c['contribution']=round(100*c['value']*c['weight']/weight,1) if weight else 0
    return {'score':score,'score_type':'Deterministic similarity, not calibrated probability','components':components,'metrics':metrics,'missing_evidence':[k for k in ['name','parcel_ref'] if not ca.get(k) or not cb.get(k)],'method_version':'spatial-v1'}

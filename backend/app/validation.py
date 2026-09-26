"""Topology checks operate in metres on EPSG:32643 geometries."""
import hashlib
from collections import defaultdict
from shapely import wkt, make_valid
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.validation import explain_validity
from .database import Dataset,Feature,Issue,event
from .transformation import to_wgs
from .matching import score_match

POLYGONS={'Polygon','MultiPolygon'}
POINTS={'Point','MultiPoint'}
def overlap_area(a,b):
    return a.intersection(b).area if a.is_valid and b.is_valid else None
def internal_gaps(geometries,coverage=None):
    union=unary_union(geometries)
    if coverage is not None: return coverage.difference(union)
    return None  # Empty building space is not a cadastral gap.

def source_epoch(dataset):
    """Return a comparable calendar token without claiming unknown epochs are equal."""
    value=str(dataset.source.get('collection_date','')).strip()
    if not value or value.casefold() in {'unknown','test','n/a'}: return None
    return value[:10]

def analyze(session):
    datasets={d.id:d for d in session.query(Dataset).filter(Dataset.status=='ready')}
    features=session.query(Feature).all()
    geoms={f.id:wkt.loads(f.geom_wkt) if f.geom_wkt else None for f in features}
    grouped=defaultdict(list)
    for f in features: grouped[f.dataset_id].append(f)
    fingerprints={i.fingerprint for i in session.query(Issue)}
    created=0;counts=defaultdict(int)
    # Rule v2 does not treat unlike classification vocabularies as a conflict.
    for old in session.query(Issue).filter_by(kind='attribute_conflict',status='pending'):
        if old.evidence.get('method_version')!='spatial-v2' and set(old.evidence.get('conflicts',{}))=={'land_use'}:
            fs=[session.get(Feature,fid) for fid in old.feature_ids]
            if len({datasets[f.dataset_id].kind for f in fs})>1:
                old.status='superseded';old.version+=1
    def issue(kind,title,fs,evidence,severity='warning',proposal=None,extra=''):
        nonlocal created
        ids=[f.id for f in fs]
        import json
        revision='|'.join(sorted((f.geom_wkt or '')+json.dumps(f.canonical,sort_keys=True) for f in fs))
        fp=hashlib.sha256((kind+'|'+ '|'.join(sorted(ids))+'|'+extra+'|'+revision).encode()).hexdigest()
        counts[kind]+=1
        if fp in fingerprints: return
        fingerprints.add(fp)
        session.add(Issue(fingerprint=fp,kind=kind,title=title,feature_ids=ids,evidence=evidence,severity=severity,proposed_geometry=proposal))
        created+=1
    for dsid,items in grouped.items():
        ids=defaultdict(list)
        for f in items:
            g=geoms[f.id];ids[f.source_id].append(f)
            if g is not None and not g.is_valid:
                repaired=make_valid(g)
                proposal=to_wgs(repaired) if not repaired.is_empty else None
                issue('invalid_geometry','Invalid geometry · '+f.source_id,[f],{'reason':explain_validity(g),'method':'GEOS validity; make_valid proposal requires review','score':None},'critical',proposal)
            if f.canonical.get('area_parse_warning'):
                issue('attribute_conflict','Recorded area cannot be parsed',[f],{'reason':f.canonical['area_parse_warning'],'score':None})
            area=f.canonical.get('recorded_area_m2')
            if area is not None and g is not None and g.is_valid and g.geom_type in POLYGONS:
                difference=abs(g.area-area);pct=100*difference/max(area,g.area,1)
                if difference>1 and pct>2:
                    issue('area_difference','Recorded and measured area differ',[f],{'metrics':{'measured_area_m2':round(g.area,2),'recorded_area_m2':area,'area_difference_m2':round(difference,2),'area_difference_pct':round(pct,2)},'reason':'Difference exceeds both 1 m² and 2%; verify recorded units and survey epoch','score':None})
        for ref,duplicates in ids.items():
            if len(duplicates)>1: issue('duplicate_record','Duplicate source identifier · '+ref,duplicates,{'reason':'Identifier repeats within one dataset','score':None})
        polygons=[f for f in items if geoms[f.id] is not None and geoms[f.id].is_valid and geoms[f.id].geom_type in POLYGONS]
        if datasets[dsid].kind in {'building','parcel'} and polygons:
            tree=STRtree([geoms[f.id] for f in polygons])
            for i,a in enumerate(polygons):
                ga=geoms[a.id]
                for j in tree.query(ga,predicate='intersects'):
                    if j<=i: continue
                    b=polygons[j];gb=geoms[b.id];area=overlap_area(ga,gb)
                    if area and area>1:
                        issue('duplicate_geometry' if ga.equals(gb) else 'overlap','Footprints overlap' if datasets[dsid].kind=='building' else 'Parcel polygons overlap',[a,b],{'metrics':{'overlap_area_m2':round(area,2),'smaller_feature_overlap_pct':round(100*area/min(ga.area,gb.area),2)},'reason':'Same-layer polygon intersection exceeds 1 m². Nested buildings/parts may be intentional; inspect source tags.','score':None,'method_version':'topology-v1'})
    buildings=[f for f in features if datasets[f.dataset_id].kind in {'building','parcel'} and geoms[f.id] is not None and geoms[f.id].is_valid and geoms[f.id].geom_type in POLYGONS]
    roads=[f for f in features if datasets[f.dataset_id].kind=='road' and geoms[f.id] is not None and geoms[f.id].is_valid and geoms[f.id].geom_type in {'LineString','MultiLineString'}]
    if buildings:
        tree=STRtree([geoms[f.id] for f in buildings])
        for road in roads:
            tags=road.attributes
            if tags.get('bridge') not in (None,'no') or tags.get('tunnel') not in (None,'no') or tags.get('covered') not in (None,'no') or str(tags.get('layer','0'))!='0': continue
            for j in tree.query(geoms[road.id],predicate='intersects'):
                b=buildings[j];interior=geoms[b.id].buffer(-.5)
                length=geoms[road.id].intersection(interior).length
                if length>2:
                    issue('road_crossing','Road crosses a mapped footprint',[b,road],{'metrics':{'interior_crossing_m':round(length,2),'inward_buffer_m':.5},'reason':'Road centreline crosses the footprint interior by more than 2 m after a 0.5 m inward buffer. Known bridges, tunnels, covered paths and nonzero road layers excluded. Missing vertical tags, passages, or mapping errors remain possible.','score':None,'method_version':'topology-v1'},'critical')
    utilities=[f for f in features if datasets[f.dataset_id].kind=='utility' and geoms[f.id] is not None and geoms[f.id].is_valid and geoms[f.id].geom_type in {'LineString','MultiLineString'}]
    if buildings:
        tree=STRtree([geoms[f.id] for f in buildings])
        for utility in utilities:
            for j in tree.query(geoms[utility.id],predicate='intersects'):
                building=buildings[j]
                inside=geoms[utility.id].intersection(geoms[building.id].buffer(-.5)).length
                if inside>2:
                    utility_type=utility.canonical.get('utility_type') or utility.attributes.get('utility') or 'Utility'
                    issue('utility_footprint_conflict','Utility alignment crosses a mapped footprint',[building,utility],{'metrics':{'interior_crossing_m':round(inside,2),'inward_buffer_m':.5},'reason':f'{utility_type} line crosses the mapped footprint interior. Verify elevation, service entry, mapping epoch and agency design data before acting.','score':None,'method_version':'utility-v1'},'critical')
    controls=[f for f in features if datasets[f.dataset_id].kind in {'survey_point','gnss','ground_truth'} and geoms[f.id] is not None and geoms[f.id].is_valid and geoms[f.id].geom_type in POINTS]
    if controls and buildings:
        tree=STRtree([geoms[f.id] for f in buildings])
        for control in controls:
            point=geoms[control.id]
            candidates=[buildings[j] for j in tree.query(point.buffer(30),predicate='intersects')]
            if not candidates: continue
            target=min(candidates,key=lambda f: point.distance(geoms[f.id]))
            distance=point.distance(geoms[target.id])
            tolerance=max(2.0,float(control.canonical.get('observation_accuracy_m') or 0)*2)
            if distance>tolerance:
                issue('survey_displacement','Survey point differs from mapped footprint',[control,target],{'metrics':{'nearest_feature_distance_m':round(distance,3),'review_tolerance_m':round(tolerance,3),'reported_accuracy_m':control.canonical.get('observation_accuracy_m')},'reason':'Ground-truth/GNSS point is outside the review tolerance of the nearest footprint. Inspect epoch, control quality, feature semantics and source CRS; this does not adjust coordinates automatically.','score':None,'method_version':'survey-v1'},'critical')
    # Candidate matching between compatible layers only; no district-to-building matches.
    comparable=[d for d in datasets.values() if d.kind in {'building','parcel','survey_point','record','amenity'}]
    for n,da in enumerate(comparable):
        for db in comparable[n+1:]:
            if not (da.kind==db.kind or {da.kind,db.kind}<={'building','amenity'} or 'record' in {da.kind,db.kind} or 'survey_point' in {da.kind,db.kind}): continue
            targets=[f for f in grouped[db.id] if geoms[f.id] is not None and geoms[f.id].is_valid]
            tree=STRtree([geoms[f.id] for f in targets]) if targets else None
            for a in grouped[da.id]:
                scope=db.source.get('comparison_scope_ids')
                if scope and a.source_id not in scope: continue
                ga=geoms[a.id]
                if ga is not None and not ga.is_valid: continue
                if ga is None or db.kind=='record':
                    ref=a.canonical.get('parcel_ref') or a.canonical.get('record_id')
                    candidates=[b for b in grouped[db.id] if ref and str(ref)==str(b.canonical.get('parcel_ref') or b.canonical.get('record_id'))]
                else: candidates=[targets[j] for j in tree.query(ga.buffer(30),predicate='intersects')] if tree else []
                scored=[(score_match(ga,geoms[b.id],a.canonical,b.canonical),b) for b in candidates]
                scored.sort(key=lambda p:p[0]['score'],reverse=True)
                if not scored or scored[0][0]['score']<25:
                    if da.kind==db.kind: issue('unmatched','No candidate within matching threshold',[a],{'reason':f'No {db.name} candidate within 30 m scoring at least 25/100','score':None},extra=db.id)
                    continue
                for evidence,b in scored[:3]:
                    if evidence['score']<25: continue
                    evidence['candidate_count']=len(scored)
                    evidence['reason']='Proposed relationship only. Accept records a link; no source geometry is silently replaced.'
                    issue('match','Candidate feature relationship',[a,b],evidence,'info' if evidence['score']>=80 else 'warning')
                    evidence['method_version']='spatial-v2'
                    if da.source.get('comparison_scope_ids') or db.source.get('comparison_scope_ids'):
                        evidence['reason']='Real historical/current source versions differ. This is a temporal mapping change, not proof that either geometry is correct or a real-world building changed.'
                    epoch_a,epoch_b=source_epoch(da),source_epoch(db)
                    if epoch_a and epoch_b and epoch_a!=epoch_b and evidence['metrics'].get('boundary_displacement_m',0)>2:
                        issue('change_detected','Temporal geometry change detected',[a,b],{'metrics':{**evidence['metrics'],'from_epoch':epoch_a,'to_epoch':epoch_b},'score':evidence['score'],'components':evidence['components'],'reason':'Two dated source snapshots have a measurable geometry difference. Review source lineage, mapping date and capture conditions; this is not proof of a physical or legal change.','method_version':'change-v1'},'warning')
                    keys=['parcel_ref','name']+(['land_use'] if da.kind==db.kind else [])
                    conflicts={key:[a.canonical.get(key),b.canonical.get(key)] for key in keys if a.canonical.get(key) and b.canonical.get(key) and str(a.canonical[key]).casefold()!=str(b.canonical[key]).casefold()}
                    if conflicts and evidence['score']>=50: issue('attribute_conflict','Candidate attributes disagree',[a,b],{'conflicts':conflicts,**evidence})
                    if evidence['metrics'].get('boundary_displacement_m',0)>2 and evidence['metrics'].get('iou',0)>.1:
                        issue('boundary_displacement','Candidate boundaries displaced',[a,b],evidence)
                    if evidence['metrics'].get('area_difference_pct',0)>2 and evidence['metrics'].get('iou',0)>.1:
                        issue('area_difference','Candidate footprint areas differ',[a,b],evidence)
    coverage=[f for f in features if datasets[f.dataset_id].kind=='coverage' and geoms[f.id] is not None and geoms[f.id].is_valid]
    parcels=[geoms[f.id] for f in features if datasets[f.dataset_id].kind=='parcel' and geoms[f.id] is not None and geoms[f.id].is_valid]
    for c in coverage:
        if parcels:
            gap=internal_gaps(parcels,geoms[c.id])
            if not gap.is_empty and gap.area>1: issue('gap','Uncovered area within declared parcel coverage',[c],{'metrics':{'gap_area_m2':round(gap.area,2)},'reason':'Declared expected coverage minus valid parcel union. Verify coverage boundary and completeness.','gap_geometry':to_wgs(gap),'score':None})
    event(session,'analysis',created=created,checks=dict(counts),method_version='spatial-v3',gap_check='requires explicit coverage and parcel layers',change_detection='dated vector snapshots only; raster comparison is not inferred')
    session.commit()
    return {'created':created,'checks':dict(counts),'note':'Findings are geometric observations, not legal determinations. Similarity scores are not probabilities. Temporal checks compare dated vector snapshots only.'}

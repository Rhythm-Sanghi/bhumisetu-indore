from sqlalchemy import update
from shapely.geometry import shape
from .database import Issue,Feature,Decision,event,serialize
from .transformation import reproject,to_wgs

def review_issue(session,issue_id,action,reviewer,note,version,geometry=None,attributes=None):
    issue=session.get(Issue,issue_id)
    if not issue: raise LookupError('Finding not found')
    if issue.status!='pending' or issue.version!=version: raise RuntimeError('Finding has already changed. Refresh before reviewing.')
    before={'issue':serialize(issue)}
    after={'status':action,'geometry_changed':False}
    if action=='edited':
        feature=session.get(Feature,issue.feature_ids[0])
        before['feature']={'geometry':feature.geometry,'canonical':feature.canonical}
        if geometry is None and attributes is None: raise ValueError('An edit requires geometry or canonical attributes')
        if geometry is not None:
            geom=reproject(geometry,'EPSG:4326')
            if geom is None or geom.is_empty or not geom.is_valid: raise ValueError('Edited geometry must be nonempty and valid')
            bounds=shape(to_wgs(geom)).bounds
            if not (-180<=bounds[0]<=bounds[2]<=180 and -90<=bounds[1]<=bounds[3]<=90): raise ValueError('Edited geometry is outside WGS84 domain')
            # Prevent inadvertent editing of unrelated geometry class.
            old=shape(feature.geometry) if feature.geometry else None
            if old and old.geom_type in {'Polygon','MultiPolygon'} and geom.geom_type not in {'Polygon','MultiPolygon'}: raise ValueError('Polygon edits must remain Polygon or MultiPolygon')
            feature.geometry=to_wgs(geom);feature.geom_wkt=geom.wkt;after['geometry_changed']=True
        if attributes is not None:
            from .transformation import SCHEMA,canonicalize
            if set(attributes)-set(SCHEMA): raise ValueError('Unknown canonical fields')
            feature.canonical=canonicalize({**feature.canonical,**attributes},{key:key for key in SCHEMA})
        after['feature']={'geometry':feature.geometry,'canonical':feature.canonical}
        # Findings involving changed evidence are superseded, not silently kept actionable.
        for related in session.query(Issue).filter(Issue.status=='pending',Issue.id!=issue.id):
            if feature.id in related.feature_ids:
                related.status='superseded';related.version+=1
        after['note']='Related pending findings superseded. Re-analysis can create fresh findings after evidence changes.'
    result=session.execute(update(Issue).where(Issue.id==issue_id,Issue.status=='pending',Issue.version==version).values(status=action,version=version+1))
    if result.rowcount!=1: raise RuntimeError('Concurrent review detected; refresh')
    decision=Decision(issue_id=issue_id,action=action,reviewer=reviewer,note=note,before=before,after=after)
    session.add(decision);event(session,'review',issue_id=issue_id,action_taken=action,reviewer=reviewer,note=note,version=version+1)
    session.commit();return serialize(decision)

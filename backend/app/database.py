import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, Column, String, Integer, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('DATA_DIR', ROOT / 'runtime')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('DATABASE_URL', 'sqlite:///' + (DATA/'workbench.db').as_posix())
engine = create_engine(URL, connect_args={'check_same_thread':False} if URL.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()
def uid(): return uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()

class Dataset(Base):
    __tablename__='datasets'
    id=Column(String,primary_key=True,default=uid)
    name=Column(String,nullable=False)
    kind=Column(String,nullable=False)
    status=Column(String,default='ready')
    created_at=Column(String,default=now)
    source=Column(JSON,nullable=False)
    inspection=Column(JSON,nullable=False)
    field_mapping=Column(JSON,default=dict)
    original_path=Column(Text,nullable=False)
    sha256=Column(String,nullable=False)

class Feature(Base):
    __tablename__='features'
    id=Column(String,primary_key=True,default=uid)
    dataset_id=Column(String,index=True,nullable=False)
    source_id=Column(String,index=True)
    original_geometry=Column(JSON,nullable=True)
    geometry=Column(JSON,nullable=True)
    geom_wkt=Column(Text,nullable=True)
    attributes=Column(JSON,nullable=False)
    canonical=Column(JSON,nullable=False)

class Issue(Base):
    __tablename__='issues'
    id=Column(String,primary_key=True,default=uid)
    fingerprint=Column(String,unique=True,nullable=False)
    kind=Column(String,nullable=False)
    severity=Column(String,nullable=False)
    title=Column(String,nullable=False)
    feature_ids=Column(JSON,nullable=False)
    evidence=Column(JSON,nullable=False)
    proposed_geometry=Column(JSON,nullable=True)
    status=Column(String,default='pending')
    version=Column(Integer,default=1)
    created_at=Column(String,default=now)

class Decision(Base):
    __tablename__='decisions'
    id=Column(String,primary_key=True,default=uid)
    issue_id=Column(String,index=True,nullable=False)
    action=Column(String,nullable=False)
    reviewer=Column(String,nullable=False)
    note=Column(Text,nullable=False)
    timestamp=Column(String,default=now)
    before=Column(JSON,nullable=False)
    after=Column(JSON,nullable=False)

class Event(Base):
    __tablename__='events'
    sequence=Column(Integer,primary_key=True,autoincrement=True)
    timestamp=Column(String,default=now)
    action=Column(String,nullable=False)
    detail=Column(JSON,nullable=False)

class Job(Base):
    __tablename__='jobs'
    id=Column(String,primary_key=True,default=uid)
    kind=Column(String,nullable=False)
    status=Column(String,default='queued')
    progress=Column(Integer,default=0)
    message=Column(Text,default='Waiting to process')
    result=Column(JSON,nullable=True)
    created_at=Column(String,default=now)
    updated_at=Column(String,default=now)

def event(session, action, **detail):
    session.add(Event(action=action, detail=detail))

def serialize(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns}

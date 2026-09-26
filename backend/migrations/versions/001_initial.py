"""Initial canonical schema and PostGIS spatial index.

Revision ID: 001
"""
from alembic import op
from app.database import Base
revision='001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name=='postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
        op.execute('ALTER TABLE features ADD COLUMN geom_utm geometry(Geometry,32643) GENERATED ALWAYS AS (ST_GeomFromText(geom_wkt,32643)) STORED')
        op.execute('CREATE INDEX ix_features_geom_utm ON features USING GIST (geom_utm)')
        op.execute('ALTER TABLE features ADD CONSTRAINT fk_feature_dataset FOREIGN KEY (dataset_id) REFERENCES datasets(id)')
        op.execute('ALTER TABLE decisions ADD CONSTRAINT fk_decision_issue FOREIGN KEY (issue_id) REFERENCES issues(id)')
def downgrade():
    Base.metadata.drop_all(op.get_bind())

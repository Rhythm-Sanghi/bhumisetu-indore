export type Geometry = {
  type: string;
  coordinates?: unknown;
  geometries?: Geometry[];
};
export type Source = {
  name?: string;
  provider: string;
  url: string;
  license: string;
  collection_date: string;
  retrieved_at: string;
  limitations: string;
  status?: string;
  id?: string;
  crs?: string;
  feature_count?: number;
  dataset_role?: string;
};
export type Dataset = {
  id: string;
  name: string;
  kind: string;
  source: Source;
  sha256: string;
  field_mapping: Record<string, string>;
  inspection: {
    count: number;
    source_crs: string;
    project_crs: string;
    geometry_types: Record<string, number>;
    columns: string[];
    invalid_count: number;
    missing_geometry: number;
    completeness?: Record<string, number>;
    bbox: number[] | null;
    bands?: number;
    width?: number;
    height?: number;
    note?: string;
    raster_role?: string;
    raster_statistics?: Record<string, number>;
  };
};
export type Issue = {
  id: string;
  kind: string;
  severity: string;
  title: string;
  feature_ids: string[];
  status: string;
  version: number;
  proposed_geometry: Geometry | null;
  evidence: {
    score: number | null;
    score_type?: string;
    reason?: string;
    components?: {
      name: string;
      value: number;
      weight: number;
      explanation: string;
      contribution: number;
    }[];
    metrics?: Record<string, number | string | null>;
    conflicts?: Record<string, unknown>;
    missing_evidence?: string[];
    candidate_count?: number;
    gap_geometry?: Geometry;
  };
};
export type EvidenceFeature = {
  id: string;
  dataset_id: string;
  source_id: string;
  geometry: Geometry | null;
  original_wgs84: Geometry | null;
  canonical: Record<string, unknown>;
  attributes: Record<string, unknown>;
  dataset_name: string;
  source: Source;
  source_crs: string;
  measured_area_m2: number;
  length_m: number;
};
export type Workspace = {
  datasets: Dataset[];
  issues: Issue[];
  feature_count: number;
  jobs: {
    id: string;
    kind: string;
    status: string;
    progress: number;
    message: string;
  }[];
  decisions: {
    id: string;
    issue_id: string;
    action: string;
    reviewer: string;
    note: string;
    timestamp: string;
  }[];
};
export type Collection = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    id: string;
    geometry: Geometry;
    properties: Record<string, unknown>;
  }[];
};

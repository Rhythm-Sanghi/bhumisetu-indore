import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  FileUp,
  GitCompareArrows,
  Info,
  Layers,
  Map as MapIcon,
  PanelLeftClose,
  Play,
  Plus,
  Search,
  TriangleAlert,
  X,
  ExternalLink,
  Pencil,
  BookOpen,
  LoaderCircle,
} from "lucide-react";
import { api, json } from "./api";
import { MapWorkspace } from "./MapWorkspace";
import { Modal, PanelHeading, StatusLabel } from "./ui";
import type {
  Collection,
  Dataset,
  EvidenceFeature,
  Geometry,
  Issue,
  Source,
  Workspace,
} from "./types";
const blank: Workspace = {
  datasets: [],
  issues: [],
  feature_count: 0,
  jobs: [],
  decisions: [],
};
const fmt = (v: number) =>
  v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
const fieldLabels: Record<string, string> = {
  record_id: "Record ID",
  parcel_ref: "Parcel reference",
  recorded_area_m2: "Recorded area (m²)",
  survey_date: "Survey date",
  land_use: "Land use",
  iou: "Intersection over union",
};
const label = (s: string) =>
  fieldLabels[s] ||
  s.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
const safeUrl = (url: string) => (/^https?:\/\//i.test(url) ? url : undefined);
export default function App() {
  const [ws, setWs] = useState<Workspace>(blank),
    [collections, setCollections] = useState<Record<string, Collection>>({}),
    [visible, setVisible] = useState<Record<string, boolean>>({}),
    [selectedId, setSelectedId] = useState<string | null>(null),
    [features, setFeatures] = useState<EvidenceFeature[]>([]),
    [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [modal, setModal] = useState<
      "import" | "sources" | "export" | "audit" | "layers" | null
    >(null),
    [inventory, setInventory] = useState<Source[]>([]),
    [audit, setAudit] = useState<Record<string, unknown>[]>([]),
    [query, setQuery] = useState(""),
    [status, setStatus] = useState("pending"),
    [kindFilter, setKindFilter] = useState("all"),
    [comparison, setComparison] = useState("both"),
    [reviewer, setReviewer] = useState("Pilot reviewer"),
    [note, setNote] = useState(""),
    [editMode, setEditMode] = useState(false),
    [geometry, setGeometry] = useState<Geometry | null>(null),
    [geometryText, setGeometryText] = useState(""),
    [attributeText, setAttributeText] = useState(""),
    [busy, setBusy] = useState(false),
    [fitToken, setFitToken] = useState(0),
    [detailSection, setDetailSection] = useState("sources"),
    [page, setPage] = useState(0),
    [view, setView] = useState("workspace"),
    [queueOpen, setQueueOpen] = useState(true);
  const issue = ws.issues.find((i) => i.id === selectedId) || null;
  const active = ws.jobs.find(
    (j) => j.status === "running" || j.status === "queued",
  );
  const previousActive = useRef(false);
  const known = useRef(new Set<string>());
  const selectionVersion = useRef(0);
  const refresh = async () => {
    const data = await api<Workspace>("/workspace");
    setWs(data);
    return data;
  };
  const refreshLayers = async (data: Workspace) => {
    const pairs = await Promise.all(
      data.datasets
        .filter((d) => d.kind !== "raster")
        .map(
          async (d) =>
            [
              d.id,
              await api<Collection>(`/datasets/${d.id}/features`),
            ] as const,
        ),
    );
    setCollections(Object.fromEntries(pairs));
    known.current = new Set(data.datasets.map((d) => d.id));
  };
  useEffect(() => {
    let mounted = true;
    api<Workspace>("/workspace")
      .then(async (data) => {
        if (!mounted) return;
        setWs(data);
        await refreshLayers(data);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);
  useEffect(() => {
    const id = setInterval(() => {
      refresh().catch((e) => setError(e.message));
    }, 2500);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    if (ws.datasets.some((d) => !known.current.has(d.id)))
      refreshLayers(ws).catch((e) => setError(e.message));
    if (previousActive.current && !active) {
      refreshLayers(ws).catch((e) => setError(e.message));
      const failed = ws.jobs.find((j) => j.status === "failed");
      if (failed && ws.jobs[0]?.id === failed.id) setError(failed.message);
      else if (ws.jobs[0]?.kind === "demo")
        setNotice("Reference data loaded. Run analysis when you are ready to generate findings.");
      else setNotice("Processing complete. Results are ready for review.");
    }
    previousActive.current = !!active;
  }, [ws]);
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const selectIssue = async (i: Issue) => {
    const version = ++selectionVersion.current;
    setSelectedId(i.id);
    setDetailSection("sources");
    setSelectedDataset(null);
    setEditMode(false);
    setGeometry(null);
    setNote("");
    setFeatures([]);
    try {
      const f = await Promise.all(
        i.feature_ids.map((id) => api<EvidenceFeature>(`/features/${id}`)),
      );
      if (version !== selectionVersion.current) return;
      setFeatures(f);
      setGeometryText(
        JSON.stringify(i.proposed_geometry || f[0]?.geometry, null, 2),
      );
      setAttributeText(JSON.stringify(f[0]?.canonical || {}, null, 2));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const selectFeature = async (id: string) => {
    const finding =
      ws.issues.find(
        (i) => i.feature_ids.includes(id) && i.status === "pending",
      ) || ws.issues.find((i) => i.feature_ids.includes(id));
    if (finding) {
      await selectIssue(finding);
      return;
    }
    ++selectionVersion.current;
    setSelectedId(null);
    setDetailSection("sources");
    setSelectedDataset(null);
    setEditMode(false);
    try {
      setFeatures([await api<EvidenceFeature>(`/features/${id}`)]);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const decide = async (action: "accepted" | "rejected" | "edited") => {
    if (!issue) return;
    await run(async () => {
      if (!note.trim())
        throw new Error("Add a review note explaining your decision.");
      let g: Geometry | null = null;
      let attrs: Record<string, unknown> | null = null;
      if (action === "edited") {
        g = geometry || JSON.parse(geometryText);
        attrs = JSON.parse(attributeText);
      }
      await api(
        `/issues/${issue.id}/review`,
        json({
          action,
          reviewer,
          note,
          version: issue.version,
          geometry: g,
          attributes: attrs,
        }),
      );
      setNotice(
        `Decision saved · ${label(action)}. Original data and evidence retained.`,
      );
      setEditMode(false);
      const data = await refresh();
      await refreshLayers(data);
      const updated = data.issues.find((i) => i.id === issue.id);
      if (updated) await selectIssue(updated);
    });
  };
  const showSources = async () => {
    await run(async () => {
      const d = await api<{ sources: Source[] }>("/inventory");
      setInventory(d.sources);
      setModal("sources");
    });
  };
  const showAudit = async () => {
    await run(async () => {
      setAudit(await api<Record<string, unknown>[]>("/audit"));
      setModal("audit");
    });
  };
  const pending = ws.issues.filter((i) => i.status === "pending");
  const reviewed = ws.issues.filter((i) =>
    ["accepted", "edited", "rejected"].includes(i.status),
  );
  const featureLabels = useMemo(
    () =>
      Object.fromEntries(
        Object.values(collections).flatMap((c) =>
          c.features.map((f) => [
            f.id,
            String(f.properties.name || f.properties.source_id || f.id),
          ]),
        ),
      ),
    [collections],
  );
  const filtered = ws.issues.filter(
    (i) =>
      (status === "all" || i.status === status) &&
      (kindFilter === "all" || i.kind === kindFilter) &&
      `${i.title} ${i.kind} ${i.id} ${featureLabels[i.feature_ids[0]] || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  useEffect(() => setPage(0), [status, kindFilter, query]);
  const chooseDataset = (d: Dataset) => {
    setSelectedDataset(d);
    setModal(null);
    setSelectedId(null);
    setFeatures([]);
    setEditMode(false);
  };
  return (
    <div
      className={`app case-layout ${view === "workspace" ? "review-view" : "catalogue-view"}`}
    >
      <header className="topbar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("workspace");
          }}
        >
          Bhumi Setu
        </a>
        <nav aria-label="Main navigation">
          <button
            className={view === "workspace" ? "nav active" : "nav"}
            aria-current={view === "workspace" ? "page" : undefined}
            onClick={() => setView("workspace")}
          >
            Review workspace
          </button>
          <button
            className={view === "datasets" ? "nav active" : "nav"}
            aria-current={view === "datasets" ? "page" : undefined}
            onClick={() => setView("datasets")}
          >
            Data catalogue
          </button>
          <button className="nav" onClick={showAudit}>
            Audit trail
          </button>
        </nav>
        <div className="project-context">
          <span>Indore pilot</span>
          <span>Local workspace</span>
        </div>
        <div className="project-actions">
          <button className="btn" onClick={() => setModal("import")}>
            <FileUp size={16} />
            Import data
          </button>
          <button
            className="btn primary"
            disabled={!!active || busy || !ws.datasets.length}
            onClick={() =>
              run(async () => {
                await api("/analyze", json({}));
                setNotice(
                  "Analysis queued. Source geometries remain unchanged.",
                );
              })
            }
          >
            {active ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Play size={15} />
            )}
            Run analysis
          </button>
          <button className="btn" onClick={() => setModal("export")}>
            <ArrowDownToLine size={16} />
            Export
          </button>
        </div>
      </header>
      <div className="authority-strip">
        <Info size={15} />
        <strong>Reference data only</strong>
        <span>
          Public map features support review. They do not establish ownership or
          legal parcel boundaries.
        </span>
        <button onClick={showSources}>
          Sources & limitations <ArrowRight size={14} />
        </button>
      </div>
      {error && (
        <div role="alert" className="alert error">
          <TriangleAlert size={17} />
          {error}
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="alert success">
          <CheckCircle2 size={16} />
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {active && (
        <div className="processing" role="status">
          <LoaderCircle className="spin" size={14} />
          {label(active.kind)} · {active.message}
          <progress value={active.progress} max="100" />
          <span>{active.progress}%</span>
        </div>
      )}
      {view === "datasets" ? (
        <main className="catalogue">
          <div className="section-title">
            <div>
              <h2>
                Datasets & provenance{" "}
                <span className="section-count">
                  {ws.datasets.length} datasets
                </span>
              </h2>
              <p>
                Inspect source metadata, coordinate systems and field mappings.
              </p>
            </div>
            <button className="btn" onClick={showSources}>
              <BookOpen size={16} />
              Data-source inventory
            </button>
          </div>
          {!ws.datasets.length ? (
            <Empty
              icon={<Database />}
              title="No datasets imported"
              text="Load the public Indore reference pack or import anonymized files."
              action={
                <button
                  className="btn primary"
                  disabled={!!active}
                  onClick={() => run(() => api("/demo", json({})))}
                >
                  Load Indore reference data
                </button>
              }
            />
          ) : (
            <div className="catalogue-table">
              <table>
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Role</th>
                    <th>Records</th>
                    <th>Source CRS</th>
                    <th>Normalized CRS</th>
                    <th>Geometry validity</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {ws.datasets.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <strong>{d.name}</strong>
                        <small>{d.source.provider}</small>
                      </td>
                      <td>{label(d.kind)}</td>
                      <td>{fmt(d.inspection.count)}</td>
                      <td>{d.inspection.source_crs}</td>
                      <td>{d.inspection.project_crs}</td>
                      <td>
                        {d.inspection.invalid_count
                          ? `${d.inspection.invalid_count} need review`
                          : "No invalid geometries"}
                      </td>
                      <td>
                        <button
                          className="text-btn"
                          onClick={() => {
                            chooseDataset(d);
                            setView("workspace");
                          }}
                        >
                          Inspect <ArrowRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      ) : (
        <main className={`workbench ${!queueOpen ? "queue-hidden" : ""}`}>
          <section className={`review-queue ${!queueOpen ? "collapsed" : ""}`}>
            <div className="queue-header">
              <button
                className="queue-toggle"
                onClick={() => setQueueOpen(!queueOpen)}
                aria-expanded={queueOpen}
                aria-label={
                  queueOpen ? "Collapse review queue" : "Expand review queue"
                }
              >
                <h1>Review queue</h1>
                <span className="queue-count">{pending.length} pending</span>
                <ChevronDown size={14} />
              </button>
              <span className="queue-summary">
                {reviewed.length} reviewed · {ws.issues.length} findings
              </span>
            </div>
            {queueOpen && (
              <>
                <div className="queue-filters">
                  <div className="search-field">
                    <Search size={14} />
                    <input
                      aria-label="Search findings"
                      placeholder="Search findings…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <select
                    aria-label="Finding status"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    {[
                      "pending",
                      "accepted",
                      "rejected",
                      "edited",
                      "superseded",
                      "all",
                    ].map((s) => (
                      <option key={s} value={s}>
                        {s === "pending" ? "Needs review" : label(s)}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Finding type"
                    value={kindFilter}
                    onChange={(e) => setKindFilter(e.target.value)}
                  >
                    <option value="all">All checks</option>
                    {[...new Set(ws.issues.map((i) => i.kind))]
                      .sort()
                      .map((k) => (
                        <option key={k} value={k}>
                          {label(k)}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="queue-table">
                  <ol className="case-list" aria-label="Review findings">
                    {filtered.slice(page * 50, (page + 1) * 50).map((i) => (
                      <li key={i.id}>
                        <button
                          className={`case-item ${i.id === selectedId ? "active" : ""}`}
                          aria-pressed={i.id === selectedId}
                          onClick={() => selectIssue(i)}
                        >
                          <span className="case-identity">
                            <strong>
                              {featureLabels[i.feature_ids[0]] || i.title}
                            </strong>
                            <span>{i.id.slice(0, 8).toUpperCase()}</span>
                          </span>
                          <span className="case-description">{i.title}</span>
                          <span className="case-meta">
                            <StatusLabel status={i.status}>
                              {i.status === "pending"
                                ? "Needs review"
                                : label(i.status)}
                            </StatusLabel>
                            <span>
                              {i.evidence.score != null
                                ? `${i.evidence.score.toFixed(0)}/100 similarity`
                                : "Rule check"}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ol>
                  {!filtered.length && (
                    <div className="queue-empty">
                      <CheckCircle2 size={20} />
                      <span>
                        {ws.issues.length
                          ? "No findings match these filters."
                          : ws.datasets.length
                            ? "Run analysis to populate the queue."
                            : "Import reference data to begin validation."}
                      </span>
                    </div>
                  )}
                  {filtered.length > 50 && (
                    <div className="table-pagination">
                      <button
                        disabled={page === 0}
                        onClick={() => setPage(page - 1)}
                      >
                        Previous
                      </button>
                      <span>
                        {page * 50 + 1}–
                        {Math.min((page + 1) * 50, filtered.length)} of{" "}
                        {filtered.length}
                      </span>
                      <button
                        disabled={(page + 1) * 50 >= filtered.length}
                        onClick={() => setPage(page + 1)}
                      >
                        Next
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
          <section className="center-panel">
            <div className="map-toolbar">
              <div className="map-toolbar-title">
                <strong>
                  {issue
                    ? issue.title
                    : selectedDataset
                      ? selectedDataset.name
                      : "Indore reference map"}
                </strong>
                <span>
                  {features[0]?.source_id || "Rajwada · Central Indore"}
                </span>
              </div>
              <button
                className="btn map-layer-button"
                onClick={() => setModal("layers")}
              >
                <Layers size={15} />
                Layers <span>{ws.datasets.length}</span>
              </button>
              <div className="segmented" aria-label="Geometry comparison">
                {[
                  ["both", "Compare"],
                  [
                    "original",
                    features.length > 1 && !issue?.proposed_geometry
                      ? "Source A"
                      : "Original",
                  ],
                  [
                    "proposed",
                    features.length > 1 && !issue?.proposed_geometry
                      ? "Source B"
                      : "Proposed",
                  ],
                ].map(([key, text]) => (
                  <button
                    key={key}
                    aria-pressed={comparison === key}
                    className={comparison === key ? "selected" : ""}
                    onClick={() => setComparison(key)}
                  >
                    {key === "both" && <GitCompareArrows size={13} />} {text}
                  </button>
                ))}
              </div>
            </div>
            <div className="map-content">
              <MapWorkspace
                datasets={ws.datasets}
                collections={collections}
                visible={visible}
                selected={features}
                issue={issue}
                onFeature={selectFeature}
                comparison={comparison}
                editMode={editMode}
                onEdit={(g) => {
                  setGeometry(g);
                  setGeometryText(JSON.stringify(g, null, 2));
                }}
                fitToken={fitToken}
              />
              {loading && (
                <div className="map-empty">
                  <LoaderCircle className="spin" />
                  <h2>Opening the review workspace</h2>
                  <p>Reading project layers and review history…</p>
                </div>
              )}
              {!loading && !ws.datasets.length && (
                <div className="map-empty">
                  <div className="empty-icon">
                    <MapIcon size={32} />
                  </div>
                  <h2>No reference layers loaded</h2>
                  <p>
                    Load genuine public building, road, amenity and district
                    reference datasets. Their source records stay intact.
                  </p>
                  <button
                    className="btn primary"
                    disabled={!!active || busy}
                    onClick={() => run(() => api("/demo", json({})))}
                  >
                    <Database size={16} />
                    {active
                      ? "Loading reference data…"
                      : "Load Indore reference data"}
                  </button>
                  <button
                    className="text-btn"
                    onClick={() => setModal("import")}
                  >
                    Or import your datasets <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>
          </section>
          <aside className="evidence-panel">
            <PanelHeading
              title={
                selectedDataset ? "Dataset inspection" : "Evidence & review"
              }
            >
              {(selectedDataset || features.length > 0) && (
                <button
                  className="icon-btn"
                  aria-label="Clear selection"
                  onClick={() => {
                    setSelectedDataset(null);
                    setSelectedId(null);
                    setFeatures([]);
                    setEditMode(false);
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </PanelHeading>
            {!selectedDataset && features.length > 0 && (
              <nav
                className="evidence-navigation"
                aria-label="Evidence sections"
              >
                {[
                  ["sources", "Source evidence"],
                  ["checks", "Checks & measurements"],
                  ["attributes", "Attributes & geometry"],
                ]
                  .filter(([key]) => key !== "checks" || issue)
                  .map(([key, title]) => (
                    <button
                      key={key}
                      aria-pressed={detailSection === key}
                      disabled={editMode && key !== "attributes"}
                      onClick={() => setDetailSection(key)}
                    >
                      {title}
                    </button>
                  ))}
              </nav>
            )}
            {selectedDataset ? (
              <DatasetDetails
                dataset={selectedDataset}
                onMap={(mapping) =>
                  run(async () => {
                    await api(`/datasets/${selectedDataset.id}/mapping`, {
                      ...json({ mapping }),
                      method: "PUT",
                    });
                    setNotice(
                      "Field mapping saved. Run analysis to rebuild affected findings.",
                    );
                    const data = await refresh();
                    setSelectedDataset(
                      data.datasets.find((d) => d.id === selectedDataset.id) ||
                        null,
                    );
                  })
                }
              />
            ) : features.length ? (
              <>
                <div
                  className="evidence-scroll case-evidence"
                  data-section={detailSection}
                >
                  {issue && (
                    <div
                      className="finding-heading"
                      hidden={detailSection !== "sources"}
                    >
                      <StatusLabel status={issue.status}>
                        {label(issue.kind)} ·{" "}
                        {issue.status === "pending"
                          ? "Needs review"
                          : label(issue.status)}
                      </StatusLabel>
                      <h2>{issue.title}</h2>
                      <p>
                        {issue.evidence.reason ||
                          "Inspect the original and current feature geometry before deciding."}
                      </p>
                    </div>
                  )}
                  <div
                    className="evidence-section source-section"
                    hidden={detailSection !== "sources"}
                  >
                    <div className="section-line">
                      <h3>Source evidence</h3>
                      <button
                        className="text-btn"
                        onClick={() => setFitToken(fitToken + 1)}
                      >
                        Locate <MapIcon size={13} />
                      </button>
                    </div>
                    {features.map((f, i) => (
                      <div className="source-evidence" key={f.id}>
                        <span className="feature-letter">
                          {String.fromCharCode(65 + i)}
                        </span>
                        <div>
                          <strong>
                            {String(f.canonical.name || f.source_id)}
                          </strong>
                          <span>{f.dataset_name}</span>
                          <a
                            href={safeUrl(f.source.url)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {f.source.license} <ExternalLink size={11} />
                          </a>
                          <small>Source ID: {f.source_id}</small>
                        </div>
                      </div>
                    ))}
                    <div className="geometry-legend">
                      <span>
                        <i className="line original" />
                        {features.length > 1 ? "Source A" : "Original"}
                      </span>
                      <span>
                        <i className="line proposed" />
                        {features.length > 1
                          ? "Source B"
                          : "Current / proposed"}
                      </span>
                    </div>
                    <p className="microcopy">
                      Compare the supplied geometries. Accepting a relationship
                      or finding records the observation without replacing
                      either source.
                    </p>
                  </div>
                  {issue && (
                    <div
                      className="evidence-section checks-section"
                      hidden={detailSection !== "checks"}
                    >
                      <div className="section-line">
                        <h3>
                          {issue.evidence.score != null
                            ? "Match confidence"
                            : "Validation evidence"}
                        </h3>
                        {issue.evidence.score != null && (
                          <strong className="large-score">
                            {issue.evidence.score.toFixed(0)}
                            <small>/100</small>
                          </strong>
                        )}
                      </div>
                      {issue.evidence.components?.map((c) => (
                        <div className="score-row" key={c.name}>
                          <div>
                            <span>{c.name}</span>
                            <strong>{c.contribution.toFixed(1)} pts</strong>
                          </div>
                          <div className="score-track">
                            <span style={{ width: `${c.value * 100}%` }} />
                          </div>
                          <p>{c.explanation}</p>
                        </div>
                      ))}
                      {issue.evidence.score != null && (
                        <p className="microcopy">
                          Deterministic similarity, not a probability. Missing
                          evidence is omitted and weights are normalized.
                        </p>
                      )}
                      {issue.evidence.metrics && (
                        <dl className="measurements">
                          {Object.entries(issue.evidence.metrics).map(
                            ([k, v]) => (
                              <div key={k}>
                                <dt>
                                  {label(
                                    k
                                      .replace(/_m2$/, " (m²)")
                                      .replace(/_pct$/, " (%)")
                                      .replace(/_m$/, " (m)"),
                                  )}
                                </dt>
                                <dd>
                                  {typeof v === "number"
                                    ? fmt(v)
                                    : String(v ?? "Not supplied")}
                                </dd>
                              </div>
                            ),
                          )}
                        </dl>
                      )}
                      {issue.evidence.conflicts && (
                        <div className="conflict-values">
                          {Object.entries(issue.evidence.conflicts).map(
                            ([key, value]) => (
                              <p key={key}>
                                <strong>{label(key)}:</strong>{" "}
                                {JSON.stringify(value)}
                              </p>
                            ),
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  <div
                    className="evidence-section attributes-section"
                    hidden={detailSection !== "attributes"}
                  >
                    <h3>Feature A · canonical attributes</h3>
                    <dl className="measurements">
                      {Object.entries(features[0].canonical).map(
                        ([key, value]) => (
                          <div key={key}>
                            <dt>{label(key)}</dt>
                            <dd>
                              {value == null || value === ""
                                ? "Not supplied"
                                : String(value)}
                            </dd>
                          </div>
                        ),
                      )}
                      <div>
                        <dt>Measured area</dt>
                        <dd>{fmt(features[0].measured_area_m2 || 0)} m²</dd>
                      </div>
                      <div>
                        <dt>Source CRS</dt>
                        <dd>{features[0].source_crs}</dd>
                      </div>
                    </dl>
                    <details>
                      <summary>Original source attributes</summary>
                      <pre>
                        {JSON.stringify(features[0].attributes, null, 2)}
                      </pre>
                    </details>
                  </div>
                  {editMode && (
                    <div className="evidence-section edit-form">
                      <h3>Edit feature A</h3>
                      <p>
                        Drag map vertices or edit WGS84 GeoJSON below. Changes
                        require a review note.
                      </p>
                      <label>
                        Geometry
                        <textarea
                          rows={7}
                          autoFocus
                          value={geometryText}
                          onChange={(e) => {
                            setGeometryText(e.target.value);
                            setGeometry(null);
                          }}
                          spellCheck={false}
                        />
                      </label>
                      <label>
                        Canonical attributes
                        <textarea
                          rows={6}
                          value={attributeText}
                          onChange={(e) => setAttributeText(e.target.value)}
                          spellCheck={false}
                        />
                      </label>
                    </div>
                  )}
                </div>
                {issue?.status === "pending" ? (
                  <div className="decision-box">
                    <h3>Record your decision</h3>
                    <label>
                      Reviewer
                      <input
                        value={reviewer}
                        onChange={(e) => setReviewer(e.target.value)}
                        maxLength={100}
                      />
                    </label>
                    <label>
                      Decision note
                      <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Record the evidence and reason for your decision…"
                        rows={2}
                      />
                    </label>
                    <div className="decision-actions">
                      {editMode ? (
                        <>
                          <button
                            className="btn"
                            onClick={() => setEditMode(false)}
                          >
                            Cancel edit
                          </button>
                          <button
                            className="btn primary"
                            disabled={busy}
                            onClick={() => decide("edited")}
                          >
                            <Check size={15} />
                            Save edit
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="btn reject"
                            disabled={busy}
                            onClick={() => decide("rejected")}
                          >
                            <X size={14} />
                            Reject
                          </button>
                          <button
                            className="btn"
                            onClick={() => {
                              setDetailSection("attributes");
                              setEditMode(true);
                            }}
                          >
                            <Pencil size={14} />
                            Edit
                          </button>
                          <button
                            className="btn primary"
                            disabled={busy}
                            onClick={() => decide("accepted")}
                          >
                            <Check size={14} />
                            Accept
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  issue && (
                    <div className="decision-complete">
                      <div>
                        <div className="section-line">
                          <StatusLabel status={issue.status}>
                            {label(issue.status)}
                          </StatusLabel>
                          <button className="text-btn" onClick={showAudit}>
                            View audit trail <ArrowRight size={12} />
                          </button>
                        </div>
                        <details>
                          <summary>Recorded review note</summary>
                          <p>
                            {ws.decisions.find((d) => d.issue_id === issue.id)
                              ?.note ||
                              "Evidence superseded by a later revision."}
                          </p>
                        </details>
                      </div>
                    </div>
                  )
                )}
              </>
            ) : (
              <div className="evidence-empty">
                <h3>Open a case from the review queue</h3>
                <p>
                  Select a finding in the review queue or a feature on the map
                  to inspect its source, geometry and validation results.
                </p>
                <div className="review-steps">
                  <span>
                    <b>01</b>Compare source evidence
                  </span>
                  <span>
                    <b>02</b>Inspect measurements
                  </span>
                  <span>
                    <b>03</b>Record a review decision
                  </span>
                </div>
                <div className="human-note">
                  <span>Human review remains the final step.</span>
                </div>
              </div>
            )}
          </aside>
        </main>
      )}
      <footer className="footer">
        <span>
          {active ? "Processing" : "Local project"} · {fmt(ws.feature_count)}{" "}
          records
        </span>
        <span>
          Analysis: EPSG:32643 <span className="dot-divider">·</span> Map:
          EPSG:3857
        </span>
        <span>
          Original sources preserved{" "}
          <span className="footer-project">SIH 26013</span>
        </span>
      </footer>
      {modal === "layers" && (
        <Modal title="Map layers" onClose={() => setModal(null)}>
          <aside className="layer-panel">
            <PanelHeading title="Layers" count={ws.datasets.length}>
              <button
                className="icon-btn"
                aria-label="Close layers"
                onClick={() => setModal(null)}
              >
                <PanelLeftClose size={16} />
              </button>
            </PanelHeading>
            <div className="layer-list">
              {ws.datasets.map((d) => (
                <div
                  className={`layer-row ${selectedDataset?.id === d.id ? "selected" : ""}`}
                  key={d.id}
                >
                  <input
                    type="checkbox"
                    aria-label={`Show ${d.name}`}
                    checked={visible[d.id] !== false}
                    onChange={(e) =>
                      setVisible({ ...visible, [d.id]: e.target.checked })
                    }
                  />
                  <button
                    aria-pressed={selectedDataset?.id === d.id}
                    onClick={() => chooseDataset(d)}
                  >
                    <span className={`layer-symbol ${d.kind}`} />
                    <span>
                      <strong>{d.name.replace("OpenStreetMap · ", "")}</strong>
                      <small>
                        {fmt(d.inspection.count)}{" "}
                        {d.kind === "raster" ? "raster" : "features"} ·{" "}
                        {d.source.license.includes("ODbL") ||
                        d.source.license.includes("Database")
                          ? "ODbL"
                          : d.source.license}
                      </small>
                    </span>
                    <ChevronRight size={14} />
                  </button>
                </div>
              ))}
            </div>
            <button className="add-layer" onClick={() => setModal("import")}>
              <Plus size={15} />
              Add a dataset
            </button>
            <div className="layer-bottom">
              <div className="layer-intro">
                <span className="eyebrow">Project coordinate system</span>
                <strong>WGS 84 / UTM zone 43N</strong>
                <span>EPSG:32643 · metres</span>
              </div>
              <button
                className="text-btn reference-load"
                disabled={!!active || busy}
                onClick={() => run(() => api("/demo", json({})))}
              >
                <Database size={13} />
                Load / resume reference pack
              </button>
              <div className="coverage-note">
                <div>
                  <strong>Cadastral coverage gap</strong>
                  <p>
                    No licensed parcel fabric is bundled. Building footprints
                    are labelled as buildings.
                  </p>
                </div>
              </div>
              <button className="text-btn" onClick={showSources}>
                View source inventory <ExternalLink size={13} />
              </button>
              <div className="attribution">
                ©{" "}
                <a
                  href="https://www.openstreetmap.org/copyright"
                  target="_blank"
                  rel="noreferrer"
                >
                  OpenStreetMap contributors
                </a>
                <br />
                District reference: geoBoundaries / Pathways
              </div>
            </div>
          </aside>
        </Modal>
      )}
      {modal === "import" && (
        <ImportModal
          error={error}
          onClose={() => setModal(null)}
          onSubmit={(form) =>
            run(async () => {
              await api("/import", { method: "POST", body: form });
              setModal(null);
              setNotice(
                "Import queued. Geometry and file validation are running.",
              );
            })
          }
        />
      )}
      {modal === "sources" && (
        <Modal
          title="Indore data-source inventory"
          wide
          onClose={() => setModal(null)}
        >
          <div className="modal-content">
            <p className="modal-lead">
              Available reference data and documented access gaps. No
              authoritative cadastral parcel fabric or private owner information
              is bundled.
            </p>
            {inventory.map((s) => (
              <article className="inventory-source" key={s.id}>
                <div className="section-line">
                  <h3>{s.name}</h3>
                  <StatusLabel
                    status={s.status === "available" ? "accepted" : "pending"}
                  >
                    {s.status === "available" ? "Available" : "Access gap"}
                  </StatusLabel>
                </div>
                <p>{s.limitations}</p>
                <dl>
                  <div>
                    <dt>Provider</dt>
                    <dd>{s.provider}</dd>
                  </div>
                  <div>
                    <dt>Licence</dt>
                    <dd>{s.license}</dd>
                  </div>
                  <div>
                    <dt>Collection / epoch</dt>
                    <dd>{s.collection_date}</dd>
                  </div>
                  <div>
                    <dt>Retrieved</dt>
                    <dd>{s.retrieved_at}</dd>
                  </div>
                  <div>
                    <dt>CRS</dt>
                    <dd>{s.crs || "Not verified"}</dd>
                  </div>
                </dl>
                <a href={safeUrl(s.url)} target="_blank" rel="noreferrer">
                  Open source reference <ExternalLink size={13} />
                </a>
              </article>
            ))}
          </div>
        </Modal>
      )}
      {modal === "export" && (
        <Modal
          title="Export reviewed results"
          feedback={error}
          onClose={() => setModal(null)}
        >
          <div className="modal-content">
            <p className="modal-lead">
              Exports include features referenced by accepted or edited
              findings, a validation report, source licences and the audit
              trail.
            </p>
            <div className="export-summary">
              <div>
                <strong>
                  {
                    ws.issues.filter((i) =>
                      ["accepted", "edited"].includes(i.status),
                    ).length
                  }{" "}
                  accepted / edited findings
                </strong>
                <span>
                  {pending.length} pending findings remain documented in the
                  report.
                </span>
              </div>
            </div>
            {["geojson", "csv", "gpkg"].map((f) => (
              <button
                className="export-option"
                key={f}
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const r = await fetch("/api/export/" + f);
                    if (!r.ok) {
                      const d = await r.json();
                      throw new Error(d.detail);
                    }
                    const blob = await r.blob();
                    const u = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = u;
                    a.download = `indore-reviewed-${f}.zip`;
                    a.click();
                    setTimeout(() => URL.revokeObjectURL(u), 1000);
                    setNotice(
                      "Reviewed export and validation report downloaded.",
                    );
                    setModal(null);
                  })
                }
              >
                <span>
                  <strong>
                    {f === "gpkg"
                      ? "GeoPackage"
                      : f === "csv"
                        ? "CSV"
                        : "GeoJSON"}
                  </strong>
                  <small>
                    {f === "gpkg"
                      ? "UTM 43N · spatial layers"
                      : f === "csv"
                        ? "Canonical fields + WGS84 geometry WKT"
                        : "WGS84 · portable geospatial features"}{" "}
                    + audit ZIP
                  </small>
                </span>
                <ArrowDownToLine size={18} />
              </button>
            ))}
            <p className="microcopy">
              Acceptance does not certify title or survey accuracy. OSM-derived
              exports retain ODbL attribution obligations.
            </p>
          </div>
        </Modal>
      )}
      {modal === "audit" && (
        <Modal title="Project audit trail" wide onClose={() => setModal(null)}>
          <div className="modal-content">
            {!audit.length ? (
              <p>
                No activity yet. Imports, processing, decisions and exports
                appear here.
              </p>
            ) : (
              <div className="audit-list">
                {audit.map((e) => (
                  <div className="audit-event" key={String(e.sequence)}>
                    <span className="audit-index">
                      {String(e.sequence).padStart(2, "0")}
                    </span>
                    <div>
                      <strong>{label(String(e.action))}</strong>
                      <time>{String(e.timestamp)}</time>
                      <details>
                        <summary>Event details</summary>
                        <pre>{JSON.stringify(e.detail, null, 2)}</pre>
                      </details>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  action: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon}
      <h2>{title}</h2>
      <p>{text}</p>
      {action}
    </div>
  );
}
function DatasetDetails({
  dataset: d,
  onMap,
}: {
  dataset: Dataset;
  onMap: (mapping: Record<string, string>) => void;
}) {
  const [mapping, setMapping] = useState(d.field_mapping);
  useEffect(() => setMapping(d.field_mapping), [d]);
  return (
    <div className="evidence-scroll dataset-details">
      <div className="evidence-section">
        <span className="eyebrow">
          {label(String(d.source.dataset_role || d.kind))} dataset
        </span>
        <h2>{d.name}</h2>
        <p>{d.source.limitations}</p>
        <a href={safeUrl(d.source.url)} target="_blank" rel="noreferrer">
          Source reference <ExternalLink size={12} />
        </a>
        <dl className="measurements">
          <div>
            <dt>Provider</dt>
            <dd>{d.source.provider}</dd>
          </div>
          <div>
            <dt>Licence</dt>
            <dd>{d.source.license}</dd>
          </div>
          <div>
            <dt>Collection / epoch</dt>
            <dd>{d.source.collection_date}</dd>
          </div>
          <div>
            <dt>Source CRS</dt>
            <dd>{d.inspection.source_crs}</dd>
          </div>
          <div>
            <dt>Project CRS</dt>
            <dd>{d.inspection.project_crs}</dd>
          </div>
          <div>
            <dt>Features</dt>
            <dd>{fmt(d.inspection.count)}</dd>
          </div>
          <div>
            <dt>Invalid geometries</dt>
            <dd>{d.inspection.invalid_count}</dd>
          </div>
          <div>
            <dt>Without geometry</dt>
            <dd>{d.inspection.missing_geometry}</dd>
          </div>
          {Object.entries(d.inspection.geometry_types).map(([key, v]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{fmt(v)}</dd>
            </div>
          ))}
        </dl>
        {d.inspection.note && <p>{d.inspection.note}</p>}
        {d.inspection.raster_statistics && (
          <dl className="measurements">
            {Object.entries(d.inspection.raster_statistics).map(
              ([key, value]) => (
                <div key={key}>
                  <dt>{label(key)}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ),
            )}
          </dl>
        )}
        <details>
          <summary>Original file checksum (SHA-256)</summary>
          <code className="checksum">{d.sha256}</code>
        </details>
      </div>
      {d.kind !== "raster" && (
        <div className="evidence-section">
          <h3>Canonical field mapping</h3>
          <p className="microcopy">
            Explicit mappings are applied to every record. Missing fields remain
            empty.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              onMap(mapping);
            }}
          >
            {Object.entries(mapping).map(([key, v]) => (
              <label key={key}>
                {label(key)}
                <select
                  value={v}
                  onChange={(e) =>
                    setMapping({ ...mapping, [key]: e.target.value })
                  }
                >
                  <option value="">Not supplied</option>
                  {d.inspection.columns.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            ))}
            <button className="btn primary" type="submit">
              <Check size={15} />
              Apply mapping
            </button>
          </form>
        </div>
      )}
      {d.inspection.completeness && (
        <div className="evidence-section">
          <h3>Attribute completeness</h3>
          <dl className="measurements">
            {Object.entries(d.inspection.completeness).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}%</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
function ImportModal({
  onClose,
  onSubmit,
  error,
}: {
  onClose: () => void;
  onSubmit: (f: FormData) => void;
  error: string;
}) {
  const [file, setFile] = useState<File | null>(null),
    [submitting, setSubmitting] = useState(false);
  return (
    <Modal title="Import a dataset" feedback={error} onClose={onClose}>
      <form
        className="modal-content import-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setSubmitting(true);
          try {
            await onSubmit(new FormData(e.currentTarget));
          } finally {
            setSubmitting(false);
          }
        }}
      >
        <label className="file-drop">
          <strong>{file?.name || "Choose a geospatial file"}</strong>
          <span>
            GeoJSON · Shapefile ZIP · GeoPackage · KML · CSV · GeoTIFF
          </span>
          <small>Maximum 30 MB / 15,000 vector records</small>
          <input
            type="file"
            name="file"
            required
            accept=".geojson,.json,.zip,.gpkg,.kml,.csv,.tif,.tiff"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <div className="form-grid">
          <label>
            Dataset name
            <input
              name="name"
              required
              placeholder="e.g. Ward survey footprints"
            />
          </label>
          <label>
            Dataset role
            <select name="kind" defaultValue="building">
              {[
                "building",
                "parcel",
                "road",
                "utility",
                "amenity",
                "waterway",
                "boundary",
                "survey_point",
                "ground_truth",
                "gnss",
                "record",
                "coverage",
                "raster",
                "orthophoto",
                "dsm",
                "dtm",
              ].map((k) => (
                <option key={k} value={k}>
                  {label(k)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Source / organization
            <input
              name="source_name"
              required
              placeholder="Original data provider"
            />
          </label>
          <label>
            Licence / permission
            <input
              name="license"
              required
              placeholder="e.g. ODbL-1.0 or internal permission"
            />
          </label>
          <label>
            Source URL
            <input name="source_url" type="url" placeholder="https://…" />
          </label>
          <label>
            Collection date / epoch
            <input name="collection_date" placeholder="YYYY-MM-DD or Unknown" />
          </label>
          <label>
            Source CRS override
            <input name="crs" placeholder="Auto-detect; e.g. EPSG:32643" />
          </label>
          <label>
            GeoPackage layer
            <input name="layer" placeholder="Required for multiple layers" />
          </label>
        </div>
        <div className="form-note">
          <Info size={16} />
          <p>
            Shapefiles need .shp, .shx, .dbf and preferably .prj in one ZIP. CSV
            accepts longitude/latitude, lon/lat, or x/y with a declared CRS.
            Tables without coordinates can match by identifiers.
          </p>
        </div>
        <details className="import-guide">
          <summary>Dataset intake guides</summary>
          <ul>
            <li>
              <strong>Municipal / utility GIS:</strong> use GeoPackage, GeoJSON
              or Shapefile ZIP with a documented CRS and collection date.
            </li>
            <li>
              <strong>Revenue / cadastral records:</strong> use parcel or record
              roles; map parcel references explicitly and submit anonymized data
              only.
            </li>
            <li>
              <strong>GNSS / ground truth:</strong> use GNSS, ground truth or
              survey-point roles; include survey epoch and horizontal accuracy
              in metres where available.
            </li>
            <li>
              <strong>Drone / ORI / DSM / DTM:</strong> use a georeferenced
              GeoTIFF and select Orthophoto, DSM or DTM. DSM/DTM receive
              elevation statistics and a hillshade-ready preview.
            </li>
          </ul>
          <p>
            Bhumi Setu preserves supplied georeferencing and proposes review
            findings. It does not infer control points, adjust surveys or
            certify a cadastral boundary.
          </p>
        </details>
        <label className="checkbox-label">
          <input type="checkbox" name="anonymized" value="true" required />
          <span>
            I confirm that this file is legally accessible and contains no
            private owner information.
          </span>
        </label>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={submitting} type="submit">
            <FileUp size={16} />
            {submitting ? "Uploading…" : "Import & inspect"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

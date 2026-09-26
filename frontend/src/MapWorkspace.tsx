import { useEffect, useRef, useState } from "react";
import Map from "ol/Map";
import Feature from "ol/Feature";
import View from "ol/View";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import GeoJSON from "ol/format/GeoJSON";
import { Fill, Stroke, Style, Circle as CircleStyle, Text } from "ol/style";
import { fromLonLat, transformExtent } from "ol/proj";
import { defaults as defaultControls, ScaleLine } from "ol/control";
import TileLayer from "ol/layer/Tile";
import OSM from "ol/source/OSM";
import ImageLayer from "ol/layer/Image";
import ImageStatic from "ol/source/ImageStatic";
import Modify from "ol/interaction/Modify";
import { boundingExtent } from "ol/extent";
import type {
  Collection,
  Dataset,
  EvidenceFeature,
  Geometry,
  Issue,
} from "./types";
import { Crosshair, Layers, MapPin, Minus, Plus } from "lucide-react";
const colors: Record<string, string> = {
  building: "#67887d",
  parcel: "#397b71",
  road: "#c5aa7b",
  amenity: "#8664a1",
  waterway: "#5794ae",
  boundary: "#7e8581",
  survey_point: "#93587c",
  coverage: "#c09953",
  utility: "#875c48",
  ground_truth: "#b54c69",
  gnss: "#276f9d",
};
const styles: Record<string, Style> = {};
function layerStyle(kind: string) {
  if (!styles[kind])
    styles[kind] = new Style({
      fill: new Fill({
        color:
          kind === "boundary" ? "#00000000" : `${colors[kind] || "#658b80"}35`,
      }),
      stroke: new Stroke({
        color: colors[kind] || "#658b80",
        width: kind === "road" ? 2 : kind === "boundary" ? 2 : 1,
        lineDash: kind === "boundary" ? [8, 6] : undefined,
      }),
      image: new CircleStyle({
        radius: 4,
        fill: new Fill({ color: colors[kind] || "#658b80" }),
        stroke: new Stroke({ color: "#fff", width: 1.5 }),
      }),
    });
  return styles[kind];
}
export function MapWorkspace({
  datasets,
  collections,
  visible,
  selected,
  issue,
  onFeature,
  comparison,
  editMode,
  onEdit,
  fitToken,
}: {
  datasets: Dataset[];
  collections: Record<string, Collection>;
  visible: Record<string, boolean>;
  selected: EvidenceFeature[];
  issue: Issue | null;
  onFeature: (id: string) => void;
  comparison: string;
  editMode: boolean;
  onEdit: (geometry: Geometry) => void;
  fitToken: number;
}) {
  const target = useRef<HTMLDivElement>(null);
  const map = useRef<Map | null>(null);
  const layers = useRef<
    Record<string, VectorLayer<VectorSource> | ImageLayer<ImageStatic>>
  >({});
  const overlay = useRef(new VectorSource());
  const editable = useRef(new VectorSource());
  const [basemap, setBasemap] = useState(false);
  const base = useRef<TileLayer<OSM> | null>(null);
  const [coords, setCoords] = useState("22.7175° N, 75.8575° E");
  const [baseError, setBaseError] = useState(false);
  const featureHandler = useRef(onFeature);
  featureHandler.current = onFeature;
  useEffect(() => {
    if (!target.current) return;
    const tile = new TileLayer({
      source: new OSM(),
      visible: false,
      opacity: 0.38,
    });
    base.current = tile;
    tile.getSource()?.on("tileloaderror", () => setBaseError(true));
    const m = new Map({
      target: target.current,
      layers: [tile],
      view: new View({ center: fromLonLat([75.8575, 22.7175]), zoom: 16 }),
      controls: defaultControls({
        zoom: false,
        rotate: false,
        attribution: true,
      }).extend([
        new ScaleLine({ bar: true, steps: 2, text: true, minWidth: 90 }),
      ]),
    });
    map.current = m;
    m.addLayer(
      new VectorLayer({
        source: overlay.current,
        zIndex: 90,
        style: (f) =>
          new Style({
            fill: new Fill({
              color:
                f.get("evidenceType") === "original"
                  ? "#c98a241c"
                  : "#e0a22c38",
            }),
            stroke: new Stroke({
              color:
                f.get("evidenceType") === "original" ? "#16756a" : "#c88013",
              width: 3,
              lineDash:
                f.get("evidenceType") === "original" ? [7, 4] : undefined,
            }),
            image: new CircleStyle({
              radius: 8,
              fill: new Fill({ color: "#e0a22c" }),
              stroke: new Stroke({ color: "#72500e", width: 2 }),
            }),
            text: new Text({
              text: f.get("label") || "",
              font: "600 12px sans-serif",
              offsetY: -16,
              fill: new Fill({ color: "#33483e" }),
              stroke: new Stroke({ color: "#fff", width: 3 }),
            }),
          }),
      }),
    );
    m.addLayer(
      new VectorLayer({
        source: editable.current,
        zIndex: 100,
        style: new Style({
          fill: new Fill({ color: "#4eabb344" }),
          stroke: new Stroke({ color: "#187e91", width: 3 }),
          image: new CircleStyle({
            radius: 5,
            fill: new Fill({ color: "#187e91" }),
          }),
        }),
      }),
    );
    m.on("singleclick", (e) => {
      m.forEachFeatureAtPixel(
        e.pixel,
        (f) => {
          const id = f.get("feature_id");
          if (id) {
            featureHandler.current(String(id));
            return true;
          }
          return false;
        },
        { hitTolerance: 5 },
      );
    });
    m.on("pointermove", (e) => {
      target.current!.style.cursor = m.hasFeatureAtPixel(e.pixel)
        ? "pointer"
        : "";
      const c = transformExtent(
        [e.coordinate[0], e.coordinate[1], e.coordinate[0], e.coordinate[1]],
        "EPSG:3857",
        "EPSG:4326",
      );
      setCoords(`${c[1].toFixed(5)}° N, ${c[0].toFixed(5)}° E`);
    });
    return () => {
      m.setTarget(undefined);
      m.dispose();
      // React can recreate the map while keeping refs during effect replay.
      // Layer instances belong to that map and must be attached afresh.
      layers.current = {};
      map.current = null;
    };
  }, []);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    for (const d of datasets) {
      if (layers.current[d.id]) {
        layers.current[d.id].setVisible(visible[d.id] !== false);
        continue;
      }
      if (d.kind === "raster" && d.inspection.bbox) {
        const l = new ImageLayer({
          source: new ImageStatic({
            url: `/api/datasets/${d.id}/raster-preview`,
            imageExtent: d.inspection.bbox,
            projection: "EPSG:4326",
          }),
          opacity: 0.65,
          zIndex: 5,
        });
        layers.current[d.id] = l;
        m.addLayer(l);
      } else if (collections[d.id]) {
        const features = new GeoJSON().readFeatures(collections[d.id], {
          dataProjection: "EPSG:4326",
          featureProjection: "EPSG:3857",
        });
        const l = new VectorLayer({
          source: new VectorSource({ features }),
          style: layerStyle(d.kind),
          zIndex: d.kind === "boundary" ? 1 : d.kind === "road" ? 15 : 20,
        });
        layers.current[d.id] = l;
        m.addLayer(l);
      }
      layers.current[d.id]?.setVisible(visible[d.id] !== false);
    }
  }, [datasets, collections, visible]);
  // Rebuild vectors when edits refresh the collection.
  useEffect(() => {
    for (const [id, collection] of Object.entries(collections)) {
      const layer = layers.current[id];
      if (layer instanceof VectorLayer) {
        layer.getSource()?.clear();
        layer.getSource()?.addFeatures(
          new GeoJSON().readFeatures(collection, {
            dataProjection: "EPSG:4326",
            featureProjection: "EPSG:3857",
          }),
        );
      }
    }
  }, [collections]);
  useEffect(() => {
    overlay.current.clear();
    const format = new GeoJSON();
    selected.forEach((f, i) => {
      const sourceComparison = selected.length > 1 && !issue?.proposed_geometry;
      if (
        sourceComparison &&
        ((comparison === "original" && i > 0) ||
          (comparison === "proposed" && i === 0))
      )
        return;
      const variants = sourceComparison
        ? [{ g: f.geometry, type: i === 0 ? "original" : "proposed" }]
        : comparison === "original"
          ? [{ g: f.original_wgs84, type: "original" }]
          : comparison === "proposed"
            ? [
                {
                  g:
                    i === 0 && issue?.proposed_geometry
                      ? issue.proposed_geometry
                      : f.geometry,
                  type: "proposed",
                },
              ]
            : [
                { g: f.original_wgs84, type: "original" },
                {
                  g:
                    i === 0 && issue?.proposed_geometry
                      ? issue.proposed_geometry
                      : f.geometry,
                  type: "proposed",
                },
              ];
      for (const v of variants) {
        if (v.g) {
          const feature = format.readFeature(
            {
              type: "Feature",
              geometry: v.g,
              properties: {
                feature_id: f.id,
                evidenceType: v.type,
                label: i === 0 ? "A" : "B",
              },
            },
            { featureProjection: "EPSG:3857" },
          );
          overlay.current.addFeature(feature as Feature);
        }
      }
    });
    if (issue?.evidence.gap_geometry) {
      overlay.current.addFeature(
        format.readFeature(
          {
            type: "Feature",
            geometry: issue.evidence.gap_geometry,
            properties: {},
          },
          { featureProjection: "EPSG:3857" },
        ) as Feature,
      );
    }
  }, [selected, comparison, issue]);
  useEffect(() => {
    if (!selected.length || !map.current) return;
    const geometries = selected
      .filter((f) => f.geometry)
      .flatMap((f) =>
        new GeoJSON().readFeatures(
          { type: "Feature", geometry: f.geometry, properties: {} },
          { featureProjection: "EPSG:3857" },
        ),
      );
    if (geometries.length) {
      const ext = boundingExtent(
        geometries.flatMap((f) => {
          const e = f.getGeometry()!.getExtent();
          return [
            [e[0], e[1]],
            [e[2], e[3]],
          ];
        }),
      );
      map.current.getView().fit(ext, {
        padding: [100, 100, 100, 100],
        maxZoom: 19,
        duration: 400,
      });
    }
  }, [selected.map((f) => f.id).join(","), fitToken]);
  useEffect(() => {
    editable.current.clear();
    if (!editMode || !selected[0]?.geometry || !map.current) return;
    const f = new GeoJSON().readFeature(
      {
        type: "Feature",
        geometry: issue?.proposed_geometry || selected[0].geometry,
        properties: {},
      },
      { featureProjection: "EPSG:3857" },
    );
    editable.current.addFeature(f as Feature);
    const modify = new Modify({ source: editable.current });
    map.current.addInteraction(modify);
    modify.on("modifyend", () =>
      onEdit(
        new GeoJSON().writeGeometryObject((f as Feature).getGeometry()!, {
          featureProjection: "EPSG:3857",
          dataProjection: "EPSG:4326",
        }) as Geometry,
      ),
    );
    return () => {
      map.current?.removeInteraction(modify);
      editable.current.clear();
    };
  }, [editMode, selected[0]?.id]);
  useEffect(() => {
    base.current?.setVisible(basemap);
  }, [basemap]);
  const fit = () =>
    map.current?.getView().animate({
      center: fromLonLat([75.8575, 22.7175]),
      zoom: 16,
      duration: 400,
    });
  return (
    <div className="map-shell">
      <div
        ref={target}
        className="map"
        tabIndex={0}
        aria-label="Indore interactive reference map. Use arrow keys to pan and plus or minus to zoom."
      />
      <div className="map-location">
        <MapPin size={14} />
        <span>Rajwada & central Indore</span>
        <span className="dot-divider">/</span>
        <span>Reference extent</span>
      </div>
      <div className="map-tools">
        <button
          title="Zoom in"
          aria-label="Zoom in"
          onClick={() =>
            map.current?.getView().animate({
              zoom: (map.current.getView().getZoom() || 16) + 1,
              duration: 180,
            })
          }
        >
          <Plus size={18} />
        </button>
        <button
          title="Zoom out"
          aria-label="Zoom out"
          onClick={() =>
            map.current?.getView().animate({
              zoom: (map.current.getView().getZoom() || 16) - 1,
              duration: 180,
            })
          }
        >
          <Minus size={18} />
        </button>
        <button
          title="Return to pilot extent"
          aria-label="Return to pilot extent"
          onClick={fit}
        >
          <Crosshair size={18} />
        </button>
        <button
          title="Toggle OSM basemap"
          aria-label="Toggle OSM basemap"
          aria-pressed={basemap}
          onClick={() => setBasemap(!basemap)}
        >
          <Layers size={18} />
        </button>
      </div>
      <div className="north">
        N<span>↑</span>
      </div>
      <div className="map-key">
        <span>
          <i className="swatch building" />
          Building
        </span>
        <span>
          <i className="swatch road" />
          Road
        </span>
        <span>
          <i className="swatch amenity" />
          Amenity
        </span>
        <span>
          <i className="swatch finding" />
          Evidence
        </span>
      </div>
      <div className="map-coordinates">{coords}</div>
      {baseError && basemap && (
        <div className="map-notice">
          Basemap tiles unavailable. Imported reference layers remain visible.
        </div>
      )}
      {editMode && (
        <div className="edit-banner">
          Drag vertices to revise geometry. Alt + click removes a vertex. Save
          in the evidence panel.
        </div>
      )}
    </div>
  );
}

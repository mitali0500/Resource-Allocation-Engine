import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import { ALGORITHM_LABELS, fmtTime, useColors } from "../theme.js";

const PRIORITY_RADIUS = { 1: 5, 2: 7, 3: 9 };
const PRIORITY_LABEL = { 1: "low", 2: "normal", 3: "urgent" };

/** Shared registry so panning or zooming one map moves the others. */
export function useMapSync() {
  return useRef({ maps: new Set(), syncing: false }).current;
}

function SyncView({ sync }) {
  const map = useMap();
  useEffect(() => {
    sync.maps.add(map);
    const follow = () => {
      if (sync.syncing) return;
      sync.syncing = true;
      for (const other of sync.maps) {
        if (other !== map) other.setView(map.getCenter(), map.getZoom(), { animate: false });
      }
      sync.syncing = false;
    };
    map.on("move zoomend", follow);
    return () => {
      map.off("move zoomend", follow);
      sync.maps.delete(map);
    };
  }, [map, sync]);
  return null;
}

function FitToScenario({ scenario }) {
  const map = useMap();
  useEffect(() => {
    const points = [
      ...scenario.technicians.map((t) => [t.home.lat, t.home.lon]),
      ...scenario.requests.map((r) => [r.location.lat, r.location.lon]),
    ];
    if (points.length) map.fitBounds(points, { padding: [16, 16], animate: false });
  }, [map, scenario]);
  return null;
}

function techIcon(selected) {
  // 24px hit area around a 12px square, so it is easy to click
  return L.divIcon({
    className: "",
    html: `<span class="tech-marker${selected ? " selected" : ""}"></span>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

export default function AllocationMap({ result, scenario, lookups, selection, onSelect, sync }) {
  const colors = useColors();
  const color = colors.algorithm(result.algorithm);
  // A wider click tolerance than the drawn marker (Leaflet canvas hit testing)
  const renderer = useMemo(() => L.canvas({ tolerance: 6 }), []);

  const byRequest = useMemo(
    () => Object.fromEntries(result.assignments.map((a) => [a.request_id, a])),
    [result],
  );

  const routes = useMemo(() => {
    const perTech = {};
    for (const a of result.assignments) (perTech[a.technician_id] ??= []).push(a);
    return Object.entries(perTech).map(([techId, jobs]) => {
      const home = lookups.techById[techId].home;
      jobs.sort((x, y) => x.start - y.start);
      return {
        techId,
        points: [[home.lat, home.lon], ...jobs.map((j) => {
          const loc = lookups.reqById[j.request_id].location;
          return [loc.lat, loc.lon];
        })],
      };
    });
  }, [result, lookups]);

  const highlightedTech =
    selection?.kind === "technician" ? selection.id
    : selection?.kind === "request" ? byRequest[selection.id]?.technician_id
    : null;

  const m = result.metrics;

  return (
    <article className="map-card">
      <header className="map-card-header">
        <span className="swatch" style={{ background: color }} aria-hidden="true" />
        <h2>{ALGORITHM_LABELS[result.algorithm] ?? result.algorithm}</h2>
        <span className="map-card-summary">
          {m.assigned}/{m.requests_total} assigned · {m.total_travel_km.toFixed(0)} km
        </span>
      </header>
      <MapContainer
        className="map"
        center={[12.97, 77.59]}
        zoom={11}
        renderer={renderer}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <SyncView sync={sync} />
        <FitToScenario scenario={scenario} />

        {routes.map(({ techId, points }) => {
          const focus = highlightedTech === techId;
          const dim = highlightedTech && !focus;
          return (
            <Polyline
              key={`${techId}-${focus}`}
              positions={points}
              pathOptions={{ color, weight: focus ? 4 : 2, opacity: dim ? 0.12 : focus ? 1 : 0.55 }}
              eventHandlers={{ click: () => onSelect({ kind: "technician", id: techId }) }}
            />
          );
        })}

        {scenario.requests.map((r) => {
          const a = byRequest[r.id];
          const selected = selection?.kind === "request" && selection.id === r.id;
          const style = a
            ? { color: selected ? colors.ink : colors.surface, weight: 2, fillColor: color, fillOpacity: 1 }
            : { color: selected ? colors.ink : colors.critical, weight: 2.5, fillColor: colors.surface, fillOpacity: 0.9 };
          return (
            <CircleMarker
              key={`${r.id}-${selected}`}
              center={[r.location.lat, r.location.lon]}
              radius={PRIORITY_RADIUS[r.priority] + (selected ? 2 : 0)}
              pathOptions={style}
              eventHandlers={{ click: () => onSelect({ kind: "request", id: r.id }) }}
            >
              <Tooltip direction="top" offset={[0, -6]}>
                <strong>{r.id}</strong> · {PRIORITY_LABEL[r.priority]} · {[...r.required_skills].join(", ")}
                <br />
                Window {fmtTime(r.earliest_start)}–{fmtTime(r.latest_start)}, {r.duration} min
                <br />
                {a
                  ? `${lookups.techById[a.technician_id].name} at ${fmtTime(a.start)}`
                  : "Unassigned"}
              </Tooltip>
            </CircleMarker>
          );
        })}

        {scenario.technicians.map((t) => {
          const selected = highlightedTech === t.id;
          return (
            <Marker
              key={`${t.id}-${selected}`}
              position={[t.home.lat, t.home.lon]}
              icon={techIcon(selected)}
              eventHandlers={{ click: () => onSelect({ kind: "technician", id: t.id }) }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <strong>{t.name}</strong> ({t.id})
                <br />
                {[...t.skills].join(", ")} · shift {fmtTime(t.shift_start)}–{fmtTime(t.shift_end)}
              </Tooltip>
            </Marker>
          );
        })}
      </MapContainer>
    </article>
  );
}

export function MapLegend() {
  const colors = useColors();
  return (
    <div className="legend" aria-label="Map legend">
      <span className="legend-item">
        <span className="tech-marker legend-tech" aria-hidden="true" /> Technician home
      </span>
      <span className="legend-item">
        <svg width="16" height="16" aria-hidden="true">
          <circle cx="8" cy="8" r="6" fill={colors.ink} stroke={colors.surface} strokeWidth="2" />
        </svg>
        Assigned job (filled in the algorithm's colour)
      </span>
      <span className="legend-item">
        <svg width="16" height="16" aria-hidden="true">
          <circle cx="8" cy="8" r="5.5" fill={colors.surface} stroke={colors.critical} strokeWidth="2.5" />
        </svg>
        Unassigned job (hollow ring)
      </span>
      <span className="legend-item">
        <svg width="34" height="16" aria-hidden="true">
          <circle cx="5" cy="8" r="3" fill="currentColor" />
          <circle cx="15" cy="8" r="4.5" fill="currentColor" />
          <circle cx="28" cy="8" r="6" fill="currentColor" />
        </svg>
        Low / normal / urgent
      </span>
      <span className="legend-item hint">Lines are each technician's route. Click a job or technician to compare decisions. Maps pan together.</span>
    </div>
  );
}

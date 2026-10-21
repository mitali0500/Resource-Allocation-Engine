import { useMemo } from "react";
import { ALGORITHM_LABELS, fmtTime, useColors } from "../theme.js";

const PRIORITY_LABEL = { 1: "low", 2: "normal", 3: "urgent" };

function AlgoName({ name }) {
  const colors = useColors();
  return (
    <span className="algo-name">
      <span className="swatch" style={{ background: colors.algorithm(name) }} aria-hidden="true" />
      {ALGORITHM_LABELS[name] ?? name}
    </span>
  );
}

function RequestDetail({ id, results, lookups, onSelect }) {
  const req = lookups.reqById[id];
  return (
    <>
      <h3>
        Job {req.id} <span className="muted">· {PRIORITY_LABEL[req.priority]}</span>
      </h3>
      <p className="muted">
        Needs {[...req.required_skills].join(" + ")} · start between {fmtTime(req.earliest_start)} and{" "}
        {fmtTime(req.latest_start)} · {req.duration} min on site
      </p>
      <ul className="decisions">
        {results.map((r) => {
          const a = r.assignments.find((x) => x.request_id === id);
          const u = r.unassigned.find((x) => x.request_id === id);
          return (
            <li key={r.algorithm}>
              <AlgoName name={r.algorithm} />
              {a ? (
                <>
                  <p>
                    <button type="button" className="link" onClick={() => onSelect({ kind: "technician", id: a.technician_id })}>
                      {lookups.techById[a.technician_id].name}
                    </button>{" "}
                    {fmtTime(a.start)}–{fmtTime(a.end)}
                  </p>
                  <p className="explanation">{a.explanation}</p>
                </>
              ) : (
                <p className="unassigned">
                  <span aria-hidden="true">⊘</span> Unassigned: {u?.reason}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

function TechnicianDetail({ id, results, lookups, onSelect }) {
  const tech = lookups.techById[id];
  return (
    <>
      <h3>{tech.name} <span className="muted">· {tech.id}</span></h3>
      <p className="muted">
        {[...tech.skills].join(", ")} · shift {fmtTime(tech.shift_start)}–{fmtTime(tech.shift_end)}
      </p>
      <ul className="decisions">
        {results.map((r) => {
          const jobs = r.assignments.filter((a) => a.technician_id === id).sort((x, y) => x.start - y.start);
          const km = jobs.reduce((s, a) => s + a.travel_km, 0);
          return (
            <li key={r.algorithm}>
              <AlgoName name={r.algorithm} />
              <p className="muted">{jobs.length} job(s) · {km.toFixed(1)} km</p>
              {jobs.length > 0 && (
                <ol className="schedule">
                  {jobs.map((a) => (
                    <li key={a.request_id}>
                      <span className="time">{fmtTime(a.start)}–{fmtTime(a.end)}</span>
                      <button type="button" className="link" onClick={() => onSelect({ kind: "request", id: a.request_id })}>
                        {a.request_id}
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

/** Jobs where the algorithms did not all make the same decision: the interesting ones. */
function Disagreements({ results, lookups, onSelect }) {
  const rows = useMemo(() => {
    const ids = new Set(results.flatMap((r) => [...r.assignments, ...r.unassigned].map((x) => x.request_id)));
    const out = [];
    for (const id of [...ids].sort()) {
      const outcomes = results.map((r) => r.assignments.find((a) => a.request_id === id)?.technician_id ?? null);
      if (new Set(outcomes).size > 1) out.push({ id, outcomes });
    }
    return out;
  }, [results]);

  return (
    <>
      <h3>Where the algorithms disagree</h3>
      <p className="muted">
        {rows.length === 0
          ? "All algorithms made identical decisions for this scenario."
          : `${rows.length} job(s) were handled differently. Select one to see each algorithm's reasoning.`}
      </p>
      {rows.length > 0 && (
        <div className="table-scroll">
          <table className="compact">
            <thead>
              <tr>
                <th scope="col">Job</th>
                {results.map((r) => (
                  <th scope="col" key={r.algorithm}><AlgoName name={r.algorithm} /></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ id, outcomes }) => (
                <tr key={id}>
                  <th scope="row">
                    <button type="button" className="link" onClick={() => onSelect({ kind: "request", id })}>{id}</button>
                  </th>
                  {outcomes.map((t, i) => (
                    <td key={results[i].algorithm} className={t ? "" : "unassigned"}>
                      {t ? lookups.techById[t].name : "⊘ none"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export default function DetailPanel({ results, lookups, selection, onSelect }) {
  return (
    <section className="panel detail">
      <div className="detail-header">
        <h2>Decisions</h2>
        {selection && (
          <button type="button" className="ghost" onClick={() => onSelect(null)}>Back to overview</button>
        )}
      </div>
      {selection?.kind === "request" && lookups.reqById[selection.id] ? (
        <RequestDetail id={selection.id} results={results} lookups={lookups} onSelect={onSelect} />
      ) : selection?.kind === "technician" && lookups.techById[selection.id] ? (
        <TechnicianDetail id={selection.id} results={results} lookups={lookups} onSelect={onSelect} />
      ) : (
        <Disagreements results={results} lookups={lookups} onSelect={onSelect} />
      )}
    </section>
  );
}

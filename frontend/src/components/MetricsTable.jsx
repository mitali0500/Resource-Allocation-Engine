import { ALGORITHM_LABELS, useColors } from "../theme.js";

const pct = (v) => `${(v * 100).toFixed(1)}%`;
const num = (d) => (v) => v.toFixed(d);

// better: which direction wins. Ties are all marked best.
const ROWS = [
  { key: "assigned", label: "Jobs assigned", better: "high", fmt: (v, m) => `${v} / ${m.requests_total}` },
  { key: "urgent_assigned_rate", label: "Urgent jobs assigned", better: "high", fmt: pct },
  { key: "total_travel_km", label: "Total travel (km)", better: "low", fmt: num(1) },
  { key: "avg_travel_km", label: "Travel per job (km)", better: "low", fmt: num(2) },
  { key: "total_idle_min", label: "Waiting on site (min)", better: "low", fmt: num(0) },
  { key: "total_cost", label: "Total cost (objective)", better: "low", fmt: num(1), noBar: true, hint: "Sum of the shared cost function (can be negative because of the priority bonus). Lower is better." },
  { key: "jobs_per_tech_stddev", label: "Workload spread (jobs, std dev)", better: "low", fmt: num(2) },
  { key: "utilization", label: "Shift time used", better: "high", fmt: pct },
  { key: "runtime_ms", label: "Runtime (ms)", better: "low", fmt: num(1) },
];

export default function MetricsTable({ results }) {
  const colors = useColors();

  return (
    <section className="panel metrics">
      <h2>Metrics</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {results.map((r) => (
                <th scope="col" key={r.algorithm} className="num">
                  <span className="swatch" style={{ background: colors.algorithm(r.algorithm) }} aria-hidden="true" />
                  {ALGORITHM_LABELS[r.algorithm] ?? r.algorithm}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const values = results.map((r) => r.metrics[row.key]);
              const best = row.better === "high" ? Math.max(...values) : Math.min(...values);
              const allSame = values.every((v) => v === values[0]);
              const maxAbs = Math.max(...values.map(Math.abs)) || 1;
              return (
                <tr key={row.key}>
                  <th scope="row" title={row.hint}>{row.label}</th>
                  {results.map((r, i) => {
                    const v = values[i];
                    const isBest = !allSame && v === best;
                    return (
                      <td key={r.algorithm} className={isBest ? "num best" : "num"}>
                        <span className="cell-value">
                          {isBest && <span className="best-mark" aria-label="best">✓</span>}
                          {row.fmt(v, r.metrics)}
                        </span>
                        {!row.noBar && (
                          <span className="bar-track" aria-hidden="true">
                            <span
                              className="bar"
                              style={{ width: `${(Math.abs(v) / maxAbs) * 100}%`, background: colors.algorithm(r.algorithm) }}
                            />
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="footnote">
        ✓ marks the best value in each row. All three algorithms use the same hard constraints and cost
        function, so differences come only from how they choose.
      </p>
    </section>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { allocate, fetchScenario } from "./api.js";
import { ALGORITHM_ORDER } from "./theme.js";
import Controls from "./components/Controls.jsx";
import AllocationMap, { MapLegend, useMapSync } from "./components/AllocationMap.jsx";
import MetricsTable from "./components/MetricsTable.jsx";
import DetailPanel from "./components/DetailPanel.jsx";

const DEFAULT_PARAMS = { technicians: 10, requests: 40, seed: 42 };
const DEFAULT_CONFIG = {
  speed_kmh: 30,
  defer_cost: 0,
  weights: { travel_km: 1, idle_minute: 0.05, workload: 2, priority_bonus: 15 },
};

export default function App() {
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [scenario, setScenario] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // { kind: "request" | "technician", id }
  const [selection, setSelection] = useState(null);
  const sync = useMapSync();
  const latestCall = useRef(0);

  // Generate a new scenario whenever its size or seed changes
  useEffect(() => {
    const t = setTimeout(() => {
      fetchScenario(params)
        .then((s) => {
          setScenario(s);
          setSelection(null);
        })
        .catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [params]);

  // Re-run every algorithm when the scenario or the cost settings change
  useEffect(() => {
    if (!scenario) return;
    const call = ++latestCall.current;
    setLoading(true);
    const t = setTimeout(() => {
      allocate(scenario, config)
        .then((r) => {
          if (call !== latestCall.current) return; // a newer run superseded this one
          r.sort((a, b) => ALGORITHM_ORDER.indexOf(a.algorithm) - ALGORITHM_ORDER.indexOf(b.algorithm));
          setResults(r);
          setError(null);
        })
        .catch((e) => call === latestCall.current && setError(e.message))
        .finally(() => call === latestCall.current && setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [scenario, config]);

  const lookups = useMemo(() => {
    if (!scenario) return null;
    return {
      techById: Object.fromEntries(scenario.technicians.map((t) => [t.id, t])),
      reqById: Object.fromEntries(scenario.requests.map((r) => [r.id, r])),
    };
  }, [scenario]);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Resource Allocation Engine</h1>
          <p className="subtitle">
            Field-service technicians assigned to repair jobs. One working day, three algorithms, the
            same constraints and cost function.
          </p>
        </div>
      </header>

      <Controls
        params={params}
        setParams={setParams}
        config={config}
        setConfig={setConfig}
        onReset={() => {
          setParams(DEFAULT_PARAMS);
          setConfig(DEFAULT_CONFIG);
        }}
        loading={loading}
      />

      {error && (
        <div className="error" role="alert">
          <strong>Request failed.</strong> {error}. Is the backend running on port 8000?
        </div>
      )}

      {scenario && results.length > 0 && (
        <main className={loading ? "content stale" : "content"}>
          <MapLegend />
          <section className="maps">
            {results.map((r) => (
              <AllocationMap
                key={r.algorithm}
                result={r}
                scenario={scenario}
                lookups={lookups}
                selection={selection}
                onSelect={setSelection}
                sync={sync}
              />
            ))}
          </section>

          <section className="lower">
            <MetricsTable results={results} />
            <DetailPanel
              results={results}
              lookups={lookups}
              selection={selection}
              onSelect={setSelection}
            />
          </section>
        </main>
      )}
    </div>
  );
}

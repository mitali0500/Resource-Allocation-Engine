function NumberField({ label, value, onChange, min, max, step = 1, hint }) {
  return (
    <label className="field" title={hint}>
      <span>{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const v = e.target.valueAsNumber;
          if (!Number.isNaN(v)) onChange(Math.min(max ?? v, Math.max(min ?? v, v)));
        }}
      />
    </label>
  );
}

export default function Controls({ params, setParams, config, setConfig, onReset, loading }) {
  const setParam = (key) => (v) => setParams((p) => ({ ...p, [key]: v }));
  const setWeight = (key) => (v) => setConfig((c) => ({ ...c, weights: { ...c.weights, [key]: v } }));

  return (
    <section className="controls" aria-label="Scenario and cost settings">
      <fieldset>
        <legend>Scenario</legend>
        <NumberField label="Technicians" value={params.technicians} onChange={setParam("technicians")} min={1} max={100} />
        <NumberField label="Jobs" value={params.requests} onChange={setParam("requests")} min={1} max={500} />
        <NumberField label="Seed" value={params.seed} onChange={setParam("seed")} min={0} max={1e6} hint="Same seed, same scenario" />
        <button
          type="button"
          onClick={() => setParams((p) => ({ ...p, seed: Math.floor(Math.random() * 10000) }))}
        >
          New random day
        </button>
      </fieldset>

      <fieldset>
        <legend>Cost weights (soft constraints)</legend>
        <NumberField label="Per km" value={config.weights.travel_km} onChange={setWeight("travel_km")} min={0} step={0.1} />
        <NumberField label="Per idle min" value={config.weights.idle_minute} onChange={setWeight("idle_minute")} min={0} step={0.01} />
        <NumberField label="Per job held" value={config.weights.workload} onChange={setWeight("workload")} min={0} step={0.5} hint="Spreads work across technicians" />
        <NumberField label="Priority bonus" value={config.weights.priority_bonus} onChange={setWeight("priority_bonus")} min={0} step={1} hint="Subtracted per priority level" />
      </fieldset>

      <fieldset>
        <legend>Planning</legend>
        <NumberField label="Speed km/h" value={config.speed_kmh} onChange={(v) => setConfig((c) => ({ ...c, speed_kmh: v }))} min={5} max={120} />
        <NumberField
          label="Defer above cost"
          value={config.defer_cost}
          onChange={(v) => setConfig((c) => ({ ...c, defer_cost: v }))}
          step={5}
          hint="Hungarian + deferral postpones matches costing more than this to a later round"
        />
        <button type="button" className="ghost" onClick={onReset}>Reset</button>
      </fieldset>

      <p className="status" aria-live="polite">{loading ? "Running…" : "Up to date"}</p>
    </section>
  );
}

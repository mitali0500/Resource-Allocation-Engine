async function request(path, options) {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(`${resp.status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  return resp.json();
}

export function fetchScenario({ technicians, requests, seed }) {
  const qs = new URLSearchParams({ technicians, requests, seed });
  return request(`/api/scenario?${qs}`);
}

export function allocate(scenario, config) {
  return request("/api/allocate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario, config }),
  });
}

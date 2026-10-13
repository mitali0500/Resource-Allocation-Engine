import { useEffect, useState } from "react";

// Leaflet draws SVG paths from JS, so map colours live here rather than in CSS.
// Algorithm colours are the first three slots of the validated categorical palette
// (all-pairs safe for colour-vision deficiency in both modes).
const PALETTE = {
  light: {
    algorithms: ["#2a78d6", "#eb6834", "#1baf7a"],
    critical: "#d03b3b",
    ink: "#0b0b0b",
    surface: "#fcfcfb",
  },
  dark: {
    algorithms: ["#3987e5", "#d95926", "#199e70"],
    critical: "#d03b3b",
    ink: "#f0efec",
    surface: "#1a1a19",
  },
};

export const ALGORITHM_LABELS = {
  greedy: "Greedy",
  hungarian: "Hungarian (rounds)",
  hungarian_deferred: "Hungarian + deferral",
};

export const ALGORITHM_ORDER = ["greedy", "hungarian", "hungarian_deferred"];

export function useColors() {
  const query = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = (e) => setDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const p = dark ? PALETTE.dark : PALETTE.light;
  return {
    ...p,
    // Colour follows the algorithm, never its position in the current result list
    algorithm: (name) => p.algorithms[ALGORITHM_ORDER.indexOf(name)] ?? p.ink,
  };
}

export function fmtTime(minutes) {
  const m = Math.round(minutes);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

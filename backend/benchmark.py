"""Compare all algorithms over many random scenarios and print a Markdown table.

    python benchmark.py            # 30 seeds per scenario size
    python benchmark.py --seeds 100
"""

import argparse

from app.algorithms import ALGORITHMS
from app.generator import generate
from app.models import PlanningConfig

SIZES = [(20, 60, "plenty of technicians"), (10, 40, "balanced"), (8, 60, "scarce technicians")]
COLUMNS = [
    ("assigned", "Assigned", "{:.1f}"),
    ("urgent_assigned_rate", "Urgent assigned", "{:.1%}"),
    ("total_travel_km", "Travel km", "{:.0f}"),
    ("total_cost", "Total cost", "{:.0f}"),
    ("jobs_per_tech_stddev", "Load std dev", "{:.2f}"),
    ("runtime_ms", "Runtime ms", "{:.1f}"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    args = parser.parse_args()
    cfg = PlanningConfig()

    print("| Scenario | Algorithm | " + " | ".join(c[1] for c in COLUMNS) + " | More jobs than greedy |")
    print("|---" * (len(COLUMNS) + 3) + "|")
    for n_tech, n_req, label in SIZES:
        totals = {name: dict.fromkeys([c[0] for c in COLUMNS], 0.0) for name in ALGORITHMS}
        wins = dict.fromkeys(ALGORITHMS, 0)
        for seed in range(args.seeds):
            scenario = generate(n_tech, n_req, seed)
            results = {name: fn(scenario, cfg) for name, fn in ALGORITHMS.items()}
            for name, res in results.items():
                for key in totals[name]:
                    totals[name][key] += getattr(res.metrics, key)
                if res.metrics.assigned > results["greedy"].metrics.assigned:
                    wins[name] += 1
        for name in ALGORITHMS:
            cells = [fmt.format(totals[name][key] / args.seeds) for key, _, fmt in COLUMNS]
            beat = "-" if name == "greedy" else f"{wins[name]}/{args.seeds}"
            print(f"| {n_tech} techs / {n_req} jobs ({label}) | {name} | " + " | ".join(cells) + f" | {beat} |")


if __name__ == "__main__":
    main()

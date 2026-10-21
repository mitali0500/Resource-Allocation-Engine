"""Greedy baseline: handle requests one at a time, most urgent first, and give each
the cheapest technician that can still take it. Decisions are never revisited."""

from __future__ import annotations

import time

from ..models import AllocationResult, PlanningConfig, Scenario
from ..scheduling import Option, TechnicianState, evaluate
from .common import build_result, describe_option, make_assignment

NAME = "greedy"


def allocate(scenario: Scenario, cfg: PlanningConfig) -> AllocationResult:
    t0 = time.perf_counter()
    states = [TechnicianState.start_of_day(t) for t in scenario.technicians]
    assignments = []

    # Urgent first, then tightest deadline, then earliest window
    queue = sorted(scenario.requests, key=lambda r: (-r.priority, r.latest_start, r.earliest_start))

    for position, req in enumerate(queue, start=1):
        options = [
            (state, opt) for state in states
            if isinstance(opt := evaluate(state, req, cfg), Option)
        ]
        if not options:
            continue
        options.sort(key=lambda so: so[1].cost)
        state, opt = options[0]

        explanation = (
            f"Processed #{position} in queue (priority {req.priority}). "
            f"Chose {describe_option(state, opt)}, the cheapest of {len(options)} feasible technician(s)"
        )
        if len(options) > 1:
            runner_up, ru_opt = options[1]
            explanation += f"; next best was {runner_up.tech.name} (cost {ru_opt.cost:.1f})"
        assignments.append(make_assignment(state, req, opt, explanation + "."))
        state.commit(req, opt)

    runtime_ms = (time.perf_counter() - t0) * 1000
    return build_result(NAME, scenario, cfg, states, assignments, runtime_ms)

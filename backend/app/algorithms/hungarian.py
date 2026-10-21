"""Hungarian (Kuhn-Munkres) in rounds.

The Hungarian algorithm solves one-to-one matching, but a technician can do several
jobs a day. So we repeat: build a cost matrix of (open requests x technicians in
their current state), solve it optimally, commit every feasible pair, update each
technician's schedule, and go again until a round assigns nothing.
Within a round, every decision is made jointly, so a cheap technician is not used
up on one job if that would strand another job only they can do.

Two variants:
- basic: every round matches as many pairs as possible, so each technician takes a
  job each round even when the only one left for them is a long detour.
- deferred: each request may also be "left for a later round" at cost
  cfg.defer_cost, so poor matches wait until the good ones are placed. When a
  deferral round matches nothing, a basic round runs so no feasible job is dropped.
"""

from __future__ import annotations

import time
from functools import partial

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..models import AllocationResult, PlanningConfig, Scenario
from ..scheduling import Option, TechnicianState, evaluate
from .common import build_result, describe_option, make_assignment

# Stand-in cost for infeasible pairs. Finite (the solver needs a full matching to exist)
# and far larger than any real cost, so it is only chosen when nothing else is possible.
INFEASIBLE = 1e9


def allocate(scenario: Scenario, cfg: PlanningConfig, defer: bool = False) -> AllocationResult:
    t0 = time.perf_counter()
    states = [TechnicianState.start_of_day(t) for t in scenario.technicians]
    open_requests = list(scenario.requests)
    assignments = []
    round_no = 0

    while open_requests and states:
        round_no += 1
        options: dict[tuple[int, int], Option] = {}
        cost = np.full((len(open_requests), len(states)), INFEASIBLE)
        for i, req in enumerate(open_requests):
            for j, state in enumerate(states):
                opt = evaluate(state, req, cfg)
                if isinstance(opt, Option):
                    options[i, j] = opt
                    cost[i, j] = opt.cost

        if not options:
            break

        matched = _solve(cost, options, cfg.defer_cost) if defer else []
        deferred_round = bool(matched)
        if not matched:
            matched = _solve(cost, options, defer_cost=None)
        if not matched:
            break

        matched_tech_of = {j: open_requests[i].id for i, j in matched}
        for i, j in matched:
            req, state, opt = open_requests[i], states[j], options[i, j]
            kind = "batch match" if not defer else (
                "batch match, poor matches deferred" if deferred_round
                else "clean-up match: only higher-cost options remained"
            )
            explanation = (
                f"Round {round_no} {kind} ({len(matched)} pairs solved jointly). "
                f"Assigned {describe_option(state, opt)}"
            )
            best_j = min((jj for (ii, jj) in options if ii == i), key=lambda jj: options[i, jj].cost)
            if best_j != j:
                explanation += (
                    f". Individually cheapest was {states[best_j].tech.name} "
                    f"(cost {options[i, best_j].cost:.1f}), but they went to "
                    f"{matched_tech_of.get(best_j, 'no job this round')} because that lowered the round's total cost"
                )
            assignments.append(make_assignment(state, req, opt, explanation + "."))

        # Commit after building explanations so every pair is described against the same round state
        for i, j in matched:
            states[j].commit(open_requests[i], options[i, j])
        done = {i for i, _ in matched}
        open_requests = [r for k, r in enumerate(open_requests) if k not in done]

    runtime_ms = (time.perf_counter() - t0) * 1000
    name = "hungarian_deferred" if defer else "hungarian"
    return build_result(name, scenario, cfg, states, assignments, runtime_ms)


def _solve(
    cost: np.ndarray, options: dict[tuple[int, int], Option], defer_cost: float | None
) -> list[tuple[int, int]]:
    """Solve one round. With defer_cost, append one dummy column per request
    ("not this round") so the solver can decline any match costing more than that."""
    n_req, n_tech = cost.shape
    if defer_cost is not None:
        dummy = np.full((n_req, n_req), INFEASIBLE)
        np.fill_diagonal(dummy, defer_cost)
        cost = np.hstack([cost, dummy])
    rows, cols = linear_sum_assignment(cost)
    return [(i, j) for i, j in zip(rows, cols) if j < n_tech and (i, j) in options]


allocate_basic = partial(allocate, defer=False)
allocate_deferred = partial(allocate, defer=True)

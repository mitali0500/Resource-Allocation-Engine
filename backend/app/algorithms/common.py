"""Pieces every algorithm shares: result assembly, metrics and unassigned-reason diagnosis."""

from __future__ import annotations

from collections import Counter

import numpy as np

from ..models import (
    AllocationResult,
    Assignment,
    Metrics,
    PlanningConfig,
    Request,
    Scenario,
    Unassigned,
)
from ..scheduling import Infeasible, Option, TechnicianState, evaluate, fmt_time


def make_assignment(state: TechnicianState, req: Request, opt: Option, explanation: str) -> Assignment:
    return Assignment(
        request_id=req.id,
        technician_id=state.tech.id,
        start=opt.start,
        end=opt.end,
        travel_km=round(opt.travel_km, 3),
        travel_min=round(opt.travel_min, 2),
        idle_min=round(opt.idle_min, 2),
        cost=round(opt.cost, 3),
        explanation=explanation,
    )


def describe_option(state: TechnicianState, opt: Option) -> str:
    return (
        f"{state.tech.name} (adds {opt.travel_km:.1f} km to route, starts {fmt_time(opt.start)}, "
        f"cost {opt.cost:.1f})"
    )


def unassigned_reason(req: Request, scenario: Scenario, cfg: PlanningConfig) -> str:
    """Distinguish 'impossible from the start' from 'possible, but capacity ran out'."""
    qualified = [t for t in scenario.technicians if req.required_skills <= t.skills]
    if not qualified:
        return f"no technician has the required skill(s): {', '.join(sorted(req.required_skills))}"

    fresh = [(t, evaluate(TechnicianState.start_of_day(t), req, cfg)) for t in qualified]
    reachable = [t.name for t, r in fresh if isinstance(r, Option)]
    if reachable:
        names = ", ".join(reachable)
        return f"capacity: qualified technicians who could have reached it ({names}) were booked on other jobs"

    reasons = Counter(
        "cannot arrive before SLA deadline" if "SLA" in r.reason else "would overrun shift"
        for _, r in fresh
        if isinstance(r, Infeasible)
    )
    summary = "; ".join(f"{n} {why}" for why, n in reasons.most_common())
    return f"{len(qualified)} qualified technician(s), none feasible even on an empty schedule: {summary}"


def build_result(
    algorithm: str,
    scenario: Scenario,
    cfg: PlanningConfig,
    states: list[TechnicianState],
    assignments: list[Assignment],
    runtime_ms: float,
) -> AllocationResult:
    assigned_ids = {a.request_id for a in assignments}
    unassigned = [
        Unassigned(request_id=r.id, reason=unassigned_reason(r, scenario, cfg))
        for r in scenario.requests
        if r.id not in assigned_ids
    ]
    return AllocationResult(
        algorithm=algorithm,
        assignments=sorted(assignments, key=lambda a: (a.technician_id, a.start)),
        unassigned=unassigned,
        metrics=compute_metrics(scenario, states, assignments, runtime_ms),
    )


def compute_metrics(
    scenario: Scenario, states: list[TechnicianState], assignments: list[Assignment], runtime_ms: float
) -> Metrics:
    n_req = len(scenario.requests)
    n_assigned = len(assignments)
    assigned_ids = {a.request_id for a in assignments}
    urgent = [r for r in scenario.requests if r.priority == 3]
    urgent_done = sum(r.id in assigned_ids for r in urgent)
    travel = sum(a.travel_km for a in assignments)
    shift_total = sum(s.tech.shift_end - s.tech.shift_start for s in states)
    busy_total = sum(s.busy_min for s in states)

    return Metrics(
        requests_total=n_req,
        assigned=n_assigned,
        assignment_rate=round(n_assigned / n_req, 4) if n_req else 1.0,
        urgent_assigned_rate=round(urgent_done / len(urgent), 4) if urgent else 1.0,
        total_travel_km=round(travel, 2),
        avg_travel_km=round(travel / n_assigned, 2) if n_assigned else 0.0,
        total_idle_min=round(sum(a.idle_min for a in assignments), 1),
        total_cost=round(sum(a.cost for a in assignments), 2),
        jobs_per_tech_stddev=round(float(np.std([len(s.job_ids) for s in states])), 3) if states else 0.0,
        utilization=round(busy_total / shift_total, 4) if shift_total else 0.0,
        runtime_ms=round(runtime_ms, 2),
    )

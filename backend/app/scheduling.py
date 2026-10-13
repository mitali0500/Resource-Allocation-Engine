"""Shared feasibility check and cost function.

Every algorithm asks the same question: "can this technician, given the jobs they
already have, fit this request into their day, and what would it cost?"
Keeping that logic here guarantees algorithms differ only in *how they choose*,
never in what they consider feasible or cheap.

A request can be inserted into any gap of a technician's schedule, not only
appended at the end. Otherwise the order in which an algorithm happens to commit
jobs (e.g. an urgent 15:00 job first) would wipe out the technician's morning.
Jobs already scheduled keep their start times; an insertion is only feasible if
the technician can still reach the next job on time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geo import haversine_km, travel_minutes
from .models import Location, PlanningConfig, Request, Technician


@dataclass(frozen=True)
class ScheduledJob:
    request: Request
    start: float
    end: float


@dataclass
class TechnicianState:
    """Mutable planning state. The Technician itself is never modified."""

    tech: Technician
    jobs: list[ScheduledJob] = field(default_factory=list)  # ordered by start
    route_km: float = 0.0
    travel_min: float = 0.0

    @classmethod
    def start_of_day(cls, tech: Technician) -> TechnicianState:
        return cls(tech=tech)

    @property
    def job_ids(self) -> list[str]:
        return [j.request.id for j in self.jobs]

    @property
    def busy_min(self) -> float:
        """Minutes spent driving or on site."""
        return sum(j.request.duration for j in self.jobs) + self.travel_min

    def commit(self, req: Request, option: Option) -> None:
        self.jobs.insert(option.position, ScheduledJob(req, option.start, option.end))
        self.route_km += option.travel_km
        self.travel_min += option.travel_min


@dataclass(frozen=True)
class Option:
    """A feasible way to fit a request into a technician's schedule."""

    position: int       # index in the technician's job list where the request goes
    start: float
    end: float
    travel_km: float    # extra km this job adds to the route (detour)
    travel_min: float
    idle_min: float     # waiting on site before the window opens
    cost: float


@dataclass(frozen=True)
class Infeasible:
    reason: str


def evaluate(state: TechnicianState, req: Request, cfg: PlanningConfig) -> Option | Infeasible:
    """Check the hard constraints for every gap, then return the cheapest feasible insertion."""
    tech = state.tech

    missing = req.required_skills - tech.skills
    if missing:
        return Infeasible(f"missing skill(s): {', '.join(sorted(missing))}")

    best: Option | None = None
    first_failure: str | None = None
    for pos in range(len(state.jobs) + 1):
        result = _try_gap(state, req, pos, cfg)
        if isinstance(result, Infeasible):
            first_failure = first_failure or result.reason
        elif best is None or result.cost < best.cost:
            best = result

    if best is not None:
        return best
    if len(state.jobs) == 0:
        return Infeasible(first_failure or "no feasible slot")
    return Infeasible(f"no gap in schedule fits ({len(state.jobs)} job(s) already booked)")


def _try_gap(state: TechnicianState, req: Request, pos: int, cfg: PlanningConfig) -> Option | Infeasible:
    tech = state.tech
    prev = state.jobs[pos - 1] if pos > 0 else None
    nxt = state.jobs[pos] if pos < len(state.jobs) else None

    from_loc: Location = prev.request.location if prev else tech.home
    free_at = prev.end if prev else tech.shift_start

    km_in = haversine_km(from_loc, req.location)
    arrival = free_at + travel_minutes(km_in, cfg.speed_kmh)
    start = max(arrival, req.earliest_start)

    if start > req.latest_start:
        return Infeasible(
            f"earliest arrival {fmt_time(arrival)} is after SLA deadline {fmt_time(req.latest_start)}"
        )
    end = start + req.duration
    if end > tech.shift_end:
        return Infeasible(f"job would end {fmt_time(end)}, after shift end {fmt_time(tech.shift_end)}")

    detour_km = km_in
    if nxt is not None:
        km_out = haversine_km(req.location, nxt.request.location)
        if end + travel_minutes(km_out, cfg.speed_kmh) > nxt.start:
            return Infeasible(f"would make the technician late for {nxt.request.id}")
        detour_km += km_out - haversine_km(from_loc, nxt.request.location)

    idle = start - arrival
    w = cfg.weights
    cost = (
        w.travel_km * detour_km
        + w.idle_minute * idle
        + w.workload * len(state.jobs)
        - w.priority_bonus * req.priority
    )
    return Option(
        position=pos,
        start=start,
        end=end,
        travel_km=detour_km,
        travel_min=travel_minutes(detour_km, cfg.speed_kmh),
        idle_min=idle,
        cost=cost,
    )


def fmt_time(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60:02d}:{m % 60:02d}"

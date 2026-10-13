"""Domain model for field-service allocation.

Times are minutes since midnight of the planning day (e.g. 540 = 09:00),
which keeps the scheduling arithmetic simple and avoids timezone handling.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Location(BaseModel):
    lat: float
    lon: float


class Technician(BaseModel):
    """A mobile resource that can perform several jobs in sequence during its shift."""

    id: str
    name: str
    skills: set[str]
    home: Location
    shift_start: int = Field(ge=0, le=24 * 60)
    shift_end: int = Field(ge=0, le=24 * 60)

    @model_validator(mode="after")
    def _shift_order(self) -> Technician:
        if self.shift_end <= self.shift_start:
            raise ValueError("shift_end must be after shift_start")
        return self


class Request(BaseModel):
    """A repair job. The technician must *start* inside [earliest_start, latest_start];
    latest_start is the SLA deadline."""

    id: str
    location: Location
    required_skills: set[str]
    duration: int = Field(gt=0, description="Minutes on site")
    earliest_start: int = Field(ge=0, le=24 * 60)
    latest_start: int = Field(ge=0, le=24 * 60)
    priority: int = Field(default=2, ge=1, le=3, description="1 = low, 3 = urgent")

    @model_validator(mode="after")
    def _window_order(self) -> Request:
        if self.latest_start < self.earliest_start:
            raise ValueError("latest_start must not be before earliest_start")
        return self


class Scenario(BaseModel):
    technicians: list[Technician]
    requests: list[Request]


class CostWeights(BaseModel):
    """Weights of the soft constraints. Shared by every algorithm so comparisons are fair."""

    travel_km: float = 1.0          # per km driven to the job
    idle_minute: float = 0.05       # per minute a technician waits for the window to open
    workload: float = 2.0           # per job the technician already has (balances load)
    priority_bonus: float = 15.0    # subtracted per priority level, so urgent jobs win scarce technicians


class PlanningConfig(BaseModel):
    speed_kmh: float = Field(default=30.0, gt=0, description="Average urban driving speed")
    weights: CostWeights = Field(default_factory=CostWeights)
    defer_cost: float = Field(
        default=0.0,
        description="hungarian_deferred only: a round leaves a request for later rather than "
        "accept a match costing more than this",
    )


class Assignment(BaseModel):
    request_id: str
    technician_id: str
    start: float
    end: float
    travel_km: float
    travel_min: float
    idle_min: float
    cost: float
    explanation: str


class Unassigned(BaseModel):
    request_id: str
    reason: str


class Metrics(BaseModel):
    requests_total: int
    assigned: int
    assignment_rate: float
    urgent_assigned_rate: float
    total_travel_km: float
    avg_travel_km: float
    total_idle_min: float
    total_cost: float
    jobs_per_tech_stddev: float
    utilization: float = Field(description="Share of paid shift time spent on jobs or travel")
    runtime_ms: float


class AllocationResult(BaseModel):
    algorithm: str
    assignments: list[Assignment]
    unassigned: list[Unassigned]
    metrics: Metrics

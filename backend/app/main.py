from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .algorithms import ALGORITHMS
from .generator import generate
from .models import AllocationResult, PlanningConfig, Scenario

app = FastAPI(title="Resource Allocation Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


class AllocateRequest(BaseModel):
    scenario: Scenario
    config: PlanningConfig = Field(default_factory=PlanningConfig)
    algorithms: list[str] = Field(default_factory=lambda: list(ALGORITHMS))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/algorithms")
def algorithms() -> list[str]:
    return list(ALGORITHMS)


@app.get("/api/scenario", response_model=Scenario)
def scenario(
    technicians: int = Query(10, ge=1, le=100),
    requests: int = Query(40, ge=1, le=500),
    seed: int = 42,
) -> Scenario:
    return generate(technicians, requests, seed)


@app.post("/api/allocate", response_model=list[AllocationResult])
def allocate(body: AllocateRequest) -> list[AllocationResult]:
    unknown = [a for a in body.algorithms if a not in ALGORITHMS]
    if unknown:
        raise HTTPException(400, f"unknown algorithm(s): {', '.join(unknown)}; choose from {list(ALGORITHMS)}")
    return [ALGORITHMS[name](body.scenario, body.config) for name in body.algorithms]

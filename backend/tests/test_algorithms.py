"""Correctness checks for every algorithm, plus scenarios that show where they differ.

The validity checker below re-derives the hard constraints from the raw data
instead of calling scheduling.evaluate, so a bug there would not hide itself.
"""

import pytest
from fastapi.testclient import TestClient

from app.algorithms import ALGORITHMS, greedy, hungarian
from app.generator import generate
from app.geo import haversine_km, travel_minutes
from app.main import app
from app.models import AllocationResult, Location, PlanningConfig, Request, Scenario, Technician

CFG = PlanningConfig()
EPS = 1e-6


def assert_valid(result: AllocationResult, scenario: Scenario, cfg: PlanningConfig = CFG) -> None:
    techs = {t.id: t for t in scenario.technicians}
    reqs = {r.id: r for r in scenario.requests}

    assigned = [a.request_id for a in result.assignments]
    unassigned = [u.request_id for u in result.unassigned]
    assert len(assigned) == len(set(assigned)), "a request was assigned twice"
    assert sorted(assigned + unassigned) == sorted(reqs), "every request is assigned or explained exactly once"

    for tech_id in techs:
        tech = techs[tech_id]
        jobs = sorted((a for a in result.assignments if a.technician_id == tech_id), key=lambda a: a.start)
        loc, free_at = tech.home, tech.shift_start
        for a in jobs:
            r = reqs[a.request_id]
            assert r.required_skills <= tech.skills, f"{tech.id} lacks skills for {r.id}"
            assert r.earliest_start - EPS <= a.start <= r.latest_start + EPS, f"{r.id} starts outside SLA window"
            assert a.end == pytest.approx(a.start + r.duration)
            assert a.end <= tech.shift_end + EPS, f"{r.id} overruns {tech.id}'s shift"
            arrival = free_at + travel_minutes(haversine_km(loc, r.location), cfg.speed_kmh)
            assert a.start >= arrival - EPS, f"{tech.id} cannot physically reach {r.id} in time"
            loc, free_at = r.location, a.end


@pytest.mark.parametrize("algorithm", list(ALGORITHMS))
@pytest.mark.parametrize("n_tech,n_req", [(10, 40), (5, 60), (25, 30)])
@pytest.mark.parametrize("seed", range(8))
def test_all_hard_constraints_hold(algorithm, n_tech, n_req, seed):
    scenario = generate(n_tech, n_req, seed)
    assert_valid(ALGORITHMS[algorithm](scenario, CFG), scenario)


@pytest.mark.parametrize("algorithm", list(ALGORITHMS))
def test_deterministic(algorithm):
    scenario = generate(10, 40, seed=3)
    a = ALGORITHMS[algorithm](scenario, CFG)
    b = ALGORITHMS[algorithm](scenario, CFG)
    assert a.assignments == b.assignments


# --- Hand-built scenarios ---------------------------------------------------

BASE = Location(lat=12.97, lon=77.59)


def km_east(km: float) -> Location:
    return Location(lat=BASE.lat, lon=BASE.lon + km / 108.5)  # ~108.5 km per degree of longitude here


def tech(id, skills, home, start=540, end=1020):
    return Technician(id=id, name=id, skills=set(skills), home=home, shift_start=start, shift_end=end)


def job(id, skills, loc, earliest=540, latest=560, duration=60, priority=2):
    return Request(
        id=id, location=loc, required_skills=set(skills), duration=duration,
        earliest_start=earliest, latest_start=latest, priority=priority,
    )


def contention_scenario() -> Scenario:
    """Ana is the only HVAC technician and is also the closest electrician.
    Both jobs need someone at 09:00-09:20, so Ana can only do one of them."""
    return Scenario(
        technicians=[
            tech("Ana", {"electrical", "hvac"}, BASE),
            tech("Ben", {"electrical"}, km_east(3)),
        ],
        requests=[
            job("ELEC", {"electrical"}, km_east(1), priority=3),  # urgent: greedy handles it first
            job("HVAC", {"hvac"}, km_east(-1), priority=2),
        ],
    )


def test_greedy_strands_job_when_it_uses_scarce_skill_first():
    scenario = contention_scenario()
    result = greedy.allocate(scenario, CFG)
    assert_valid(result, scenario)
    assert {a.request_id: a.technician_id for a in result.assignments} == {"ELEC": "Ana"}
    assert "capacity" in result.unassigned[0].reason


def test_hungarian_sees_the_conflict_and_serves_both():
    scenario = contention_scenario()
    result = hungarian.allocate(scenario, CFG)
    assert_valid(result, scenario)
    assert {a.request_id: a.technician_id for a in result.assignments} == {"ELEC": "Ben", "HVAC": "Ana"}
    # The explanation says why the individually cheapest technician was not used
    elec = next(a for a in result.assignments if a.request_id == "ELEC")
    assert "Individually cheapest was Ana" in elec.explanation


def detour_scenario() -> Scenario:
    """Two jobs near Ana, none near Ben. Ana can do both in sequence."""
    return Scenario(
        technicians=[tech("Ana", {"electrical"}, BASE), tech("Ben", {"electrical"}, km_east(30))],
        requests=[
            job("MORNING", {"electrical"}, km_east(1), earliest=540, latest=600, priority=1),
            job("LATER", {"electrical"}, km_east(2), earliest=660, latest=720, priority=1),
        ],
    )


def test_basic_hungarian_forces_a_long_detour():
    # Round 1 must give both technicians a job, so Ben drives ~28 km to LATER
    result = hungarian.allocate_basic(detour_scenario(), CFG)
    assert {a.request_id: a.technician_id for a in result.assignments} == {"MORNING": "Ana", "LATER": "Ben"}
    assert result.metrics.total_travel_km > 25


def test_deferred_hungarian_waits_and_gives_both_to_ana():
    scenario = detour_scenario()
    result = hungarian.allocate_deferred(scenario, CFG)
    assert_valid(result, scenario)
    assert {a.request_id: a.technician_id for a in result.assignments} == {"MORNING": "Ana", "LATER": "Ana"}
    assert result.metrics.total_travel_km == pytest.approx(2, abs=0.05)
    later = next(a for a in result.assignments if a.request_id == "LATER")
    assert "Round 2" in later.explanation


def test_deferral_never_drops_feasible_jobs():
    # Even if every match is "too expensive", clean-up rounds still assign everything feasible
    scenario = generate(10, 40, seed=5)
    strict = PlanningConfig(defer_cost=-1000)
    assert (
        hungarian.allocate_deferred(scenario, strict).metrics.assigned
        == hungarian.allocate_basic(scenario, strict).metrics.assigned
    )


def test_both_agree_when_there_is_no_contention():
    scenario = Scenario(
        technicians=[tech("Ana", {"electrical"}, BASE), tech("Ben", {"hvac"}, km_east(10))],
        requests=[job("E", {"electrical"}, km_east(1)), job("H", {"hvac"}, km_east(11))],
    )
    g, h = greedy.allocate(scenario, CFG), hungarian.allocate(scenario, CFG)
    pairs = lambda r: {(a.request_id, a.technician_id) for a in r.assignments}
    assert pairs(g) == pairs(h) == {("E", "Ana"), ("H", "Ben")}
    assert g.metrics.total_cost == pytest.approx(h.metrics.total_cost)


@pytest.mark.parametrize("algorithm", list(ALGORITHMS))
def test_unassigned_reasons_are_specific(algorithm):
    scenario = Scenario(
        technicians=[tech("Ana", {"electrical"}, BASE, start=540, end=600)],
        requests=[
            job("NOSKILL", {"plumbing"}, BASE),
            job("TOOFAR", {"electrical"}, km_east(30), latest=545),   # 60 min drive, deadline 09:05
            job("TOOLATE", {"electrical"}, BASE, earliest=580, latest=590),  # would end after 10:00 shift end
        ],
    )
    reasons = {u.request_id: u.reason for u in ALGORITHMS[algorithm](scenario, CFG).unassigned}
    assert "no technician has" in reasons["NOSKILL"]
    assert "SLA deadline" in reasons["TOOFAR"]
    assert "overrun shift" in reasons["TOOLATE"]


@pytest.mark.parametrize("algorithm", list(ALGORITHMS))
def test_technician_does_several_jobs_in_a_day(algorithm):
    scenario = Scenario(
        technicians=[tech("Ana", {"electrical"}, BASE)],
        requests=[job(f"J{h}", {"electrical"}, km_east(h), earliest=h * 60, latest=h * 60 + 30)
                  for h in (9, 11, 13, 15)],
    )
    result = ALGORITHMS[algorithm](scenario, CFG)
    assert_valid(result, scenario)
    assert result.metrics.assigned == 4


def test_metrics():
    scenario = contention_scenario()
    m = hungarian.allocate(scenario, CFG).metrics
    assert m.assigned == 2 and m.assignment_rate == 1.0 and m.urgent_assigned_rate == 1.0
    assert m.total_travel_km == pytest.approx(1 + 2, abs=0.05)  # Ana 1 km west, Ben 2 km back west
    assert m.jobs_per_tech_stddev == 0


# --- API ------------------------------------------------------------------------

client = TestClient(app)


def test_api_allocate_runs_all_algorithms():
    scenario = client.get("/api/scenario", params={"technicians": 5, "requests": 15, "seed": 1}).json()
    resp = client.post("/api/allocate", json={"scenario": scenario})
    assert resp.status_code == 200
    assert [r["algorithm"] for r in resp.json()] == list(ALGORITHMS)


def test_api_rejects_unknown_algorithm():
    scenario = client.get("/api/scenario", params={"technicians": 2, "requests": 2}).json()
    resp = client.post("/api/allocate", json={"scenario": scenario, "algorithms": ["magic"]})
    assert resp.status_code == 400

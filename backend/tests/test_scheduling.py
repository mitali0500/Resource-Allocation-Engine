import pytest
from pydantic import ValidationError

from app.generator import generate
from app.models import Location, PlanningConfig, Request, Technician
from app.scheduling import Infeasible, Option, TechnicianState, evaluate

HOME = Location(lat=12.97, lon=77.59)
# ~0.09 degrees of latitude is ~10 km, i.e. 20 min at 30 km/h
TEN_KM_NORTH = Location(lat=12.97 + 10 / 111.19, lon=77.59)
CFG = PlanningConfig()


def tech(**kw) -> Technician:
    base = dict(id="T1", name="Asha", skills={"electrical"}, home=HOME, shift_start=540, shift_end=1020)
    return Technician(**(base | kw))


def req(**kw) -> Request:
    base = dict(
        id="R1", location=TEN_KM_NORTH, required_skills={"electrical"},
        duration=60, earliest_start=540, latest_start=660,
    )
    return Request(**(base | kw))


def test_feasible_job_starts_after_travel():
    opt = evaluate(TechnicianState.start_of_day(tech()), req(), CFG)
    assert isinstance(opt, Option)
    assert opt.travel_km == pytest.approx(10, abs=0.05)
    assert opt.start == pytest.approx(540 + 20, abs=0.2)
    assert opt.idle_min == 0


def test_technician_waits_for_window_to_open():
    opt = evaluate(TechnicianState.start_of_day(tech()), req(earliest_start=600, latest_start=700), CFG)
    assert isinstance(opt, Option)
    assert opt.start == 600
    assert opt.idle_min == pytest.approx(40, abs=0.2)


def test_missing_skill_is_infeasible():
    res = evaluate(TechnicianState.start_of_day(tech(skills={"hvac"})), req(), CFG)
    assert isinstance(res, Infeasible) and "missing skill" in res.reason


def test_needs_all_required_skills():
    res = evaluate(TechnicianState.start_of_day(tech()), req(required_skills={"electrical", "hvac"}), CFG)
    assert isinstance(res, Infeasible) and "hvac" in res.reason


def test_cannot_reach_before_sla_deadline():
    # Available at 09:00 but needs 20 min to drive; deadline is 09:10
    res = evaluate(TechnicianState.start_of_day(tech()), req(latest_start=550), CFG)
    assert isinstance(res, Infeasible) and "SLA" in res.reason


def test_job_cannot_overrun_shift():
    res = evaluate(TechnicianState.start_of_day(tech(shift_end=600)), req(), CFG)
    assert isinstance(res, Infeasible) and "shift end" in res.reason


def test_commit_blocks_time():
    state = TechnicianState.start_of_day(tech())
    opt = evaluate(state, req(), CFG)
    state.commit(req(), opt)
    assert state.job_ids == ["R1"]
    # Busy 09:20-10:20 at that site: a second job there with a 10:00 deadline no longer fits
    res = evaluate(state, req(id="R2", earliest_start=540, latest_start=600), CFG)
    assert isinstance(res, Infeasible) and "no gap" in res.reason


def test_next_job_continues_from_previous_site():
    state = TechnicianState.start_of_day(tech())
    first = evaluate(state, req(), CFG)
    state.commit(req(), first)
    # Same site, window open after the first job ends: no extra driving
    second = evaluate(state, req(id="R2", earliest_start=600, latest_start=720), CFG)
    assert isinstance(second, Option)
    assert second.position == 1
    assert second.travel_km == pytest.approx(0, abs=1e-6)
    assert second.start == pytest.approx(first.end)


def test_job_can_be_inserted_before_a_later_job():
    state = TechnicianState.start_of_day(tech())
    afternoon = req(id="PM", earliest_start=840, latest_start=900)
    state.commit(afternoon, evaluate(state, afternoon, CFG))
    # A morning job committed *after* the afternoon one still fits in front of it
    morning = evaluate(state, req(id="AM", earliest_start=540, latest_start=600), CFG)
    assert isinstance(morning, Option)
    assert morning.position == 0
    assert morning.end <= 840


def test_insertion_rejected_if_it_makes_next_job_late():
    state = TechnicianState.start_of_day(tech())
    fixed = req(id="FIXED", location=HOME, earliest_start=600, latest_start=600)
    state.commit(fixed, evaluate(state, fixed, CFG))
    # 60 min job 10 km away, ending 10:20 at the earliest: can't be back home for 10:00
    res = evaluate(state, req(id="NEW", earliest_start=540, latest_start=560), CFG)
    assert isinstance(res, Infeasible)


def test_urgent_requests_are_cheaper():
    state = TechnicianState.start_of_day(tech())
    low = evaluate(state, req(priority=1), CFG)
    urgent = evaluate(state, req(priority=3), CFG)
    assert urgent.cost < low.cost


def test_invalid_windows_are_rejected():
    with pytest.raises(ValidationError):
        req(earliest_start=700, latest_start=600)
    with pytest.raises(ValidationError):
        tech(shift_start=600, shift_end=600)


def test_generator_is_reproducible():
    assert generate(5, 20, seed=7) == generate(5, 20, seed=7)
    assert generate(5, 20, seed=7) != generate(5, 20, seed=8)

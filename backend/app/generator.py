"""Reproducible synthetic scenarios (the same seed always gives the same scenario)."""

from __future__ import annotations

import random

from .models import Location, Request, Scenario, Technician

# Central Bengaluru, roughly 25 km x 25 km
LAT_RANGE = (12.86, 13.08)
LON_RANGE = (77.48, 77.70)

SKILLS = ["electrical", "hvac", "plumbing", "appliance", "networking"]
SHIFTS = [(8 * 60, 16 * 60), (9 * 60, 17 * 60), (10 * 60, 18 * 60)]
NAMES = [
    "Asha", "Rahul", "Priya", "Vikram", "Meera", "Arjun", "Kavya", "Rohan",
    "Sneha", "Karan", "Divya", "Aditya", "Neha", "Sanjay", "Pooja", "Imran",
    "Lakshmi", "Nikhil", "Ananya", "Farhan",
]
# Urgent jobs get tight SLA windows, low-priority jobs loose ones (minutes)
WINDOW_BY_PRIORITY = {3: (45, 90), 2: (120, 240), 1: (240, 480)}


def _location(rng: random.Random) -> Location:
    return Location(lat=round(rng.uniform(*LAT_RANGE), 5), lon=round(rng.uniform(*LON_RANGE), 5))


def generate(n_technicians: int = 10, n_requests: int = 40, seed: int = 42) -> Scenario:
    rng = random.Random(seed)

    technicians = []
    for i in range(n_technicians):
        start, end = rng.choice(SHIFTS)
        technicians.append(
            Technician(
                id=f"T{i + 1:02d}",
                name=NAMES[i % len(NAMES)] + ("" if i < len(NAMES) else f" {i // len(NAMES) + 1}"),
                skills=set(rng.sample(SKILLS, k=rng.choice([1, 2, 2, 3]))),
                home=_location(rng),
                shift_start=start,
                shift_end=end,
            )
        )

    requests = []
    for i in range(n_requests):
        priority = rng.choices([1, 2, 3], weights=[3, 5, 2])[0]
        earliest = rng.randrange(8 * 60, 16 * 60, 15)
        lo, hi = WINDOW_BY_PRIORITY[priority]
        latest = min(earliest + rng.randrange(lo, hi + 1, 15), 17 * 60)
        requests.append(
            Request(
                id=f"R{i + 1:03d}",
                location=_location(rng),
                required_skills=set(rng.sample(SKILLS, k=2 if rng.random() < 0.1 else 1)),
                duration=rng.randrange(30, 121, 15),
                earliest_start=earliest,
                latest_start=max(latest, earliest),
                priority=priority,
            )
        )

    return Scenario(technicians=technicians, requests=requests)

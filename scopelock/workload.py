"""Deterministic approval-queue capacity rehearsal."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import heapq
import math
import random


@dataclass(frozen=True)
class WorkloadScenario:
    name: str
    arrivals_per_hour: float
    service_minutes: float
    approvers: int
    duration_hours: float
    patience_minutes: float
    p95_sla_minutes: float
    max_abandonment_rate: float

    def validate(self) -> None:
        positive = {
            "arrivals_per_hour": self.arrivals_per_hour,
            "service_minutes": self.service_minutes,
            "duration_hours": self.duration_hours,
            "patience_minutes": self.patience_minutes,
            "p95_sla_minutes": self.p95_sla_minutes,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if isinstance(self.approvers, bool) or not isinstance(self.approvers, int) or self.approvers < 1:
            raise ValueError("approvers must be a positive integer")
        if not 0 <= self.max_abandonment_rate <= 1:
            raise ValueError("max_abandonment_rate must be between 0 and 1")


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 6)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 6)


def simulate_approval_queue(scenario: WorkloadScenario, *, seed: int) -> dict:
    """Simulate a seeded FCFS queue without external services or credentials."""
    scenario.validate()
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    rng = random.Random(seed)
    horizon = scenario.duration_hours * 60
    next_arrival = 0.0
    arrivals: list[float] = []
    while True:
        next_arrival += rng.expovariate(scenario.arrivals_per_hour / 60)
        if next_arrival > horizon:
            break
        arrivals.append(next_arrival)

    available = [0.0 for _ in range(scenario.approvers)]
    heapq.heapify(available)
    offered_waits: list[float] = []
    served_waits: list[float] = []
    service_times: list[float] = []
    abandoned = 0
    busy_within_horizon = 0.0
    for arrival in arrivals:
        earliest = heapq.heappop(available)
        start = max(arrival, earliest)
        wait = start - arrival
        offered_waits.append(wait)
        if wait > scenario.patience_minutes:
            abandoned += 1
            heapq.heappush(available, earliest)
            continue
        service = rng.expovariate(1 / scenario.service_minutes)
        end = start + service
        served_waits.append(wait)
        service_times.append(service)
        busy_within_horizon += max(0.0, min(end, horizon) - start)
        heapq.heappush(available, end)

    total = len(arrivals)
    abandonment_rate = abandoned / total if total else 0.0
    offered_p95 = _percentile(offered_waits, .95)
    accepted = (
        (offered_p95 or 0.0) <= scenario.p95_sla_minutes
        and abandonment_rate <= scenario.max_abandonment_rate
    )
    return {
        "scenario": scenario.name,
        "assumptions": asdict(scenario),
        "seed": seed,
        "arrivals": total,
        "served": len(served_waits),
        "abandoned": abandoned,
        "abandonment_rate": round(abandonment_rate, 6),
        "offered_wait_p50_minutes": _percentile(offered_waits, .5),
        "offered_wait_p95_minutes": offered_p95,
        "served_wait_p95_minutes": _percentile(served_waits, .95),
        "mean_service_minutes": round(sum(service_times) / len(service_times), 6) if service_times else None,
        "utilization": round(busy_within_horizon / (horizon * scenario.approvers), 6),
        "accepted": accepted,
        "breaches": [
            name for name, breached in (
                ("p95_wait_sla", (offered_p95 or 0.0) > scenario.p95_sla_minutes),
                ("abandonment_budget", abandonment_rate > scenario.max_abandonment_rate),
            ) if breached
        ],
    }


def approval_workload_budget(
    scenarios: list[WorkloadScenario],
    *,
    seed: int = 2606,
    service_time_multipliers: tuple[float, ...] = (.75, 1.0, 1.25, 1.5),
) -> dict:
    """Gate a rollout and expose sensitivity to service-time assumptions."""
    if not scenarios:
        raise ValueError("at least one workload scenario is required")
    names = [scenario.name for scenario in scenarios]
    if len(names) != len(set(names)):
        raise ValueError("scenario names must be unique")
    if not service_time_multipliers or any(
        not math.isfinite(item) or item <= 0 for item in service_time_multipliers
    ):
        raise ValueError("service_time_multipliers must be finite and positive")

    results = [
        simulate_approval_queue(scenario, seed=seed + index)
        for index, scenario in enumerate(scenarios)
    ]
    sensitivity = []
    for multiplier in service_time_multipliers:
        rows = [
            simulate_approval_queue(
                replace(
                    scenario,
                    name=f"{scenario.name}@{multiplier:g}x",
                    service_minutes=scenario.service_minutes * multiplier,
                ),
                seed=seed + index,
            )
            for index, scenario in enumerate(scenarios)
        ]
        sensitivity.append({
            "service_time_multiplier": multiplier,
            "all_scenarios_accepted": all(row["accepted"] for row in rows),
            "scenarios": rows,
        })

    failed = [row["scenario"] for row in results if not row["accepted"]]
    return {
        "recommendation": "promote" if not failed else "block",
        "failed_scenarios": failed,
        "scenarios": results,
        "sensitivity": sensitivity,
        "limitations": [
            "Arrival and service distributions are seeded synthetic assumptions.",
            "The model omits priority classes, shift changes, outages, and reviewer accuracy.",
            "A queue-SLA pass is not evidence that the underlying approvals are correct.",
        ],
    }


def default_workload_budget() -> dict:
    """Reproducible base and surge fixture used by the demo and CI."""
    return approval_workload_budget([
        WorkloadScenario("base", 6, 6, 2, 8, 20, 10, .05),
        WorkloadScenario("surge", 18, 6, 2, 8, 20, 10, .05),
    ])

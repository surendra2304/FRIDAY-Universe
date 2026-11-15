#!/usr/bin/env python3
"""Generator for the synthetic 5-minute telemetry evaluation series.

This series is SYNTHETIC — it is not measured data and must never be
presented as such (Futuris evidence vocabulary: ``EvidenceClass.SYNTHETIC``).
It exists so the walk-forward evaluation harness can exercise the exact
operating shape of Futuris's production targets — non-negative 5-minute
service telemetry with a strong daily cycle (season length 288) — alongside
the two real, provenanced series in this directory. See PROVENANCE.json.

The generator is deterministic: ``numpy.random.default_rng(42)`` (PCG64).
Regenerating with the same seed reproduces ``synthetic_telemetry_5min.csv``
bit-for-bit; the harness test-suite asserts exactly that.

Shape (14 days x 288 five-minute steps = 4032 points, requests-per-minute
style magnitudes):

    value[t] = max(0, base + trend*t
                     + daily harmonics (24h and 12h periods)
                     + weekly modulation (weekday/weekend amplitude)
                     + AR(1) noise, phi=0.65, sigma=55)
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta

import numpy as np

SEED = 42
DAYS = 14
STEPS_PER_DAY = 288
START = datetime(2026, 10, 5, 0, 0)  # a Monday


def generate(seed: int = SEED) -> tuple[list[str], np.ndarray]:
    """Return (iso timestamps, values) for the synthetic telemetry series."""
    n = DAYS * STEPS_PER_DAY
    t = np.arange(n, dtype=float)
    step_of_day = t % STEPS_PER_DAY
    day_index = t // STEPS_PER_DAY

    base = 2200.0
    trend = 0.011 * t  # slow growth, ~ +44 over the fortnight
    daily = 620.0 * np.sin(2.0 * np.pi * (step_of_day - 96.0) / STEPS_PER_DAY) + 210.0 * np.sin(
        4.0 * np.pi * (step_of_day - 60.0) / STEPS_PER_DAY
    )
    # Days 5 and 6 of each week (Sat/Sun) run at 62% amplitude.
    weekend = np.where((day_index % 7) >= 5, 0.62, 1.0)
    rng = np.random.default_rng(seed)
    innovations = rng.normal(0.0, 55.0, size=n)
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.65 * noise[i - 1] + innovations[i]

    values = np.maximum(0.0, base + trend + weekend * daily + noise)
    stamps = [(START + timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%S") for i in range(n)]
    return stamps, values


def main() -> None:
    stamps, values = generate()
    with open("synthetic_telemetry_5min.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "value"])
        for ts, v in zip(stamps, values, strict=True):
            w.writerow([ts, f"{v:.4f}"])
    print(f"wrote {len(values)} rows")


if __name__ == "__main__":
    main()

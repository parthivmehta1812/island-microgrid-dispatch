"""Synthetic 24-hour island profile and default component parameters."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HOURS = 24


@dataclass
class Generator:
    name: str
    cost: float     # EUR per Wh produced
    pmin: float     # W, minimum output (unit is always online)
    pmax: float     # W, maximum output
    dpmax: float    # W per hour, maximum ramp rate


@dataclass
class Battery:
    cost: float      # EUR per Wh charged or discharged
    pin_max: float   # W, maximum charging power
    pout_max: float  # W, maximum discharging power
    emin: float      # Wh, minimum stored energy
    emax: float      # Wh, maximum stored energy
    eta_in: float    # charging efficiency
    eta_out: float   # discharging efficiency


def island_profile(seed: int = 3) -> pd.DataFrame:
    """Return a reproducible synthetic summer day for the island (all values in W)."""
    rng = np.random.default_rng(seed)
    h = np.arange(HOURS)

    # Load: typical residential day — flat night base, morning rise, busy midday,
    # sharp evening peak when people come home, steep drop late at night.
    shape_kw = np.array([24.0, 23.6, 23.4, 23.5, 23.8, 24.4, 26.0, 30.5, 37.5, 43.0, 46.0, 45.0,
                         47.5, 45.5, 42.0, 41.5, 44.5, 56.0, 66.0, 63.5, 60.0, 58.5, 47.0, 29.0])
    load = shape_kw * 1000 * rng.normal(1.0, 0.01, HOURS)

    # Solar: clear-sky bell between ~05:30 and ~21:00 with passing clouds, peak about 6 kW
    shape = np.clip(np.sin(np.pi * (h - 5.5) / 15.5), 0, None) ** 1.4
    solar = 6_000 * shape * np.clip(rng.normal(0.95, 0.10, HOURS), 0.6, 1.0)

    # Wind: smooth random series around a 15 % capacity factor (a calm day), turbines max 33.6 kW
    x = np.zeros(HOURS)
    for t in range(1, HOURS):
        x[t] = 0.85 * x[t - 1] + rng.normal(0, 0.04)
    wind = 33_600 * np.clip(0.15 + x, 0.0, 0.40)

    return pd.DataFrame(
        {"Load [W]": load, "Wind [W]": wind, "Solar [W]": solar},
        index=pd.Index(h, name="hour"),
    ).round(1)


def default_units() -> tuple[list[Generator], Battery]:
    """Return the course's teaching-case component values."""
    gens = [
        Generator("Generator 1 (dirty fossil)", cost=0.06, pmin=10_000, pmax=40_000, dpmax=5_000),
        Generator("Generator 2 (CCS)",          cost=0.12, pmin=10_000, pmax=40_000, dpmax=5_000),
    ]
    bat = Battery(
        cost=3.4, pin_max=7_000, pout_max=10_000,
        emin=5_000, emax=50_000, eta_in=0.9678, eta_out=0.9478,
    )
    return gens, bat

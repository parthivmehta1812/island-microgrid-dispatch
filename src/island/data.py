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

    load = (
        23_500
        + 14_000 * np.exp(-0.5 * ((h - 9.0) / 2.0) ** 2)
        + 18_000 * np.exp(-0.5 * ((h - 13.5) / 2.2) ** 2)
        + 34_000 * np.exp(-0.5 * ((h - 19.5) / 2.4) ** 2)
    ) * rng.normal(1.0, 0.02, HOURS)

    shape = np.clip(np.sin(np.pi * (h - 5.5) / 15.5), 0, None) ** 1.4
    solar = 6_000 * shape * np.clip(rng.normal(0.95, 0.10, HOURS), 0.6, 1.0)

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

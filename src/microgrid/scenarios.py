"""Default island assets and the scenario set studied in the README."""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from .data import island_profiles
from .model import Battery, Case, Generator, build_model, solve
from .results import dispatch_table, summary

# --- assets of the fictional island (all values are illustrative assumptions) ---
FOSSIL = Generator("fossil", cost=0.28, pmin=25, pmax=90, ramp=30, emission=0.75, startup_cost=15)
CCS = Generator("ccs", cost=0.33, pmin=25, pmax=80, ramp=20, emission=0.10, startup_cost=25)
BATTERY = Battery(cost=0.02, pch_max=50, pdis_max=50, emin=20, emax=200, eta_ch=0.95, eta_dis=0.95, e0=100, cyclic=True)
VOLL = 5.0          # EUR/kWh for unserved energy (safety valve, never used in the default scenarios)
CO2_PRICE = 0.10    # EUR/kg = 100 EUR/t


def base_case(profiles: pd.DataFrame | None = None) -> Case:
    p = profiles if profiles is not None else island_profiles()
    return Case(
        load=p["load"].tolist(),
        wind=p["wind"].tolist(),
        solar=p["solar"].tolist(),
        generators=[copy.deepcopy(FOSSIL), copy.deepcopy(CCS)],
        battery=copy.deepcopy(BATTERY),
        voll=VOLL,
        name="A: always-on generators",
    )


def scenario_set(profiles: pd.DataFrame | None = None) -> list[Case]:
    a = base_case(profiles)

    b = copy.deepcopy(a)
    b.name = "B: unit commitment"
    b.unit_commitment = True

    c = copy.deepcopy(b)
    c.name = "C: + CO2 price 100 EUR/t"
    c.co2_price = CO2_PRICE

    d = copy.deepcopy(c)
    d.name = "D: + 2x battery"
    d.battery.emax, d.battery.pch_max, d.battery.pdis_max = 400, 100, 100
    d.battery.e0 = 200
    return [a, b, c, d]


def run(case: Case):
    m = solve(build_model(case))
    return dispatch_table(m, case), summary(m, case)


def pareto_front(case: Case, points: int = 9) -> pd.DataFrame:
    """Cost-emission trade-off: minimise cost under a tightening CO2 cap.

    Load shedding is switched off here, so every point on the front fully
    supplies the island and the trade-off is purely between cost and CO2.
    """
    case = copy.deepcopy(case)
    case.voll = None
    free = copy.deepcopy(case)
    free.co2_cap = None
    _, s_free = run(free)

    # lowest achievable emissions: price CO2 so high that cost no longer matters
    clean = copy.deepcopy(case)
    clean.co2_price = 1e3
    m = solve(build_model(clean))
    co2_min = float(sum(g.emission * m.P[g.name, t].value * case.dt for g in clean.generators for t in m.T))

    rows = []
    for cap in np.linspace(s_free["co2_t"] * 1000, co2_min * 1.001, points):
        c = copy.deepcopy(case)
        c.co2_cap = float(cap)
        _, s = run(c)
        rows.append({"co2_cap_t": cap / 1000, "co2_t": s["co2_t"], "total_cost_eur": s["total_cost_eur"],
                     "fossil_kwh": s["fossil_kwh"], "ccs_kwh": s["ccs_kwh"]})
    return pd.DataFrame(rows)

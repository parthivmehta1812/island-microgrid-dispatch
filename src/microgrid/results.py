"""Turn a solved model into tidy pandas tables."""
from __future__ import annotations

import pandas as pd
import pyomo.environ as pyo

from .model import Case


def _val(x):
    try:
        return pyo.value(x)
    except (TypeError, ValueError):
        return float(x)


def dispatch_table(m: pyo.ConcreteModel, case: Case) -> pd.DataFrame:
    """Hourly schedule of every unit (kW) plus the battery state of energy (kWh)."""
    rows = []
    for t in m.T:
        r = {"hour": t, "load": case.load[t]}
        for g in m.G:
            r[g] = _val(m.P[g, t])
        r["wind"] = _val(m.W[t])
        r["solar"] = _val(m.S[t])
        r["wind_curtailed"] = case.wind[t] - r["wind"]
        r["solar_curtailed"] = case.solar[t] - r["solar"]
        if case.battery is not None:
            r["bat_charge"] = _val(m.Pch[t])
            r["bat_discharge"] = _val(m.Pdis[t])
            r["bat_energy"] = _val(m.E[t])
        r["shed"] = _val(m.shed[t]) if case.voll is not None else 0.0
        rows.append(r)
    df = pd.DataFrame(rows).set_index("hour")
    return df.round(6)


def summary(m: pyo.ConcreteModel, case: Case) -> dict:
    """Headline KPIs of one scenario."""
    d = dispatch_table(m, case)
    gens = [g.name for g in case.generators]
    energy_load = d["load"].sum() * case.dt
    res_used = (d["wind"].sum() + d["solar"].sum()) * case.dt
    out = {
        "scenario": case.name,
        "total_cost_eur": _val(m.obj),
        "generation_cost_eur": _val(m.cost_gen),
        "co2_cost_eur": _val(m.cost_co2),
        "battery_cost_eur": _val(m.cost_bat),
        "startup_cost_eur": _val(m.cost_su),
        "co2_t": _val(m.co2) / 1000,
        "renewable_share_pct": 100 * res_used / energy_load,
        "unserved_kwh": d["shed"].sum() * case.dt,
        "curtailed_kwh": (d["wind_curtailed"].sum() + d["solar_curtailed"].sum()) * case.dt,
    }
    for g in gens:
        out[f"{g}_kwh"] = d[g].sum() * case.dt
    if case.battery is not None:
        out["battery_throughput_kwh"] = (d["bat_charge"].sum() + d["bat_discharge"].sum()) * case.dt
    return out

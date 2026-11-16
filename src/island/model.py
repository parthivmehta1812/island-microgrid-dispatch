"""Pyomo optimisation model for least-cost island dispatch."""
from __future__ import annotations

import pandas as pd
import pyomo.environ as pyo

from .data import Battery, Generator, HOURS


def solve_schedule(profile: pd.DataFrame, gens: list[Generator], bat: Battery) -> dict:
    """Least-cost hourly schedule.

    Generators are always online (P >= Pmin), wind and solar are used in full,
    and the battery start level is a free variable.
    """
    load = profile["Load [W]"].values
    res  = profile["Wind [W]"].values + profile["Solar [W]"].values

    m = pyo.ConcreteModel()
    m.T  = pyo.RangeSet(0, HOURS - 1)
    m.TE = pyo.RangeSet(0, HOURS)
    m.G  = pyo.RangeSet(0, len(gens) - 1)

    m.P   = pyo.Var(m.G, m.T, bounds=lambda m, g, t: (gens[g].pmin, gens[g].pmax))
    m.Pin  = pyo.Var(m.T, bounds=(0, bat.pin_max))
    m.Pout = pyo.Var(m.T, bounds=(0, bat.pout_max))
    m.E    = pyo.Var(m.TE, bounds=(bat.emin, bat.emax))

    m.balance   = pyo.Constraint(m.T, rule=lambda m, t:
        sum(m.P[g, t] for g in m.G) + res[t] + m.Pout[t] == load[t] + m.Pin[t])
    m.ramp_up   = pyo.Constraint(m.G, m.T, rule=lambda m, g, t:
        pyo.Constraint.Skip if t == 0 else m.P[g, t] - m.P[g, t - 1] <= gens[g].dpmax)
    m.ramp_down = pyo.Constraint(m.G, m.T, rule=lambda m, g, t:
        pyo.Constraint.Skip if t == 0 else m.P[g, t - 1] - m.P[g, t] <= gens[g].dpmax)
    m.storage   = pyo.Constraint(m.T, rule=lambda m, t:
        m.E[t + 1] == m.E[t] + bat.eta_in * m.Pin[t] - m.Pout[t] / bat.eta_out)

    m.cost = pyo.Objective(
        expr=sum(gens[g].cost * m.P[g, t] for g in m.G for t in m.T)
             + bat.cost * sum(m.Pin[t] + m.Pout[t] for t in m.T)
    )

    result = pyo.SolverFactory("appsi_highs").solve(m)
    if result.solver.termination_condition != pyo.TerminationCondition.optimal:
        raise RuntimeError("No feasible schedule — check the limits")

    gen_cols = [f"Power gen. {g + 1} [W]" for g in m.G]
    sched = pd.DataFrame({
        "Wind power [W]":           profile["Wind [W]"].values,
        "Solar power [W]":          profile["Solar [W]"].values,
        **{gen_cols[g]: [pyo.value(m.P[g, t]) for t in m.T] for g in m.G},
        "Battery input power [W]":  [pyo.value(m.Pin[t])  for t in m.T],
        "Battery output power [W]": [pyo.value(m.Pout[t]) for t in m.T],
        "Battery energy level [Wh]":[pyo.value(m.E[t])    for t in m.T],
        "Load [W]": load,
    }, index=profile.index)
    sched["Total generation [W]"]  = sched[["Wind power [W]", "Solar power [W]", *gen_cols,
                                             "Battery output power [W]"]].sum(axis=1)
    sched["Total consumption [W]"] = sched["Load [W]"] + sched["Battery input power [W]"]

    costs = pd.DataFrame({
        **{f"Cost gen. {g + 1} [EUR]": gens[g].cost * sched[gen_cols[g]] for g in m.G},
        "Cost battery [EUR]": bat.cost * (sched["Battery input power [W]"] + sched["Battery output power [W]"]),
    })
    costs["Instantaneous costs [EUR]"] = costs.sum(axis=1)

    energy = (
        sched[["Wind power [W]", "Solar power [W]", *gen_cols,
               "Battery output power [W]", "Battery input power [W]", "Load [W]"]]
        .sum() / 1000
    ).rename(lambda c: c.split(" [")[0] + " [kWh]")

    return {"schedule": sched.round(3), "costs": costs.round(3),
            "energy": energy, "total": float(pyo.value(m.cost))}


def shares(r: dict) -> dict:
    """Compute renewable and dirty-fossil shares from a solve_schedule result."""
    e = r["energy"]
    gen_total = (
        e["Wind power [kWh]"] + e["Solar power [kWh]"]
        + e["Power gen. 1 [kWh]"] + e["Power gen. 2 [kWh]"]
        + e["Battery output power [kWh]"]
    )
    r["gen_total"] = gen_total
    return {
        "renewables":   (e["Wind power [kWh]"] + e["Solar power [kWh]"]) / gen_total * 100,
        "dirty fossil":  e["Power gen. 1 [kWh]"] / gen_total * 100,
    }

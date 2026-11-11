"""Economic dispatch / unit commitment model for a small island microgrid.

The model decides, hour by hour, how much each dispatchable generator produces
and how the battery is charged and discharged so that demand is met at the
lowest total cost, subject to the technical limits of every unit.

Formulation (all powers in kW, energy in kWh, time step ``dt`` in hours):

    min  sum_t [ sum_g (c_g + p_CO2 * e_g) * P_g,t * dt
                 + c_bat * (P_ch,t + P_dis,t) * dt
                 + sum_g c_su,g * su_g,t
                 + VOLL * shed_t * dt ]

    s.t. power balance   sum_g P_g,t + W_t + S_t + P_dis,t + shed_t = L_t + P_ch,t
         generator limits  Pmin_g * u_g,t <= P_g,t <= Pmax_g * u_g,t
         ramp limits       |P_g,t - P_g,t-1| <= R_g  (relaxed at start-up/shut-down)
         renewables        0 <= W_t <= W_avail,t,  0 <= S_t <= S_avail,t
         battery           E_t+1 = E_t + (eta_ch * P_ch,t - P_dis,t / eta_dis) * dt
                           Emin <= E_t <= Emax,  P_ch <= Pch_max,  P_dis <= Pdis_max
         emissions (opt.)  sum_t sum_g e_g * P_g,t * dt <= CO2_cap

Without unit commitment, u_g,t is fixed to 1 (every generator stays online, so
it can never go below its minimum output). With unit commitment, u_g,t is a
binary on/off decision and the problem becomes a MILP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import pyomo.environ as pyo


@dataclass
class Generator:
    name: str
    cost: float            # fuel + O&M cost per unit of energy (e.g. EUR/kWh)
    pmin: float            # minimum stable output when online (kW)
    pmax: float            # maximum output (kW)
    ramp: float            # maximum change in output per time step (kW per step)
    emission: float = 0.0  # CO2 intensity (kg/kWh)
    startup_cost: float = 0.0  # EUR per start (only used with unit commitment)


@dataclass
class Battery:
    cost: float               # throughput / degradation cost (EUR per kWh charged or discharged)
    pch_max: float            # maximum charging power (kW)
    pdis_max: float           # maximum discharging power (kW)
    emin: float               # minimum state of energy (kWh)
    emax: float               # maximum state of energy (kWh)
    eta_ch: float = 0.95      # charging efficiency
    eta_dis: float = 0.95     # discharging efficiency
    e0: Optional[float] = None  # initial energy (kWh); None = chosen by the optimiser
    cyclic: bool = True       # end the horizon with at least the initial energy


@dataclass
class Case:
    load: Sequence[float]
    wind: Sequence[float]
    solar: Sequence[float]
    generators: list
    battery: Optional[Battery] = None
    dt: float = 1.0
    co2_price: float = 0.0               # EUR per kg CO2
    co2_cap: Optional[float] = None      # kg CO2 over the horizon
    unit_commitment: bool = False
    allow_curtailment: bool = True
    voll: Optional[float] = None         # value of lost load (EUR/kWh); None = no load shedding
    name: str = "case"
    meta: dict = field(default_factory=dict)


def build_model(case: Case) -> pyo.ConcreteModel:
    T = len(case.load)
    if not (len(case.wind) == len(case.solar) == T):
        raise ValueError("load, wind and solar profiles must have the same length")

    m = pyo.ConcreteModel(name=case.name)
    m.T = pyo.RangeSet(0, T - 1)
    m.TE = pyo.RangeSet(0, T)  # energy states include the end of the horizon
    m.G = pyo.Set(initialize=[g.name for g in case.generators], ordered=True)
    gen = {g.name: g for g in case.generators}
    dt = case.dt

    # --- generators -------------------------------------------------------
    m.P = pyo.Var(m.G, m.T, within=pyo.NonNegativeReals)
    if case.unit_commitment:
        m.u = pyo.Var(m.G, m.T, within=pyo.Binary)
        m.su = pyo.Var(m.G, m.T, within=pyo.NonNegativeReals)  # start-up indicator (relaxed, integral by construction)
    else:
        m.u = pyo.Param(m.G, m.T, initialize=1.0)

    m.gen_min = pyo.Constraint(m.G, m.T, rule=lambda m, g, t: m.P[g, t] >= gen[g].pmin * m.u[g, t])
    m.gen_max = pyo.Constraint(m.G, m.T, rule=lambda m, g, t: m.P[g, t] <= gen[g].pmax * m.u[g, t])

    def ramp_up(m, g, t):
        if t == 0:
            return pyo.Constraint.Skip
        slack = gen[g].pmax * (1 - m.u[g, t - 1]) if case.unit_commitment else 0
        return m.P[g, t] - m.P[g, t - 1] <= gen[g].ramp + slack

    def ramp_down(m, g, t):
        if t == 0:
            return pyo.Constraint.Skip
        slack = gen[g].pmax * (1 - m.u[g, t]) if case.unit_commitment else 0
        return m.P[g, t - 1] - m.P[g, t] <= gen[g].ramp + slack

    m.ramp_up = pyo.Constraint(m.G, m.T, rule=ramp_up)
    m.ramp_down = pyo.Constraint(m.G, m.T, rule=ramp_down)

    if case.unit_commitment:
        def startup(m, g, t):
            prev = m.u[g, t - 1] if t > 0 else 1  # assume units are online before the horizon
            return m.su[g, t] >= m.u[g, t] - prev
        m.startup = pyo.Constraint(m.G, m.T, rule=startup)

    # --- renewables -------------------------------------------------------
    if case.allow_curtailment:
        m.W = pyo.Var(m.T, bounds=lambda m, t: (0, case.wind[t]))
        m.S = pyo.Var(m.T, bounds=lambda m, t: (0, case.solar[t]))
    else:
        m.W = pyo.Param(m.T, initialize=lambda m, t: case.wind[t])
        m.S = pyo.Param(m.T, initialize=lambda m, t: case.solar[t])

    # --- battery ----------------------------------------------------------
    b = case.battery
    if b is not None:
        m.Pch = pyo.Var(m.T, bounds=(0, b.pch_max))
        m.Pdis = pyo.Var(m.T, bounds=(0, b.pdis_max))
        m.E = pyo.Var(m.TE, bounds=(b.emin, b.emax))
        m.soc = pyo.Constraint(
            m.T, rule=lambda m, t: m.E[t + 1] == m.E[t] + (b.eta_ch * m.Pch[t] - m.Pdis[t] / b.eta_dis) * dt
        )
        if b.e0 is not None:
            m.E[0].fix(b.e0)
        if b.cyclic:
            m.cyclic = pyo.Constraint(expr=m.E[T] >= m.E[0])
        if case.unit_commitment:  # no simultaneous charging and discharging
            m.mode = pyo.Var(m.T, within=pyo.Binary)
            m.ch_mode = pyo.Constraint(m.T, rule=lambda m, t: m.Pch[t] <= b.pch_max * m.mode[t])
            m.dis_mode = pyo.Constraint(m.T, rule=lambda m, t: m.Pdis[t] <= b.pdis_max * (1 - m.mode[t]))
        pch, pdis = m.Pch, m.Pdis
    else:
        pch = pdis = {t: 0 for t in range(T)}

    # --- load shedding (optional safety valve) ----------------------------
    if case.voll is not None:
        m.shed = pyo.Var(m.T, within=pyo.NonNegativeReals)
        shed = m.shed
    else:
        shed = {t: 0 for t in range(T)}

    # --- power balance ----------------------------------------------------
    m.balance = pyo.Constraint(
        m.T,
        rule=lambda m, t: sum(m.P[g, t] for g in m.G) + m.W[t] + m.S[t] + pdis[t] + shed[t]
        == case.load[t] + pch[t],
    )

    # --- emissions ----------------------------------------------------------
    m.co2 = pyo.Expression(expr=sum(gen[g].emission * m.P[g, t] * dt for g in m.G for t in m.T))
    if case.co2_cap is not None:
        m.co2_limit = pyo.Constraint(expr=m.co2 <= case.co2_cap)

    # --- objective --------------------------------------------------------
    m.cost_gen = pyo.Expression(expr=sum(gen[g].cost * m.P[g, t] * dt for g in m.G for t in m.T))
    m.cost_co2 = pyo.Expression(expr=case.co2_price * m.co2)
    m.cost_bat = pyo.Expression(expr=(b.cost * sum((m.Pch[t] + m.Pdis[t]) * dt for t in m.T)) if b else 0)
    m.cost_su = pyo.Expression(
        expr=sum(gen[g].startup_cost * m.su[g, t] for g in m.G for t in m.T) if case.unit_commitment else 0
    )
    m.cost_shed = pyo.Expression(expr=(case.voll * sum(m.shed[t] * dt for t in m.T)) if case.voll is not None else 0)
    m.obj = pyo.Objective(
        expr=m.cost_gen + m.cost_co2 + m.cost_bat + m.cost_su + m.cost_shed, sense=pyo.minimize
    )
    return m


def solve(m: pyo.ConcreteModel, solver: str = "appsi_highs", tee: bool = False) -> pyo.ConcreteModel:
    opt = pyo.SolverFactory(solver)
    res = opt.solve(m, tee=tee)
    tc = res.solver.termination_condition
    if tc != pyo.TerminationCondition.optimal:
        raise RuntimeError(f"Solver did not find an optimal solution: {tc}")
    return m

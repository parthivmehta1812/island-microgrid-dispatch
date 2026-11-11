"""Sanity checks: physics and limits hold in every scenario."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from microgrid.model import Battery, Case, Generator, build_model, solve  # noqa: E402
from microgrid.results import dispatch_table, summary  # noqa: E402
from microgrid.scenarios import scenario_set  # noqa: E402

TOL = 1e-4


@pytest.fixture(scope="module")
def solved():
    out = []
    for c in scenario_set():
        m = solve(build_model(c))
        out.append((c, dispatch_table(m, c), summary(m, c)))
    return out


def test_power_balance(solved):
    for c, d, _ in solved:
        supply = d[[g.name for g in c.generators]].sum(axis=1) + d.wind + d.solar + d.bat_discharge + d.shed
        demand = d.load + d.bat_charge
        assert (supply - demand).abs().max() < TOL, c.name


def test_generator_limits_and_ramps(solved):
    for c, d, _ in solved:
        for g in c.generators:
            p = d[g.name]
            on = p > TOL
            assert (p <= g.pmax + TOL).all()
            assert (p[on] >= g.pmin - TOL).all()
            if not c.unit_commitment:
                assert (p.diff().abs().dropna() <= g.ramp + TOL).all()


def test_battery_limits(solved):
    for c, d, _ in solved:
        b = c.battery
        assert d.bat_energy.between(b.emin - TOL, b.emax + TOL).all()
        assert (d.bat_charge <= b.pch_max + TOL).all() and (d.bat_discharge <= b.pdis_max + TOL).all()


def test_no_unserved_energy(solved):
    for c, _, s in solved:
        assert s["unserved_kwh"] < TOL, c.name


def test_renewables_not_above_available(solved):
    for c, d, _ in solved:
        assert (d.wind <= pd.Series(list(c.wind)) + TOL).all() and (d.solar <= pd.Series(list(c.solar)) + TOL).all()


def test_merit_order_toy_case():
    """Two generators, flat load: the cheaper unit must be loaded first."""
    cheap = Generator("cheap", cost=0.1, pmin=0, pmax=50, ramp=100)
    dear = Generator("dear", cost=0.3, pmin=0, pmax=50, ramp=100)
    c = Case(load=[70] * 4, wind=[0] * 4, solar=[0] * 4, generators=[cheap, dear])
    d = dispatch_table(solve(build_model(c)), c)
    assert d.cheap.round(6).eq(50).all() and d.dear.round(6).eq(20).all()


def test_battery_shifts_energy():
    """Free storage should move surplus solar into an evening deficit."""
    g = Generator("gen", cost=0.3, pmin=0, pmax=100, ramp=100)
    b = Battery(cost=0.0, pch_max=50, pdis_max=50, emin=0, emax=100, eta_ch=1, eta_dis=1, e0=0, cyclic=False)
    c = Case(load=[20, 20], wind=[0, 0], solar=[60, 0], generators=[g], battery=b)
    d = dispatch_table(solve(build_model(c)), c)
    assert d.gen.sum() == pytest.approx(0, abs=TOL)

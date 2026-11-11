"""Run the full island study: inputs, four scenarios, the cost-emission front, figures.

Usage:
    python run_scenarios.py            # writes everything to ./results
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from microgrid.data import island_profiles  # noqa: E402
from microgrid.plots import (  # noqa: E402
    plot_battery, plot_dispatch_compare, plot_pareto, plot_profiles, plot_scenarios,
)
from microgrid.scenarios import pareto_front, run, scenario_set  # noqa: E402


def main(out: Path = ROOT / "results", assets: Path = ROOT / "assets"):
    out.mkdir(exist_ok=True)
    assets.mkdir(exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)

    profiles = island_profiles()
    profiles.to_csv(ROOT / "data" / "island_profiles.csv")
    plot_profiles(profiles, assets / "01_inputs.png")

    cases = scenario_set(profiles)
    dispatches, rows = {}, []
    for c in cases:
        d, s = run(c)
        dispatches[c.name] = d
        rows.append(s)
        d.to_csv(out / f"dispatch_{c.name.split(':')[0]}.csv")
        print(f"{c.name:<28} cost €{s['total_cost_eur']:>8,.0f}   CO2 {s['co2_t']:5.2f} t   "
              f"RES share {s['renewable_share_pct']:5.1f}%   curtailed {s['curtailed_kwh']:7.0f} kWh")
    summary = pd.DataFrame(rows)
    summary.round(2).to_csv(out / "summary.csv", index=False)

    a, b = cases[0].name, cases[1].name
    plot_dispatch_compare(dispatches[a], dispatches[b], assets / "02_dispatch_A_vs_B.png",
                          titles=(f"{a}: generators can never go below minimum output",
                                  f"{b}: generators switch off when renewables suffice"))
    plot_battery(dispatches, assets / "03_battery_soc.png", {c.name: c.battery.emax for c in cases})
    plot_scenarios(summary, assets / "04_scenarios.png")

    front = pareto_front(cases[1])
    front.round(3).to_csv(out / "pareto_front.csv", index=False)
    plot_pareto(front, assets / "05_pareto.png")
    print(f"\nPareto front: {front.co2_t.iloc[0]:.2f} t -> {front.co2_t.iloc[-1]:.2f} t CO2, "
          f"€{front.total_cost_eur.iloc[0]:,.0f} -> €{front.total_cost_eur.iloc[-1]:,.0f}")
    print(f"Results written to {out}, plots written to {assets}")


if __name__ == "__main__":
    main()

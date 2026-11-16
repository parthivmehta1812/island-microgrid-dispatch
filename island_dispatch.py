"""
Optimal scheduling of a small island energy system — Steps 1-8.

The script follows the eight-step optimal-scheduling exercise of the
TU Delft / DelftX course "Digitalization of Intelligent and Integrated
Energy Systems", applied to a synthetic 24-hour profile.

    Step 1  Inspect the consumption and weather profile
    Step 2  Build and solve the optimisation model (base case)
    Step 3  Check the power balance and the generator limits
    Step 4  Compare the costs of the generators
    Step 5  Plot the schedule, the battery and the costs
    Step 6  Sensitivity: double the solar generation and make the battery cheaper
    Step 7  Renewable share, and push "dirty fossil" generation below 10 %
    Step 8  Find a configuration that reduces the costs even more

Run:
    python island_dispatch.py
    -> prints every step, saves plots to ./assets, data files to ./results
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from island.data import default_units, island_profile
from island.model import shares, solve_schedule
from island.plots import plot_costs, plot_energy_share, plot_profiles, plot_schedule

ASSETS  = ROOT / "assets"   # README plots — committed to git
RESULTS = ROOT / "results"  # generated data files — git-ignored


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    report: list[str] = []

    def say(text: str = "") -> None:
        print(text)
        report.append(text)

    # ── Step 1 ────────────────────────────────────────────────────────────────
    p = island_profile()
    p.to_csv(RESULTS / "input_profile.csv")
    plot_profiles(p, ASSETS / "step1_profiles.png")
    res_kwh = (p["Wind [W]"] + p["Solar [W]"]).sum() / 1000
    say("STEP 1 - Inspect the profile")
    say(f"  Load {p['Load [W]'].sum()/1000:.0f} kWh/day  "
        f"(peak {p['Load [W]'].max()/1000:.1f} kW at {p['Load [W]'].idxmax()} h);  "
        f"wind + solar {res_kwh:.0f} kWh ({res_kwh / (p['Load [W]'].sum()/1000) * 100:.0f} % of load).")
    short = int(((p["Wind [W]"] + p["Solar [W]"]) < p["Load [W]"]).sum())
    say(f"  Renewables below the load in {short}/24 hours → generators and battery are needed.")

    # ── Step 2 ────────────────────────────────────────────────────────────────
    gens, bat = default_units()
    base = solve_schedule(p, gens, bat)
    base["schedule"].to_csv(RESULTS / "step2_schedule_base.csv")
    say("\nSTEP 2 - Base case solved")
    say("  Energy per unit [kWh]: " +
        ", ".join(f"{k.split(' [')[0]} {v:.1f}" for k, v in base["energy"].items()))

    # ── Step 3 ────────────────────────────────────────────────────────────────
    s = base["schedule"]
    gap = (s["Total generation [W]"] - s["Total consumption [W]"]).abs().max()
    say("\nSTEP 3 - Checks")
    say(f"  Power balance: largest hourly mismatch {gap:.4f} W → {'OK' if gap < 1e-2 else 'VIOLATED'}")
    for i, g in enumerate(gens, 1):
        col  = s[f"Power gen. {i} [W]"]
        ramp = col.diff().abs().max()
        ok   = col.min() >= g.pmin - 1e-3 and col.max() <= g.pmax + 1e-3 and ramp <= g.dpmax + 1e-3
        say(f"  {g.name}: {col.min()/1000:.1f}–{col.max()/1000:.1f} kW, "
            f"largest ramp {ramp/1000:.1f} kW/h → {'OK' if ok else 'VIOLATED'}")

    # ── Step 4 ────────────────────────────────────────────────────────────────
    c = base["costs"].sum()
    say("\nSTEP 4 - Costs")
    say(f"  Gen 1: EUR {c['Cost gen. 1 [EUR]']:,.0f} | "
        f"Gen 2: EUR {c['Cost gen. 2 [EUR]']:,.0f} | "
        f"Battery: EUR {c['Cost battery [EUR]']:,.0f} | "
        f"Total: EUR {base['total']:,.0f}")

    # ── Step 5 ────────────────────────────────────────────────────────────────
    plot_schedule(base, ASSETS / "step5_schedule_base.png", "Step 5: optimal schedule, base case")
    plot_costs(base,    ASSETS / "step5_costs_base.png",    "Step 5: costs, base case")
    say("\nSTEP 5 - Figures saved (step5_schedule_base.png, step5_costs_base.png)")

    # ── Step 6 ────────────────────────────────────────────────────────────────
    p6       = p.copy(); p6["Solar [W]"] *= 2
    bat6     = copy.deepcopy(bat); bat6.cost = 1.0
    r6       = solve_schedule(p6, gens, bat6)
    plot_schedule(r6, ASSETS / "step6_schedule.png", "Step 6: double solar, battery cost 1 EUR/Wh")
    plot_costs(r6,    ASSETS / "step6_costs.png",    "Step 6: costs with double solar and a cheaper battery")
    c6 = r6["costs"].sum()
    say("\nSTEP 6 - Double solar, battery cost 3.4 → 1 EUR/Wh")
    say(f"  Total EUR {base['total']:,.0f} → EUR {r6['total']:,.0f} "
        f"({(r6['total']/base['total']-1)*100:+.0f} %);  "
        f"battery EUR {c['Cost battery [EUR]']:,.0f} → {c6['Cost battery [EUR]']:,.0f}")

    # ── Step 7 ────────────────────────────────────────────────────────────────
    sh_base = shares(base)
    gens7   = copy.deepcopy(gens)
    gens7[0].cost = 4.0
    gens7[0].pmin = 0
    r7 = solve_schedule(p, gens7, bat)
    sh7 = shares(r7)
    plot_energy_share({"Base case": base, "Gen. 1 penalised": r7},
                      ASSETS / "step7_energy_share.png")
    say("\nSTEP 7 - Renewables and dirty fossil")
    say(f"  Base: renewables {sh_base['renewables']:.1f} %, dirty fossil {sh_base['dirty fossil']:.1f} %")
    say(f"  Gen 1 cost 0.06 → 4 EUR/Wh, Pmin 10 kW → 0: "
        f"dirty fossil {sh7['dirty fossil']:.1f} % "
        f"({'below' if sh7['dirty fossil'] < 10 else 'NOT below'} 10 %)")

    # ── Step 8 ────────────────────────────────────────────────────────────────
    gens8 = copy.deepcopy(gens)
    for g in gens8:
        g.pmin, g.dpmax = 0, 20_000
    bat8      = copy.deepcopy(bat); bat8.cost = 1.0
    r8        = solve_schedule(p, gens8, bat8)
    plot_schedule(r8, ASSETS / "step8_schedule.png",
                  "Step 8: flexible generators (Pmin 0, ramp 20 kW/h), battery 1 EUR/Wh")
    plot_costs(r8,    ASSETS / "step8_costs.png",
                  "Step 8: costs with flexible generators")
    say("\nSTEP 8 - Flexible generators (Pmin 0, ramp 20 kW/h) + battery 1 EUR/Wh")
    say(f"  Total EUR {base['total']:,.0f} → EUR {r8['total']:,.0f} "
        f"({(r8['total']/base['total']-1)*100:+.0f} %);  "
        f"battery out {r8['energy']['Battery output power [kWh]']:.1f} kWh")

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = pd.DataFrame({
        "Step": ["2 Base case", "6 Double solar + cheap battery",
                 "7 Gen. 1 penalised", "8 Flexible generators"],
        "Total cost [EUR]":   [r["total"] for r in (base, r6, r7, r8)],
        "Gen. 1 [kWh]":       [r["energy"]["Power gen. 1 [kWh]"]          for r in (base, r6, r7, r8)],
        "Gen. 2 [kWh]":       [r["energy"]["Power gen. 2 [kWh]"]          for r in (base, r6, r7, r8)],
        "Battery out [kWh]":  [r["energy"]["Battery output power [kWh]"]  for r in (base, r6, r7, r8)],
    }).round(1)
    summary.to_csv(RESULTS / "summary.csv", index=False)
    (RESULTS / "report.txt").write_text("\n".join(report) + "\n")
    say(f"\nPlots  → {ASSETS}")
    say(f"Data   → {RESULTS}")


if __name__ == "__main__":
    main()

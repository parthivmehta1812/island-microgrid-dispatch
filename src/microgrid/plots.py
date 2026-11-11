"""Static figures for the README (matplotlib)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
# categorical slots, assigned to entities in a fixed order (validated colour-blind safe)
C = {"wind": "#2a78d6", "solar": "#eb6834", "ccs": "#1baf7a", "fossil": "#eda100", "battery": "#e87ba4"}
LABEL = {"wind": "Wind", "solar": "Solar PV", "ccs": "Gas + CCS", "fossil": "Diesel (fossil)", "battery": "Battery"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "text.color": INK, "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "legend.frameon": False,
})


def _hours_axis(ax, n):
    ax.set_xlim(0, n - 1)
    ax.set_xticks(range(0, n, 6))
    ax.set_xticklabels([f"{h % 24:02d}h" if h % 24 else f"Day {h // 24 + 1}" for h in range(0, n, 6)])
    for d in range(24, n, 24):
        ax.axvline(d, color=INK_2, lw=0.8, ls=":")


def plot_profiles(p: pd.DataFrame, path: str):
    fig, ax = plt.subplots(figsize=(11, 4.2))
    x = p.index.values
    ax.plot(x, p["load"], color=INK, lw=2, label="Demand")
    ax.plot(x, p["wind"], color=C["wind"], lw=2, label=LABEL["wind"])
    ax.plot(x, p["solar"], color=C["solar"], lw=2, label=LABEL["solar"])
    _hours_axis(ax, len(x))
    ax.set_ylabel("Power [kW]")
    ax.set_title("Island inputs: demand vs. available wind and solar")
    for d, txt in enumerate(["sunny, calm", "windy, some clouds", "overcast"]):
        ax.text(24 * d + 1, ax.get_ylim()[1] * 0.97, txt, color=INK_2, va="top", fontsize=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _stack(ax, d: pd.DataFrame, title: str):
    x = d.index.values
    order = ["wind", "solar", "ccs", "fossil"]
    ys = [d[k].values for k in order] + [d["bat_discharge"].values]
    cols = [C[k] for k in order] + [C["battery"]]
    labs = [LABEL[k] for k in order] + ["Battery discharge"]
    ax.stackplot(x, ys, colors=cols, labels=labs, edgecolor=SURFACE, linewidth=1.0)
    ax.fill_between(x, 0, -d["bat_charge"].values, color=C["battery"], alpha=0.55, edgecolor=SURFACE,
                    linewidth=1.0, label="Battery charging")
    ax.plot(x, d["load"], color=INK, lw=2, label="Demand")
    curt = d["wind_curtailed"] + d["solar_curtailed"]
    total = sum(ys)
    ax.fill_between(x, total, total + curt, facecolor="none", edgecolor=INK_2, hatch="////", linewidth=0,
                    label="Curtailed renewables")
    ax.axhline(0, color=INK_2, lw=0.8)
    _hours_axis(ax, len(x))
    ax.set_ylabel("Power [kW]")
    ax.set_title(title)


def plot_dispatch_compare(d_a: pd.DataFrame, d_b: pd.DataFrame, path: str, titles=("", "")):
    fig, axes = plt.subplots(2, 1, figsize=(11, 8.4), sharex=True, sharey=True)
    _stack(axes[0], d_a, titles[0])
    _stack(axes[1], d_b, titles[1])
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_battery(dispatches: dict, path: str, emax: dict):
    fig, ax = plt.subplots(figsize=(11, 3.6))
    styles = ["-", "--", "-.", ":"]
    for (name, d), ls in zip(dispatches.items(), styles):
        ax.plot(d.index, d["bat_energy"] / emax[name] * 100, color=INK if ls == "-" else INK_2, lw=2, ls=ls, label=name)
    _hours_axis(ax, len(next(iter(dispatches.values()))))
    ax.set_ylim(0, 105)
    ax.set_ylabel("State of charge [%]")
    ax.set_title("Battery state of charge by scenario")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=4)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_scenarios(s: pd.DataFrame, path: str):
    """Cost breakdown and CO2 per scenario as two separate panels (no dual axis)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    names = s["scenario"].tolist()[::-1]
    y = np.arange(len(names))
    parts = [("generation_cost_eur", "Fuel & O&M", C["wind"]), ("co2_cost_eur", "CO2 price", C["solar"]),
             ("battery_cost_eur", "Battery wear", C["ccs"]), ("startup_cost_eur", "Start-ups", C["fossil"])]
    left = np.zeros(len(names))
    rs = s.iloc[::-1]
    for col, lab, colr in parts:
        v = rs[col].values
        ax1.barh(y, v, left=left, color=colr, label=lab, edgecolor=SURFACE, linewidth=2, height=0.6)
        left += v
    for yi, tot in zip(y, left):
        ax1.text(tot + 15, yi, f"€{tot:,.0f}", va="center", color=INK, fontsize=10)
    ax1.set_yticks(y)
    ax1.set_yticklabels(names)
    ax1.set_xlabel("Operating cost over 3 days [€]")
    ax1.set_title("Total operating cost")
    ax1.set_xlim(0, left.max() * 1.18)
    ax1.grid(axis="y", visible=False)
    ax1.legend(loc="lower right", fontsize=9)

    co2 = rs["co2_t"].values
    ax2.barh(y, co2, color=INK_2, height=0.6)
    for yi, v in zip(y, co2):
        ax2.text(v + 0.02, yi, f"{v:.2f} t", va="center", color=INK, fontsize=10)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlabel("CO2 over 3 days [t]")
    ax2.set_title("Emissions")
    ax2.set_xlim(0, co2.max() * 1.3)
    ax2.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_pareto(p: pd.DataFrame, path: str):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(p["co2_t"], p["total_cost_eur"], color=C["wind"], lw=2, marker="o", ms=8,
            markeredgecolor=SURFACE, markeredgewidth=2)
    first, knee, last = p.iloc[0], p.iloc[-2], p.iloc[-1]
    ax.annotate(f"Cost-optimal\n{first.co2_t:.2f} t, €{first.total_cost_eur:,.0f}", (first.co2_t, first.total_cost_eur),
                xytext=(12, 4), textcoords="offset points", ha="left", color=INK, fontsize=10)
    ax.annotate(f"{knee.co2_t:.2f} t, €{knee.total_cost_eur:,.0f}", (knee.co2_t, knee.total_cost_eur),
                xytext=(12, -22), textcoords="offset points", color=INK, fontsize=10)
    ax.annotate(f"Lowest CO2\n{last.co2_t:.2f} t, €{last.total_cost_eur:,.0f}", (last.co2_t, last.total_cost_eur),
                xytext=(12, -6), textcoords="offset points", color=INK, fontsize=10)
    ax.set_xlabel("CO2 emissions over 3 days [t]")
    ax.set_ylabel("Operating cost [€]")
    ax.set_title("Cost vs. emissions trade-off (unit commitment, CO2 cap)")
    ax.invert_xaxis()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)

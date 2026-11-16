"""Matplotlib figures for the island dispatch study."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── Style ──────────────────────────────────────────────────────────────────────
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
COL = {
    "Wind":    "#2a78d6",
    "Solar":   "#eb6834",
    "Gen 1":   "#eda100",
    "Gen 2":   "#1baf7a",
    "Battery": "#e87ba4",
}
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.labelcolor": INK2, "font.size": 10,
})


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# ── Individual figures ─────────────────────────────────────────────────────────

def plot_profiles(p: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(p.index, p["Load [W]"] / 1000,  color=INK,        lw=2, label="Load")
    ax.plot(p.index, p["Wind [W]"] / 1000,  color=COL["Wind"], lw=2, label="Wind")
    ax.plot(p.index, p["Solar [W]"] / 1000, color=COL["Solar"], lw=2, label="Solar")
    ax.set(xlabel="Time of day [hours]", ylabel="Power [kW]",
           title="Step 1: consumption and renewable generation")
    ax.legend(ncol=3, loc="upper left")
    _save(fig, path)


def plot_schedule(r: dict, path: Path, title: str) -> None:
    s = r["schedule"] / 1000
    t = s.index
    fig, ax = plt.subplots(2, 4, figsize=(16, 7))
    g1, g2 = s["Power gen. 1 [W]"], s["Power gen. 2 [W]"]
    ax[0, 0].plot(t, g1, color=COL["Gen 1"], lw=2, label="Generator 1 (dirty fossil)")
    ax[0, 0].plot(t, g2, color=COL["Gen 2"], lw=2, ls="--", label="Generator 2 (CCS)")
    ax[0, 0].plot(t, g1 + g2, color=INK, lw=1.5, ls=":", label="Total power")
    ax[0, 0].set_title("Output of the generators"); ax[0, 0].legend(fontsize=8)
    ax[0, 1].plot(t, s["Battery output power [W]"], color=COL["Battery"], lw=2)
    ax[0, 1].set_title("Output of the battery")
    w, so = s["Wind power [W]"], s["Solar power [W]"]
    ax[0, 2].plot(t, w,  color=COL["Wind"],  lw=2, label="Wind")
    ax[0, 2].plot(t, so, color=COL["Solar"], lw=2, label="Solar")
    ax[0, 2].plot(t, w + so, color=INK, lw=1.5, ls=":", label="Total power")
    ax[0, 2].set_title("Output of the renewables"); ax[0, 2].legend(fontsize=8, loc="lower left")
    ax[0, 3].plot(t, s["Total generation [W]"], color=INK, lw=2)
    ax[0, 3].set_title("Total generation")
    ax[1, 0].plot(t, s["Load [W]"], color=INK, lw=2)
    ax[1, 0].set_title("Load")
    ax[1, 1].plot(t, s["Battery input power [W]"], color=INK2, lw=2)
    ax[1, 1].set_title("Input of the battery")
    ax[1, 2].plot(t, s["Battery energy level [Wh]"], color=INK, lw=2)
    ax[1, 2].set_title("Energy level in the battery")
    ax[1, 3].plot(t, s["Total consumption [W]"], color=INK, lw=2)
    ax[1, 3].set_title("Total consumption")
    for a in ax.ravel():
        a.set_xlabel("Time of day [hours]")
        a.set_ylabel("Power [kW]")
    ax[1, 2].set_ylabel("Energy [kWh]")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    _save(fig, path)


def plot_costs(r: dict, path: Path, title: str) -> None:
    c = r["costs"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4))
    a1.plot(c.index, c["Cost gen. 1 [EUR]"],          color=COL["Gen 1"],   lw=2, label="Generator 1 (dirty fossil)")
    a1.plot(c.index, c["Cost gen. 2 [EUR]"],          color=COL["Gen 2"],   lw=2, ls="--", label="Generator 2 (CCS)")
    a1.plot(c.index, c["Cost battery [EUR]"],          color=COL["Battery"], lw=2, label="Battery")
    a1.plot(c.index, c["Instantaneous costs [EUR]"],   color=INK,            lw=1.5, ls=":", label="Total costs")
    a1.set(title="Costs of the components", xlabel="Time of day [hours]", ylabel="Costs [EUR]")
    a1.legend(fontsize=8)
    a2.plot(c.index, c["Instantaneous costs [EUR]"].cumsum(), color=COL["Wind"], lw=2)
    a2.set(title=f"Cumulative costs (total EUR {r['total']:,.0f})",
           xlabel="Time of day [hours]", ylabel="Costs [EUR]")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    _save(fig, path)


def plot_energy_share(results: dict, path: Path) -> None:
    labels = list(results)
    parts = [
        ("Wind power",           COL["Wind"]),
        ("Solar power",          COL["Solar"]),
        ("Power gen. 1",         COL["Gen 1"]),
        ("Power gen. 2",         COL["Gen 2"]),
        ("Battery output power", COL["Battery"]),
    ]
    fig, ax = plt.subplots(figsize=(8, 4))
    left = np.zeros(len(labels))
    for key, col in parts:
        v = np.array([results[l]["energy"][f"{key} [kWh]"] / results[l]["gen_total"] * 100
                      for l in labels])
        label = (key.replace("Power gen. 1", "Generator 1 (dirty fossil)")
                    .replace("Power gen. 2", "Generator 2 (CCS)")
                    .replace(" power", ""))
        ax.barh(labels, v, left=left, color=col, edgecolor="#fcfcfb", linewidth=2, label=label)
        left += v
    ax.set(xlabel="Share of total generation [%]",
           title="Step 7: where the energy comes from", xlim=(0, 100))
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=8)
    _save(fig, path)

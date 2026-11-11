# Island Microgrid Dispatch: Cost vs. CO2 Scheduling with Pyomo

An optimisation model that decides, hour by hour, how a small off-grid island should run two
dispatchable generators and a battery alongside wind and solar, so that demand is met
at the lowest cost. The model is then used to answer the operator's real questions:

* What do inflexible generators actually cost us?
* What changes if CO2 has a price?
* Is a bigger battery worth it?
* How much more do we pay for each tonne of CO2 we avoid?

![Dispatch with always-on vs. switchable generators](results/02_dispatch_A_vs_B.png)

---

## The case: a fictional island

| Asset | Size | Key parameters (assumptions) |
|---|---|---|
| Demand | ~150 homes + harbour/shop | 30–130 kW, evening peak, 4.7 MWh over 3 days |
| Wind | 100 kW | smooth stochastic profile, calm / windy / moderate days |
| Solar PV | 150 kWp | summer clear-sky shape × daily cloudiness |
| Diesel generator (fossil) | 25–90 kW | €0.28/kWh, 0.75 kg CO2/kWh, ramp 30 kW/h, start-up €15 |
| Gas generator with CCS | 25–80 kW | €0.33/kWh, 0.10 kg CO2/kWh, ramp 20 kW/h, start-up €25 |
| Battery | 200 kWh / 50 kW | 95 % / 95 % efficiency, €0.02/kWh wear cost, SoC 10–100 % |

Three days with different weather are simulated at hourly resolution: sunny and calm,
windy with passing clouds, and overcast. Wind and solar together could supply about 82 %
of the demand, but often at the wrong time.

![Inputs](results/01_inputs.png)

All data is **synthetic and reproducible** (`src/microgrid/data.py`, fixed random seed). No
measured or third-party data is used.

---

## The model

A linear program (LP) or, with unit commitment, a mixed-integer program (MILP), written in
**Pyomo** and solved with the open-source **HiGHS** solver.

**Minimise** fuel and O&M cost + CO2 cost + battery wear + start-up cost (+ a penalty for unserved load)

**Subject to**

* **Power balance** every hour: generators + wind + solar + battery discharge = demand + battery charging
* **Generator limits:** `Pmin · u ≤ P ≤ Pmax · u`, where `u` is fixed to 1 (always on) or a binary on/off decision
* **Ramp limits:** output can only change by a set amount per hour (relaxed at start-up and shut-down)
* **Battery:** state-of-energy balance with charge and discharge efficiencies, energy and power limits, no simultaneous charge and discharge (MILP), and a cyclic end state (it must end the period at least as full as it started)
* **Renewables:** may be curtailed, never exceeded
* **Optional CO2 cap** over the horizon, used to trace the cost–emission trade-off

The full formulation is documented at the top of `src/microgrid/model.py`.

---

## Scenarios and results (3 days)

| Scenario | Total cost | CO2 | Renewable share | Curtailed RES |
|---|---:|---:|---:|---:|
| **A** Always-on generators (no unit commitment) | €1,112 | 1.53 t | 24 % | 2,715 kWh |
| **B** Unit commitment (generators can switch off) | €420 | 0.98 t | 74 % | 391 kWh |
| **C** B + CO2 price of €100/t | €510 | 0.21 t | 74 % | 391 kWh |
| **D** C + double battery (400 kWh / 100 kW) | €395 | 0.10 t | 81 % | 46 kWh |

![Scenario comparison](results/04_scenarios.png)

### What the results show

1. **Flexibility matters more than fuel price.** When both generators have to stay online
   at their minimum output, they push out renewable energy that is already there. 2.7 MWh of
   wind and solar is curtailed and the renewable share is only 24 %. Letting the units switch
   off cuts operating cost by **62 %** and triples the renewable share. Nothing new is built.
2. **A CO2 price reorders the generators.** At €100/t, the CCS unit becomes cheaper per kWh
   than the diesel unit (€0.34 vs. €0.355). The schedule switches over, and emissions fall by
   **79 %** while the total cost (including the CO2 payment) rises by about a fifth.
3. **Storage pays for itself in this setup.** Doubling the battery soaks up almost all the
   remaining curtailment. It lifts the renewable share to 81 %, halves emissions again and
   brings the cost **below** scenario B, even with the CO2 price included.
4. **The trade-off is cheap at first, then steep.** Sweeping a CO2 cap shows that emissions
   can drop by about **76 %** (0.98 → 0.23 t) for a **16 %** higher cost. The last tenth of a
   tonne is the expensive part.

![Cost vs. emissions trade-off](results/05_pareto.png)

![Battery state of charge](results/03_battery_soc.png)

---

## Run it yourself (VS Code)

```bash
git clone https://github.com/<your-username>/island-microgrid-dispatch.git
cd island-microgrid-dispatch
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python run_scenarios.py      # writes figures and CSVs to ./results
pytest -q                    # checks power balance, limits and two toy cases
```

To try your own ideas, change the assets in `src/microgrid/scenarios.py` (costs, sizes,
ramps, CO2 price) or the weather in `src/microgrid/data.py`, then rerun.

```
island-microgrid-dispatch/
├── run_scenarios.py          # runs the full study
├── src/microgrid/
│   ├── model.py              # Pyomo formulation (LP / MILP)
│   ├── data.py               # synthetic load, wind and solar profiles
│   ├── scenarios.py          # island assets, scenarios A–D, Pareto sweep
│   ├── results.py            # tidy tables and KPIs
│   └── plots.py              # figures
├── data/island_profiles.csv  # generated inputs
├── results/                  # figures, dispatch tables, summary.csv, pareto_front.csv
└── tests/test_model.py       # physics and limit checks
```

---

## Limitations and next steps

* Perfect foresight over 72 hours. A rolling-horizon or stochastic version would reflect
  forecast errors.
* Linear costs and constant efficiencies. Part-load efficiency curves and battery degradation
  models would add realism.
* Possible extensions: hydrogen storage (electrolyser + fuel cell) as a seasonal buffer,
  capacity expansion (how much PV, wind or storage to build), and demand response.

---

## Acknowledgements

The problem set-up was inspired by the optimal scheduling module of the TU Delft / DelftX
course *Digitalization of Intelligent and Integrated Energy Systems*. The code, the island
case, the data, the extra features (unit commitment, CO2 pricing and caps, curtailment,
cyclic storage, Pareto analysis) and all results in this repository are my own. No course
materials, notebooks or data are included.

**Cross-check:** before building the island case, I ran this model formulation on the course's
reference case with the course's own parameters. It reproduced the course's reference results
exactly: the same total cost and the same hour-by-hour generator and battery schedule.

Author: Parthiv Mehta · [LinkedIn](https://www.linkedin.com/in/parthivmehta) · MIT License

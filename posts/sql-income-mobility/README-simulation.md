# Optional simulation example

The original teaching example uses a fully simulated family panel. Every person, relationship and income value is invented. The published article now uses real PSID results; see [README.md](README.md) and [README-real.md](README-real.md) for that workflow.

## Run the simulation

Use Python 3.9 or later. From this post's folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
python tutorial.py
```

On Windows, activate with `.venv\Scripts\activate`. SQLite is included with Python. After installing dependencies, the example needs no downloads, account or API key.

`run.py` generates the invented panel, builds a local SQLite database, checks the matches and regressions, and regenerates the original simulation outputs. `tutorial.py` reads that database and prints the three simulated income comparisons. Both scripts resolve paths relative to their own folder.

| Files | Role |
| --- | --- |
| `run.py` | Simulation, validation and original figures |
| `tutorial.py` | SQL execution and regression for the simulation |
| `sql/schema.sql`, `sql/match.sql` | Original simulated table structure and matching query |
| `data/*.csv`, `data/mobility.sqlite` | Generated simulated records and database |
| `data/provenance.json` | Simulation seed and CSV checksums |
| `results/tables/`, `results/figures/` | Original simulated estimates and figures |
| `results/summary.json`, `results/validation.json`, `results/environment.txt` | Original simulation summaries and checks |

Running the simulation replaces these legacy generated files. The published article reads the separate aggregate outputs in `results/real/`. Its current `index.qmd` and `build_preview.py` use those real results, so running `run.py` does not update the article's figures or numbers. There is no current article preview for the simulation.

## What the example illustrates

The fixed seed is `640006`. The panel contains 4,000 families of origin and 7,166 adult children. Parents share family income, and each adult child forms a separate family. The population relationship between lasting parental and child log income is set to 0.4.

The SQL query follows linked parents to their family incomes, removes duplicate family years from co-resident parents, averages each generation's income over the requested ages, and joins one row per child using both parts of the person identifier. All three comparisons use the same children:

* One year for parents when the child is 15 and one year for the adult child at 40.
* Average parental income when the child is 15 to 19 and average adult child income at 40 to 44.
* The same parental average and average adult child income at 25 to 29.

All incomes are positive constant dollar values, and every requested year is observed. Temporary income noise makes one year a noisy measure of lasting income. A changing loading on lasting child status creates the early career age pattern by construction. Neither mechanism is estimated from survey data in this example.

`run.py` checks compound identifiers, foreign keys, parent links and positive incomes. It independently rebuilds 23 matches with pandas, checks the effect of removing `DISTINCT`, verifies OLS slopes with the covariance formula, and checks the simulated age mechanism without annual shocks. Results are saved in `results/validation.json`.

The simplified layout has annual interviews, income in the same calendar year, complete histories and no survey weights. The original regressions report no standard errors. For the article's real data timing, minimum observation requirements, common sample and uncertainty estimates, use [README-real.md](README-real.md) and `real_analysis.py`.

# Touchline — Premier League Player Intelligence

A local Streamlit scouting dashboard for comparing **listed market values** with performance-based model estimates. Includes a redesigned dark interface, search and filters, held-out valuation plots, player dossiers, position/season percentiles, four-player comparisons, scenario estimates, CSV exports and model/data diagnostics.

## Start on Windows / PyCharm

Requires Python 3.10 or newer. Extract this project, open its folder in PyCharm, and use the terminal inside the project directory:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. No API key is needed for the included demo. macOS/Linux: activate with `source .venv/bin/activate` instead.

## What the supplied data can establish

**The included 40-player dataset is synthetic.** Real names are paired with random, formula-generated performance and values. The 2024 season label, clubs and approximate ages belong to that demonstration; they are not a current roster or verified current market data. The app prominently labels synthetic data, including processed copies with provenance.

The Live football workspace fetches stats and matches on request after API setup. The Valuation workspace uses its selected CSV; fetching live results does not replace that CSV. Imported valuation data is labeled as unverified rather than automatically called current.

A model trained on Transfermarkt estimates learns patterns in those estimates. It cannot prove an objective fair value or that Transfermarkt is wrong. Actual transfer fees are another target and are not interchangeable with market estimates. A large model gap is a research lead, not a definitive bargain/overvaluation label.

## Reliability changes

- Existing player predictions come from **held-out evaluation**, never the final model trained on that player's target.
- Default: five player-group folds. Every season of a player stays in one fold. Complete stable IDs are preferred; otherwise exact normalized names define groups. Homonyms/alias changes still need a verified ID mapping.
- Optional: forward-by-season validation. Earlier seasons train the model; the next season is tested. The first season has no prediction. Earlier observations of the same player may be used. This measures a different task from unseen-player generalization.
- Numeric scaling is fitted inside each training fold. Only age, goals, assists, appearances and position enter the model; the target and extra columns cannot leak through a passthrough transformer.
- A fixed Ridge model (alpha=10) limits unstable coefficients in a tiny dataset. There is no claim that it is the optimal model. Estimates below zero are clipped at zero, consistently in evaluation and scenarios. Extreme extrapolation can still be misleading.
- Held-out MAE, RMSE, R², fold errors and errors by position are reported. A position-median baseline is computed using each fold's training rows only. Positive baseline improvement means lower model MAE.
- The final scenario model is fitted on all validated rows only after evaluation. Its fitted outputs are never presented as held-out accuracy.
- Strict input checks reject nonfinite/missing numbers, nonpositive values, impossible counts, unknown positions and duplicate player-seasons. Errors are surfaced for correction rather than silently dropping rows or replacing missing with zero.
- Market-value merges require season and exact identity, with one-to-one validation. Fuzzy matching and silent unmatched-player drops have been removed.
- If snapshot dates are supplied, statistics after the valuation date are rejected. When dates are absent, the app warns that alignment is unverified. Calendar-season splitting does not prove exact temporal validity; inspect dates and ensure training valuation snapshots predate the intended forecast cutoff.
- No calibrated prediction intervals are claimed. MAE is an aggregate error, not a per-player confidence interval. Percentile profiles describe the supplied peer sample, not league-wide quality.

Validation methodology references: [scikit-learn grouped cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html) and [preventing preprocessing leakage](https://scikit-learn.org/stable/common_pitfalls.html).

## CSV contract

One row per player per league season. Aggregate club stints before import; do not duplicate season totals for each club. Consistent observation dates and competition scope are essential.

| Column | Required | Format |
|---|---|---|
| name | Yes | Player name, nonblank |
| team | Yes | Club or explicitly aggregated club label |
| position | Yes | Attacker, Midfielder, Defender, Goalkeeper; FW/MF/DF/GK accepted |
| season | Yes | Start year, e.g. 2025 for 2025/26 |
| age | Yes | Age at a consistent reference date, 14–50 |
| appearances | Yes | Nonnegative whole league appearances, at most 42 |
| goals, assists | Yes | Nonnegative whole season counts; unknown is not zero |
| transfer_value_eur | Yes | Positive raw EUR number, e.g. 35000000; no € sign or “35m” |
| player_id | Recommended | Complete stable identity, same ID namespace across sources |
| stats_as_of | Recommended | ISO date of statistics cutoff |
| valuation_date | Recommended | ISO date of the market-value snapshot |
| value_source | Recommended | Source of market valuation |
| data_kind | Recommended | Use synthetic for demo data; otherwise identify provenance |

A header-only import template is available in Model & data quality. At least 10 distinct players are required to run; this is a technical minimum, **not** sufficient evidence of accuracy. Aim for hundreds of players across multiple seasons and a meaningful latest-season holdout.

Additional columns are preserved in exports but **not automatically used** as model inputs. This avoids inadvertently adding future information or target proxies. Very large files will increase memory use; this is a local research app, not a hosted multi-user service.

## Best next CSVs to provide

1. Historical player market values with stable IDs, valuation dates, currency and source. Match stats windows to those dates. If the goal is today's valuation, do not use end-of-season stats from after today's cutoff.
2. Complete Premier League player coverage and minutes, including low-scoring midfielders, defenders and goalkeepers. A scorers leaderboard is a selected sample and cannot represent the league.
3. Role-specific performance: xG, non-penalty xG, xA, shots, progressive passes/carries, defensive actions and goalkeeper saves/PSxG. Include season totals and minutes so per-90 rates can be derived properly with low-minutes safeguards.
4. Contract months remaining, injury availability, age at snapshot and historical club/league context. These influence market estimates beyond performance.

Once supplied, extend the feature schema deliberately, compare suitable models within training-only selection, and evaluate once on an untouched time holdout. Without real targets and aligned stats, improved code cannot establish real-world precision.

## Optional API pipeline

Copy `.env.example` to `.env` and set your football-data.org key. Provide `data/transfer_values.csv` with `season,transfer_value_eur` and either the same `player_id` namespace or exact `name`. `valuation_date` and `value_source` are preserved when supplied. Explicit cross-provider mapping is required; Transfermarkt IDs and football-data.org IDs are not interchangeable.

```bash
python main.py --mode live --seasons 2024 2025
```

This fetches **scorers**, not full squad statistics. Historical access and fields depend on the provider subscription. Missing API stats remain missing and must be resolved before modeling. Requests have a timeout and explicit rate-limit errors; no live authenticated request was tested during this update. Recorded `retrieved_at` is the fetch time, not the statistics cutoff. Historical ages in this basic collector use an August 1 approximation; supply precise snapshot ages for research.

See the provider's [official documentation](https://docs.football-data.org/) for endpoint behavior and access. The scorer endpoint is a leaderboard and defaults to a limited result set; increasing its limit does not create full league coverage.

Offline pipeline and CLI:

```bash
python main.py --mode demo
python -m src.predict "Erling Haaland" --season 2024
```

The pipeline creates `data/processed_dataset.csv`, `data/held_out_predictions.csv`, `data/evaluation.json`, and a final `model.joblib`. Demo mode remains labeled synthetic. Do not load untrusted joblib files. The CLI recalculates held-out evaluation from the CSV and requires unambiguous exact names.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover player-group separation, forward-season ordering, held-out error calculation, target exclusion, invalid inputs, duplicate rows, exact season-aware joins, date leakage, dashboard rendering, empty search results and scenario submission. See `VALIDATION.md` for the checks and demo metrics recorded for this update.

## New: Live football workspace

Choose **Live football** in the sidebar. It runs independently of the valuation CSV and does not train a model just to show fixtures.

1. Register at https://www.football-data.org/client/register and obtain your API token.
2. Copy `.env.example` to `.env` beside `app.py`; set `FOOTBALL_DATA_API_KEY=your_token_here` and save. On Windows, ensure the filename is `.env`, not `.env.txt`.
3. Open **API setup → Test API connection**. No key needs to be pasted into chat or source code. The app reads the file again when it makes a request. An environment variable with the same name takes precedence over the file.
4. Open **Recent matches → Load / refresh matches**. Past week includes today and the preceding six UTC calendar dates. Next week and custom ranges up to 31 days are available. Filter clubs and statuses without another API request; expand cards for half-time score, officials and venue when supplied. Download the visible matches as CSV.
5. Open **Current-season stats → Load / refresh current-season stats**. The app gets `currentSeason.startDate` from the provider and requests that season explicitly. No season year is hardcoded. The provider's current season can be its newest scheduled season even before play starts; an empty scorer list is handled explicitly.
6. Download the stats CSV, or upload matching market values in this tab to prepare a valuation CSV. Supply missing appearances and other unknown fields before modeling. Switch to **Valuation workspace** and upload the prepared CSV to replace the demo in that workspace.

The match snapshot and valuation dataset are separate: refreshing fixtures does not update player valuations. Early-season totals are not directly comparable to full-season totals; current data alone does not fix exposure bias. Train on matched observation windows and add minutes/per-90 metrics in a future feature update before relying on current-season valuations.

The free tier advertises fixtures, delayed scores and 10 calls/minute. Scorers, historical seasons and deeper fields may require additional access. A successful connection test does not guarantee every endpoint is enabled. Authentication, permission, rate-limit and network failures get distinct readable errors. See https://www.football-data.org/pricing for current details.

Responses stay in the current Streamlit session until replaced or the session ends; changing filters makes no API calls. Refreshing is explicit, with a 15-second guard between fetch actions. Selected date ranges are shown alongside fetch time so retained snapshots are not mistaken for new results. The guard does not coordinate multiple app users; this remains a local research tool. Null scores display `vs`, not a fabricated 0–0. No API key is stored in downloads, request URLs or error output.

References: https://docs.football-data.org/general/v4/competition.html and https://docs.football-data.org/general/v4/lookup_tables.html.

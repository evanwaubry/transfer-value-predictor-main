# Validation record

## Completed checks

- 14 automated tests passed (`python -m pytest -q` from project root).
- Streamlit AppTest rendered all five tabs, handled empty search results, submitted the scenario form, and displayed a useful error for single-season forward evaluation.
- CLI demo training and exact-player held-out prediction completed successfully.
- Grouped validation keeps all seasons of each player outside their test fold's training data.
- Forward validation trains on earlier seasons only; earliest-season predictions stay missing.
- Tested missing/nonfinite/invalid numbers, duplicate identities, exact season-aware joins, temporal snapshot rejection and target exclusion from features.
- Two test-fixture pandas dtype warnings do not affect app execution or test results.

## Demo-only evaluation

40 synthetic rows; five player-held-out folds, each 32 training / 8 test rows.

| Metric | Result |
|---|---:|
| MAE | €4,638,583 |
| RMSE | €5,939,943 |
| R² | 0.8495 |
| Position-median baseline MAE | €5,639,050 |
| MAE improvement over baseline | 17.7% |

These values measure recovery of the synthetic generator's patterns. They do not establish real player pricing accuracy. The model still lacks minutes, defensive/goalkeeping performance, contracts, injuries and verified dated targets.

## Verification limits

No authenticated live API call or real market-value dataset was available. Browser installation failed on download, so screenshot-based layout inspection was not completed. Streamlit's interaction test runner successfully executed the interface. Dependency ranges are provided, and the versions used for verification are listed below; every version combination in those ranges was not tested.

## Environment package versions

- python-dotenv: 1.2.3
- streamlit: 1.64.0
- plotly: 7.1.0
- pandas: 2.2.3
- numpy: 2.3.5
- scikit-learn: 1.8.0
- pytest: 9.1.1

## Live football update

22 tests passed after adding the API client and live workspace. New checks cover automatic provider season selection, inclusive UTC date filtering and deduplication, zero versus missing scores, safe 401/403/429/server errors, and the live tab workflow with a mocked match response. The demo CLI still completes successfully. Live authenticated data was not fetched because no user API key is configured; mocked responses verify handling, not provider access or data freshness.

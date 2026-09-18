# Deploying Touchline to Vercel

The project now has two front ends that share the same model code:

- **`app.py`** — the original Streamlit dashboard, for local use (`streamlit run app.py`).
- **`public/` + `api/`** — a static HTML/JS dashboard backed by two Vercel Python
  serverless functions. This is the one to deploy to Vercel.

Streamlit itself can't run on Vercel (it needs a persistent server), so the
serverless version reimplements the same UI as a plain web app: `public/index.html`,
`style.css`, and `app.js` render everything, and call `/api/analyze` and `/api/live`
for the actual model/data work. The Ridge regression, validation logic, and CSV
schema checks are untouched — reused directly from `src/model.py` and
`src/data_processing.py`.

## 1. Push this project to GitHub

Vercel deploys from a Git repository. Commit these new files along with the rest
of the project:

```
api/analyze.py
api/live.py
api/requirements.txt
public/index.html
public/style.css
public/app.js
public/data/sample_dataset.csv
vercel.json
.vercelignore
```

## 2. Import the project in Vercel

1. Go to [vercel.com/new](https://vercel.com/new) and import the GitHub repo.
2. Framework preset: leave as **Other** (no build step is needed — `vercel.json`
   already points Vercel at the `public/` folder for static files).
3. Deploy. Vercel will detect `api/analyze.py` and `api/live.py` and build them as
   Python serverless functions using `api/requirements.txt`.

## 3. (Optional) Enable Live Football

The Live Football tab proxies [football-data.org](https://www.football-data.org/client/register)
so your API key never reaches the browser.

1. Create a free account at football-data.org and copy your API token.
2. In your Vercel project: **Settings → Environment Variables**.
3. Add `FOOTBALL_DATA_API_KEY` = `<your token>` for the Production (and Preview)
   environment.
4. Redeploy. Test it from the app's **Live football → API setup → Test API
   connection** button.

Without this variable, the Valuation workspace still works fully (it doesn't need
any API key) — only the Live Football tab is affected.

## 4. What each new file does

| File | Purpose |
|---|---|
| `api/analyze.py` | POST endpoint: validates an uploaded CSV, runs the Ridge model with the chosen validation strategy, and returns metrics, per-row predictions, and the fitted model's coefficients as JSON. |
| `api/live.py` | GET endpoint: proxies football-data.org matches/scorers/test-connection, keeping the API key server-side. |
| `public/index.html` | Dashboard layout: sidebar filters, tabs (Market overview, Scouting table, Player dossier, Compare, Scenario lab, Model & data quality), Live football view. |
| `public/style.css` | Dark, "Touchline"-branded styling. |
| `public/app.js` | All client logic: fetches `/api/analyze` and `/api/live`, renders charts (Chart.js), tables, and the interactive Scenario Lab (computed instantly in the browser from the model coefficients returned by `/api/analyze`, so it never needs a second API round trip). |
| `vercel.json` | Tells Vercel the static site root is `public/` and gives the Python functions more memory/time for the CSV evaluation step. |

## 5. Local testing before deploying

You can test the serverless functions locally with the [Vercel CLI](https://vercel.com/docs/cli):

```bash
npm i -g vercel
vercel dev
```

This serves `public/` and runs `api/analyze.py` / `api/live.py` locally at
`http://localhost:3000`, exactly as they'll behave in production.

## 6. Extending the GUI further

Since everything is plain HTML/CSS/JS with no build step, you (or an AI coding
tool) can keep iterating directly on `public/index.html`, `style.css`, and
`app.js` — add new charts, animations, a real client-side router, drag-and-drop
CSV upload, saved views, etc. — without touching the Python model code at all,
as long as the request/response shape to `/api/analyze` and `/api/live` stays the
same (documented at the top of each file in `api/`).

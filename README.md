# Wind forecasts for day-ahead purchases

Web application for the buying team of a UK energy utility. For a purchase decision made the day before delivery, it shows **the latest national wind forecast available at that moment** and **how accurate such forecasts were**, so the buyer can size the power to buy beyond wind generation.

- Data: Elexon BMRS only, national level: `FUELHH` (actual wind generation) and `WINDFOR` (wind forecasts, with their publish time).
- Scope: purchase decisions made in **January 2026** (delivery days 2 January to 1 February 2026).
- Stack: Python (Django REST Framework) API, React + TypeScript front end (Vite, Recharts), Docker.

**Live app:** _add the Vercel URL of the front end_
**API:** _add the Vercel URL of the backend_ (try `/api/meta/`)
**Demo video:** _add the unlisted YouTube link_

## What the application shows

1. **Forecast at the purchase deadline.** Pick a delivery day and a deadline (default 09:00 UK time, day before). For every half-hour, the chart shows the most recent forecast published before the deadline, next to the actual generation, with the day's bias, typical error and relative error.
2. **Accuracy over January.** The same indicators for the whole month, the error and bias day by day (click a day to open it above), and a comparison of the error for deadlines from 06:00 to 21:00.

Errors are `forecast - actual`: a positive bias means the forecast was too high, so the buyer would have bought too little.

## What the data says (deadline 09:00, 1,488 half-hour slots)

| Indicator | Value |
|---|---|
| Bias | +1,748 MW (forecasts too high) |
| Typical error (MAE) | 2,042 MW |
| Large misses (RMSE) | 2,509 MW |
| Error relative to output (wMAPE) | 18.1 % |

- The error is mostly a **systematic overestimate**, so a buyer who does not correct for it systematically buys too little.
- Day to day it varies a lot: 19 January was the best day (MAE 743 MW), 28 January the worst (forecast too high by 5,375 MW on average, 93 % of that day's output).
- **Deciding later helps only a little**: with an 18:00 deadline the MAE is 1,877 MW (16.6 %), against 2,042 MW (18.1 %) at 09:00.

These figures come from one month and one data source: read them as a pilot result, not a general rule.

## Files and directories

| Path | Purpose |
|---|---|
| `backend/` | Django REST API, ingestion script, data files, tests. See [backend/README.md](backend/README.md) for details, endpoints and assumptions |
| `backend/forecasts/services.py` | Business logic: decision deadline, forecast selection, error metrics |
| `backend/scripts/ingest_elexon.py` | Downloads FUELHH and WINDFOR from Elexon into `backend/data/` |
| `backend/data/` | Ingested data (committed so the deployed API can read it) |
| `frontend/` | React + TypeScript application (Vite) |
| `frontend/src/api.ts` | Typed calls to the API |
| `frontend/src/App.tsx` | Page layout; holds the delivery day and deadline shared by both views |
| `frontend/src/components/ForecastView.tsx` | Forecast at the deadline for one delivery day |
| `frontend/src/components/AccuracyView.tsx` | Accuracy over the month and comparison of deadlines |
| `docker-compose.yml` | Runs API and web app together |
| `backend/Dockerfile`, `frontend/Dockerfile` | Container images (the front end is served by nginx, which forwards `/api` to the API) |

## Start the application

### With Docker

```bash
docker compose up --build
```

- Web app: http://localhost:8080
- API: http://localhost:8000/api/meta/

### Without Docker

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py test               # 20 tests
python manage.py runserver          # http://127.0.0.1:8000/api/meta/
```

Front end (Node 22), in a second terminal:

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173, /api is forwarded to port 8000
```

The data is already in `backend/data/`. To download it again from Elexon (needs internet access): `python scripts/ingest_elexon.py` in `backend/`.

## Deployment (Vercel)

Two Vercel projects from the same repository:

1. **Backend**: root directory `backend`. `vercel.json` routes every request to `api/index.py` and bundles `data/`. Vercel does not run Docker; the Dockerfiles are for local use.
2. **Front end**: root directory `frontend`, with the environment variable `VITE_API_URL` set to the backend URL (no trailing slash).

## Key assumptions

- The purchase deadline is 09:00 UK time on the day before delivery. It can be changed in the interface; the real deadline is to be confirmed with the client.
- For each half-hour, the forecast used is the one with the latest publish time not after the deadline.
- WINDFOR forecasts are hourly while FUELHH actuals are half-hourly: the half-hour at HH:30 reuses the forecast of HH:00.

More detail on assumptions and metrics is in [backend/README.md](backend/README.md).

## AI tools

_Edit this section so it is accurate._ Claude (Anthropic) was used as an assistant during development, for example to debug the front end, design the views and write documentation. All code was reviewed and run by the author.

## Data attribution

Contains BMRS data © Elexon Limited copyright and database right. See the BMRS Data Licence.
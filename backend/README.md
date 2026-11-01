# Wind forecast API (backend)

Django REST Framework API for a UK energy utility buying power on the day-ahead market. It answers two questions, using Elexon BMRS national wind data only (FUELHH actuals, WINDFOR forecasts), for purchase decisions made in January 2026:

1. What is the **latest wind forecast available** when the purchase decision has to be made?
2. How **accurate** have those forecasts been?

## Files

| Path | Purpose |
|---|---|
| `windapp/` | Django project (settings, urls, wsgi). No database. |
| `forecasts/data.py` | Loads the ingested files into memory; `latest_forecast()` picks the forecast known at a given time |
| `forecasts/services.py` | Business logic: decision deadline, half-hour slots, error metrics, accuracy breakdowns |
| `forecasts/serializers.py` | Query-parameter validation (scope: decisions made in January 2026) |
| `forecasts/views.py`, `urls.py` | The three endpoints |
| `forecasts/tests.py` | Unit and API tests |
| `scripts/ingest_elexon.py` | Downloads data from Elexon into `data/` |
| `data/` | `actuals.json`, `forecasts.json`, `meta.json` (generated, committed so the deployed app can read them) |
| `api/index.py`, `vercel.json` | Vercel entry point and config |
| `Dockerfile`, `docker-compose.yml` | Local container run |

## Start the application

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/ingest_elexon.py        # once: needs internet access to Elexon
python manage.py test                  # 20 tests
python manage.py runserver             # http://127.0.0.1:8000/api/meta/
```

With Docker (after ingesting the data):

```bash
docker compose up --build              # http://localhost:8000/api/meta/
```

## Endpoints (all GET, JSON, MW)

| Endpoint | Parameters | Returns |
|---|---|---|
| `/api/meta/` | none | Scope, default deadline, error definition |
| `/api/forecast/` | `delivery_date` (YYYY-MM-DD), `cutoff` (HH:MM, optional) | For each half-hour of the delivery day: latest forecast published at or before the deadline, its `publish_time`, its horizon, and the `actual_mw` for comparison |
| `/api/accuracy/` | `delivery_from`, `delivery_to`, `cutoff` (all optional) | Overall error metrics plus breakdowns by day, hour of day, and forecast horizon |

Errors are `forecast - actual`: a positive bias means forecasts were too high (the buyer would have bought too little).
Metrics: MAE, RMSE, bias, and wMAPE (total absolute error as a percentage of total actual generation).

## Key assumptions

- **Decision deadline**: 09:00 UK time on the day before delivery (query parameter `cutoff`). This is an assumption to confirm with the client.
- **Scope**: decisions made on 1-31 January 2026, so delivery days are 2 January to 1 February 2026.
- **Forecast selection**: for each half-hour slot, the forecast with the greatest `publishTime` not after the deadline. Forecasts published later are never used.
- **Hourly forecasts vs half-hourly actuals**: WINDFOR forecasts all start on the hour (verified on the ingested data), while FUELHH actuals are every 30 minutes. A half-hour slot at HH:30 therefore reuses the forecast of its hour (HH:00). Without this, half of the slots had no forecast. The forecast is compared with the half-hour actual, which adds some noise compared with averaging the two half-hours.
- `by_horizon` uses every published forecast (not only the one selected at the deadline) to show how error grows with lead time.
- Forecasts published more than 72 hours ahead are dropped at ingestion (`--max-horizon-hours`) to keep the data files small.

## Deploy on Vercel

Set the Vercel project root to this directory. `vercel.json` routes every request to `api/index.py`, which exposes the Django WSGI app, and bundles `data/`. Vercel does not run Docker, so the Dockerfile is for local use only.

Live app and front end: see the [main README](../README.md)

## AI tools

See the [main README](../README.md#ai-tools)

## Data attribution

Contains BMRS data © Elexon Limited copyright and database right. See the BMRS Data Licence.
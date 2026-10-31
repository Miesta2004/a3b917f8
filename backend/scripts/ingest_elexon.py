#!/usr/bin/env python
"""Download wind actuals (FUELHH) and wind forecasts (WINDFOR) from Elexon BMRS into data/*.json.

Public API, no key needed. Standard library only.

    python scripts/ingest_elexon.py                    # decisions in January 2026
    python scripts/ingest_elexon.py --max-horizon-hours 96

Output files use epoch seconds (UTC): {"fields": [...], "rows": [[...], ...]}.
Data: BMRS, (c) Elexon Limited. Keep the attribution required by the BMRS Data Licence.
"""
import argparse
import json
import sys
import time as time_mod
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DEFAULT_BASE = "https://data.elexon.co.uk/bmrs/api/v1"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_json(url, params, retries=3):
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(f"{url}?{query}", headers={"Accept": "application/json", "User-Agent": "wind-forecast-challenge"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            return payload["data"] if isinstance(payload, dict) and "data" in payload else payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == retries:
                raise SystemExit(f"Request failed after {retries} attempts: {request.full_url}\n{exc}")
            time_mod.sleep(2 * attempt)


def to_ts(text):
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


def days(first, last):
    while first <= last:
        yield first
        first += timedelta(days=1)


def fetch_actuals(base, first, last):
    rows = {}
    for day in days(first, last):
        records = get_json(
            f"{base}/datasets/FUELHH/stream",
            {"settlementDateFrom": day.isoformat(), "settlementDateTo": day.isoformat(), "fuelType": "WIND"},
        )
        for r in records:
            if r.get("fuelType") != "WIND":
                continue
            start, published = to_ts(r["startTime"]), to_ts(r["publishTime"])
            if start not in rows or published >= rows[start][0]:  # keep the latest revision
                rows[start] = (published, float(r["generation"]))
        print(f"  actuals {day}: {len(records)} records", file=sys.stderr)
    return sorted([s, g] for s, (_, g) in rows.items())


def fetch_forecasts(base, publish_first, publish_last, target_lo, target_hi, max_horizon_hours):
    rows = {}
    for day in days(publish_first, publish_last):
        start_of_day = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        records = get_json(
            f"{base}/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": start_of_day.strftime("%Y-%m-%dT%H:%MZ"),
                "publishDateTimeTo": (start_of_day + timedelta(days=1) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%MZ"),
            },
        )
        for r in records:
            start, publish = to_ts(r["startTime"]), to_ts(r["publishTime"])
            horizon_hours = (start - publish) / 3600
            if target_lo <= start < target_hi and 0 <= horizon_hours <= max_horizon_hours:
                rows[(start, publish)] = float(r["generation"])
        print(f"  forecasts published {day}: {len(records)} records", file=sys.stderr)
    return sorted([s, p, g] for (s, p), g in rows.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--decisions-from", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--decisions-to", type=date.fromisoformat, default=date(2026, 1, 31))
    parser.add_argument("--max-horizon-hours", type=float, default=72, help="drop forecasts published further ahead than this")
    args = parser.parse_args()

    delivery_first, delivery_last = args.decisions_from + timedelta(days=1), args.decisions_to + timedelta(days=1)
    target_lo = int(datetime.combine(delivery_first, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    target_hi = int(datetime.combine(delivery_last + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())

    print("Fetching actuals (FUELHH, WIND)...", file=sys.stderr)
    actuals = fetch_actuals(args.base_url, delivery_first, delivery_last)
    print("Fetching forecasts (WINDFOR)...", file=sys.stderr)
    forecasts = fetch_forecasts(args.base_url, args.decisions_from - timedelta(days=1), args.decisions_to, target_lo, target_hi, args.max_horizon_hours)

    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "actuals.json").write_text(json.dumps({"fields": ["start", "generation_mw"], "rows": actuals}, separators=(",", ":")))
    (DATA_DIR / "forecasts.json").write_text(json.dumps({"fields": ["start", "publish", "generation_mw"], "rows": forecasts}, separators=(",", ":")))
    (DATA_DIR / "meta.json").write_text(
        json.dumps(
            {
                "source": "Elexon BMRS (FUELHH, WINDFOR). Contains BMRS data (c) Elexon Limited.",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "decisions": [args.decisions_from.isoformat(), args.decisions_to.isoformat()],
                "max_horizon_hours": args.max_horizon_hours,
                "actual_rows": len(actuals),
                "forecast_rows": len(forecasts),
            },
            indent=2,
        )
    )
    print(f"Wrote {len(actuals)} actuals and {len(forecasts)} forecasts to {DATA_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
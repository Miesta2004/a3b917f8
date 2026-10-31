"""Business logic: which forecast was available at decision time, and how accurate was it."""
from datetime import datetime, time, timedelta, timezone
from math import sqrt
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")  # the client buys in UK local time
SLOT_SECONDS = 1800  # one half-hour slot
HORIZON_BUCKET_HOURS = 6  # lead-time groups: 0-6h, 6-12h, ...
HORIZON_CAP_HOURS = 48  # everything beyond is grouped as '48h+'


# ---------------------------------------------------------------------------
# Part 1: time helpers and the forecast of one delivery day
# ---------------------------------------------------------------------------
def iso(ts):
    """Epoch seconds -> '2026-01-15T00:00:00Z', the format the front end will read."""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def _local_midnight(day):
    """Epoch seconds of 00:00 UK local time on a given date."""
    return int(datetime.combine(day, time(0), tzinfo=LONDON).timestamp())


def cutoff_ts(delivery_date, cutoff):
    """Purchase deadline: `cutoff` (UK local time, e.g. 09:00) on the day BEFORE delivery."""
    decision_day = delivery_date - timedelta(days=1)
    return int(datetime.combine(decision_day, cutoff, tzinfo=LONDON).timestamp())


def slots(delivery_date):
    """Start times of every half-hour slot of one UK delivery day (48 in January)."""
    start = _local_midnight(delivery_date)
    end = _local_midnight(delivery_date + timedelta(days=1))
    return range(start, end, SLOT_SECONDS)


def day_points(dataset, delivery_date, cutoff):
    """For each half-hour of the delivery day: the forecast the buyer could see at the deadline.

    Returns (deadline, points). Each point also carries the actual generation, so the
    front end can show 'what was forecast' next to 'what really happened'.
    """
    deadline = cutoff_ts(delivery_date, cutoff)
    points = []
    for start in slots(delivery_date):
        forecast = dataset.latest_forecast(start, deadline)  # (publish_time, mw) or None
        points.append(
            {
                "start_time": iso(start),
                "forecast_mw": forecast[1] if forecast else None,
                "publish_time": iso(forecast[0]) if forecast else None,
                "horizon_hours": round((start - forecast[0]) / 3600, 1) if forecast else None,
                "actual_mw": dataset.actuals.get(start),
            }
        )
    return deadline, points


# ---------------------------------------------------------------------------
# Part 2: how accurate were the forecasts?
# ---------------------------------------------------------------------------
def error_metrics(pairs):
    """Summarise a list of (forecast, actual) pairs, in MW.

    Error = forecast - actual: positive means the forecast was too high.
    """
    n = len(pairs)
    if n == 0:
        return {"n": 0, "mae_mw": None, "rmse_mw": None, "bias_mw": None, "wmape_pct": None}
    errors = [forecast - actual for forecast, actual in pairs]
    total_actual = sum(actual for _, actual in pairs)
    abs_sum = sum(abs(e) for e in errors)
    return {
        "n": n,
        "mae_mw": round(abs_sum / n, 1),  # typical size of the error
        "rmse_mw": round(sqrt(sum(e * e for e in errors) / n), 1),  # punishes big misses more
        "bias_mw": round(sum(errors) / n, 1),  # average direction: too high or too low
        "wmape_pct": round(100 * abs_sum / total_actual, 2) if total_actual > 0 else None,  # error as % of output
    }


def _days(first, last):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def accuracy(dataset, first_day, last_day, cutoff):
    """Error statistics over a range of delivery days.

    Each slot is judged on the forecast the buyer saw at the deadline (same rule as day_points).
    """
    overall, by_day, horizons = [], [], []
    by_hour = {h: [] for h in range(24)}
    by_horizon = {}
    missing = 0

    for day in _days(first_day, last_day):
        deadline = cutoff_ts(day, cutoff)
        day_pairs = []
        for start in slots(day):
            actual = dataset.actuals.get(start)
            forecast = dataset.latest_forecast(start, deadline)

            if forecast is not None and actual is not None:
                pair = (forecast[1], actual)
                day_pairs.append(pair)
                by_hour[datetime.fromtimestamp(start, LONDON).hour].append(pair)
                horizons.append((start - forecast[0]) / 3600)
            else:
                missing += 1  # no forecast yet, or no actual: cannot be scored

            # Error versus lead time: use EVERY published forecast, not only the deadline one.
            if actual is not None:
                for publish, generation in dataset.all_forecasts(start):
                    hours_ahead = (start - publish) / 3600
                    if hours_ahead >= 0:
                        bucket = min(int(hours_ahead // HORIZON_BUCKET_HOURS) * HORIZON_BUCKET_HOURS, HORIZON_CAP_HOURS)
                        by_horizon.setdefault(bucket, []).append((generation, actual))

        by_day.append({"delivery_date": day.isoformat(), **error_metrics(day_pairs)})
        overall.extend(day_pairs)

    def horizon_label(bucket):
        if bucket >= HORIZON_CAP_HOURS:
            return f"{bucket}h+"
        return f"{bucket}-{bucket + HORIZON_BUCKET_HOURS}h"

    return {
        "overall": {
            **error_metrics(overall),
            "slots_missing_data": missing,
            "mean_horizon_hours": round(sum(horizons) / len(horizons), 1) if horizons else None,
        },
        "by_day": by_day,
        "by_hour_of_day": [{"hour": h, **error_metrics(by_hour[h])} for h in range(24)],
        "by_horizon": [{"horizon": horizon_label(b), **error_metrics(by_horizon[b])} for b in sorted(by_horizon)],
    }
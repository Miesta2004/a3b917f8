from datetime import date, datetime, time, timezone
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from . import services
from .data import Dataset


def ts(day, hour, minute=0):
    return int(datetime(2026, 1, day, hour, minute, tzinfo=timezone.utc).timestamp())


SLOT = ts(15, 0)  # 2026-01-15 00:00Z, first slot of the delivery day
CUTOFF = time(9, 0)  # deadline: 2026-01-14 09:00 (UK time = UTC in January)


def dataset():
    return Dataset(
        actual_rows=[(SLOT, 1200), (SLOT + 1800, 1000)],
        forecast_rows=[
            (SLOT, ts(14, 6), 1000),  # available before the deadline
            (SLOT, ts(14, 8, 59), 1100),  # latest available: published one minute before the deadline
            (SLOT, ts(14, 10), 2000),  # published after the deadline: must be ignored
        ],  # WINDFOR is hourly: only slots on the hour carry forecasts
    )


class LatestForecastTests(SimpleTestCase):
    def test_picks_latest_published_before_deadline(self):
        publish, mw = dataset().latest_forecast(SLOT, services.cutoff_ts(date(2026, 1, 15), CUTOFF))
        self.assertEqual((publish, mw), (ts(14, 8, 59), 1100))

    def test_forecast_published_exactly_at_deadline_counts(self):
        ds = Dataset([], [(SLOT, ts(14, 9), 1500)])
        self.assertEqual(ds.latest_forecast(SLOT, ts(14, 9)), (ts(14, 9), 1500))

    def test_none_when_everything_is_published_late(self):
        ds = Dataset([], [(SLOT, ts(14, 10), 1500)])
        self.assertIsNone(ds.latest_forecast(SLOT, ts(14, 9)))


class HourlyForecastTests(SimpleTestCase):
    def test_half_hour_slot_falls_back_to_its_hour(self):
        ds = Dataset([], [(SLOT, ts(14, 6), 1000)])
        self.assertEqual(ds.latest_forecast(SLOT + 1800, ts(14, 9)), (ts(14, 6), 1000))

    def test_own_forecast_is_preferred_over_the_hour(self):
        ds = Dataset([], [(SLOT, ts(14, 6), 1000), (SLOT + 1800, ts(14, 6), 1500)])
        self.assertEqual(ds.latest_forecast(SLOT + 1800, ts(14, 9)), (ts(14, 6), 1500))

    def test_next_hour_is_not_borrowed(self):
        ds = Dataset([], [(SLOT, ts(14, 6), 1000)])
        self.assertIsNone(ds.latest_forecast(SLOT + 3600 + 1800, ts(14, 9)))


class MetricsTests(SimpleTestCase):
    def test_error_metrics(self):
        m = services.error_metrics([(110, 100), (80, 100)])  # errors +10, -20
        self.assertEqual(m["n"], 2)
        self.assertEqual(m["mae_mw"], 15.0)
        self.assertEqual(m["rmse_mw"], 15.8)
        self.assertEqual(m["bias_mw"], -5.0)
        self.assertEqual(m["wmape_pct"], 15.0)

    def test_empty(self):
        self.assertIsNone(services.error_metrics([])["mae_mw"])

    def test_day_has_48_slots(self):
        _, points = services.day_points(dataset(), date(2026, 1, 15), CUTOFF)
        self.assertEqual(len(points), 48)
        self.assertEqual(points[0]["forecast_mw"], 1100)
        self.assertEqual(points[0]["actual_mw"], 1200)
        self.assertEqual(points[1]["forecast_mw"], 1100)  # 00:30 reuses the forecast of its hour
        self.assertIsNone(points[5]["forecast_mw"])  # 02:30: nothing published for that hour

    def test_accuracy_uses_deadline_forecast_and_skips_missing(self):
        result = services.accuracy(dataset(), date(2026, 1, 15), date(2026, 1, 15), CUTOFF)
        overall = result["overall"]
        self.assertEqual(overall["n"], 2)  # errors: 1100-1200=-100 and 1100-1000=+100
        self.assertEqual(overall["bias_mw"], 0.0)
        self.assertEqual(overall["mae_mw"], 100.0)
        self.assertEqual(overall["slots_missing_data"], 46)

    def test_horizon_buckets_include_late_forecasts(self):
        result = services.accuracy(dataset(), date(2026, 1, 15), date(2026, 1, 15), CUTOFF)
        by_horizon = {b["horizon"]: b["n"] for b in result["by_horizon"]}
        # 3 forecasts x 2 half-hour slots (00:00 and 00:30). 06:00 -> 18h/18.5h -> 18-24h;
        # 08:59 and 10:00 -> 15h, 14h, 15.5h, 14.5h -> 12-18h
        self.assertEqual(by_horizon["12-18h"], 4)
        self.assertEqual(by_horizon["18-24h"], 2)
        self.assertEqual(sum(by_horizon.values()), 6)


@patch("forecasts.views.get_dataset", side_effect=lambda: dataset())
class ApiTests(SimpleTestCase):
    client = APIClient()

    def test_forecast_endpoint(self, _):
        r = self.client.get("/api/forecast/", {"delivery_date": "2026-01-15"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["decision_deadline"], "2026-01-14T09:00:00Z")
        self.assertEqual(r.json()["points"][0]["forecast_mw"], 1100)

    def test_custom_cutoff_changes_the_forecast(self, _):
        r = self.client.get("/api/forecast/", {"delivery_date": "2026-01-15", "cutoff": "07:00"})
        self.assertEqual(r.json()["points"][0]["forecast_mw"], 1000)

    def test_outside_january_decisions_is_rejected(self, _):
        self.assertEqual(self.client.get("/api/forecast/", {"delivery_date": "2026-03-01"}).status_code, 400)
        self.assertEqual(self.client.get("/api/forecast/", {"delivery_date": "2026-01-01"}).status_code, 400)

    def test_bad_cutoff_format_is_rejected(self, _):
        self.assertEqual(self.client.get("/api/forecast/", {"delivery_date": "2026-01-15", "cutoff": "9am"}).status_code, 400)

    def test_accuracy_endpoint(self, _):
        r = self.client.get("/api/accuracy/", {"delivery_from": "2026-01-15", "delivery_to": "2026-01-15"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["overall"]["n"], 2)

    def test_meta(self, _):
        self.assertEqual(self.client.get("/api/meta/").json()["default_cutoff"], "09:00")
"""Loads the Elexon data written by scripts/ingest_elexon.py and answers one key question:
"which forecast was known at a given moment?"

All timestamps are UTC epoch seconds (whole numbers): compact in the files and easy to compare.
"""
import json
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path

from django.conf import settings


class DataNotAvailable(Exception):
    """The ingested Elexon files are missing (the ingestion script has not been run)."""


class Dataset:
    def __init__(self, actual_rows, forecast_rows):
        # actual_rows:   (start, generation_mw)            e.g. (1768435200, 3120.0)
        # forecast_rows: (start, publish, generation_mw)   several per start: one per publication
        # Actuals: a dictionary start -> MW, for instant lookup.
        self.actuals = {int(s): float(g) for s, g in actual_rows}

        # Forecasts: group all publications of the same half-hour together...
        grouped = {}
        for start, publish, gen in forecast_rows:
            grouped.setdefault(int(start), []).append((int(publish), float(gen)))

        # ...then sort each group by publication time, oldest first.
        # self.forecasts[start] = ([publish times], [matching MW values])
        self.forecasts = {}
        for start, items in grouped.items():
            items.sort()
            self.forecasts[start] = ([p for p, _ in items], [g for _, g in items])

    def _entry(self, start):
        """Forecasts that apply to the half-hour slot `start`.

        WINDFOR publishes HOURLY forecasts (every startTime is on the hour, checked on the
        January 2026 data), while actual generation (FUELHH) is every 30 minutes.
        So a slot at HH:30 has no forecast of its own: it uses the forecast of its hour (HH:00).
        """
        return self.forecasts.get(start) or self.forecasts.get(start - start % 3600)

    def latest_forecast(self, start, cutoff):
        """Most recent forecast for the slot `start` published at or before `cutoff`.

        Returns (publish_time, mw), or None if no forecast existed yet at that time.
        This is the heart of the first requirement: only what the buyer could know counts.
        """
        entry = self._entry(start)
        if not entry:
            return None
        publishes, gens = entry
        # bisect_right = binary search: how many publications are <= cutoff?
        i = bisect_right(publishes, cutoff)
        return (publishes[i - 1], gens[i - 1]) if i else None

    def all_forecasts(self, start):
        """Every (publish_time, mw) for a slot. Used to study error versus lead time."""
        entry = self._entry(start)
        return list(zip(*entry)) if entry else []


def _read_rows(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["rows"]
    except FileNotFoundError as exc:
        # A clear message instead of a crash: the API turns this into an HTTP 503.
        raise DataNotAvailable(
            f"{Path(path).name} not found in {Path(path).parent}. Run scripts/ingest_elexon.py first."
        ) from exc


@lru_cache(maxsize=1)
def get_dataset():
    """Read the files once, then keep the result in memory for every later request."""
    data_dir = Path(settings.DATA_DIR)
    return Dataset(_read_rows(data_dir / "actuals.json"), _read_rows(data_dir / "forecasts.json"))
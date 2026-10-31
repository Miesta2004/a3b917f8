"""The three endpoints. A view receives the request, calls the logic, and returns JSON.

Flow for every request: validate the parameters -> load the data -> call services.py -> answer.
"""
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .data import DataNotAvailable, get_dataset
from .serializers import AccuracyQuerySerializer, ForecastQuerySerializer, delivery_bounds


def _dataset_or_503():
    """Return (dataset, None), or (None, error response) if the data files are missing."""
    try:
        return get_dataset(), None
    except DataNotAvailable as exc:
        return None, Response({"detail": str(exc)}, status=503)  # 503 = service unavailable


class MetaView(APIView):
    """GET /api/meta/ : what the API covers and how to read its numbers."""

    def get(self, request):
        first, last = delivery_bounds()
        return Response(
            {
                "decision_window": [d.isoformat() for d in settings.DECISION_WINDOW],
                "delivery_window": [first.isoformat(), last.isoformat()],
                "default_cutoff": settings.DEFAULT_CUTOFF.strftime("%H:%M"),
                "cutoff_timezone": "Europe/London",
                "units": "MW",
                "error_definition": "forecast - actual; positive means the forecast was too high",
            }
        )


class ForecastView(APIView):
    """GET /api/forecast/ : latest forecast available at the purchase deadline, per half-hour."""

    def get(self, request):
        query = ForecastQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)  # invalid input -> automatic HTTP 400

        dataset, error = _dataset_or_503()
        if error:
            return error

        day = query.validated_data["delivery_date"]
        cutoff = query.validated_data["cutoff"]
        deadline, points = services.day_points(dataset, day, cutoff)

        values = [p["forecast_mw"] for p in points if p["forecast_mw"] is not None]
        return Response(
            {
                "delivery_date": day.isoformat(),
                "decision_deadline": services.iso(deadline),
                "points": points,
                "summary": {
                    "slots_without_forecast": len(points) - len(values),
                    "mean_forecast_mw": round(sum(values) / len(values), 1) if values else None,
                    "min_forecast_mw": min(values) if values else None,
                    "max_forecast_mw": max(values) if values else None,
                },
            }
        )


class AccuracyView(APIView):
    """GET /api/accuracy/ : forecast error over a range of delivery days."""

    def get(self, request):
        query = AccuracyQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        dataset, error = _dataset_or_503()
        if error:
            return error

        q = query.validated_data
        result = services.accuracy(dataset, q["delivery_from"], q["delivery_to"], q["cutoff"])
        return Response(
            {
                "delivery_from": q["delivery_from"].isoformat(),
                "delivery_to": q["delivery_to"].isoformat(),
                "cutoff": q["cutoff"].strftime("%H:%M"),
                **result,
            }
        )
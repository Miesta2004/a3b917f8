"""Validation of the parameters sent in the URL (?delivery_date=...&cutoff=...).

    If something is wrong, Django REST Framework automatically answers with HTTP 400 and a message.
"""
from datetime import timedelta

from django.conf import settings
from rest_framework import serializers

ONE_DAY = timedelta(days=1)


def delivery_bounds():
    """Delivery dates in scope: the day after each decision date (decisions: 1-31 January)."""
    first_decision, last_decision = settings.DECISION_WINDOW
    return first_decision + ONE_DAY, last_decision + ONE_DAY


def check_delivery_date(value):
    first, last = delivery_bounds()
    if not first <= value <= last:
        raise serializers.ValidationError(
            f"Only decisions made in {settings.DECISION_WINDOW[0]:%B %Y} are in scope: "
            f"delivery dates must be between {first} and {last}."
        )
    return value


class CutoffField(serializers.TimeField):
    """Purchase deadline as 'HH:MM'. Optional: defaults to 09:00 (see settings.py)."""

    def __init__(self, **kwargs):
        super().__init__(input_formats=["%H:%M"], required=False, default=settings.DEFAULT_CUTOFF, **kwargs)


class ForecastQuerySerializer(serializers.Serializer):
    """Parameters of /api/forecast/ : one delivery day."""

    delivery_date = serializers.DateField(validators=[check_delivery_date])  # required
    cutoff = CutoffField()


class AccuracyQuerySerializer(serializers.Serializer):
    """Parameters of /api/accuracy/ : a range of delivery days (whole scope if omitted)."""

    delivery_from = serializers.DateField(required=False, validators=[check_delivery_date])
    delivery_to = serializers.DateField(required=False, validators=[check_delivery_date])
    cutoff = CutoffField()

    def validate(self, attrs):
        first, last = delivery_bounds()
        attrs.setdefault("delivery_from", first)
        attrs.setdefault("delivery_to", last)
        if attrs["delivery_from"] > attrs["delivery_to"]:
            raise serializers.ValidationError("delivery_from must not be after delivery_to.")
        return attrs
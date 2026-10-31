from django.urls import path

from . import views

urlpatterns = [
    path("meta/", views.MetaView.as_view()),  # scope and how to read the numbers
    path("forecast/", views.ForecastView.as_view()),  # latest forecast at the purchase deadline
    path("accuracy/", views.AccuracyView.as_view()),  # forecast error statistics
]
from django.urls import path

from applications.frontend.views import (
    ReportJokeView,
)

urlpatterns = [
    # Insult Reporting Endpoint
    path("insult", ReportJokeView.as_view(), name="report_joke")
]

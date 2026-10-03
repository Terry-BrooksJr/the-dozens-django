# applications/API/tests/urls.py
from django.http import HttpResponse
from django.urls import path


def dummy_report_view(request):
    return HttpResponse("ok")


urlpatterns = [
    # The form's __init__ calls reverse("report-list"), so provide a stub
    path("api/v1/reports/", dummy_report_view, name="report-list"),
]

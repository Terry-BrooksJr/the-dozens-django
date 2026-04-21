# applications/API/tests/admin_test_urls.py
#
# Minimal URL configuration used only by test_admin.py so that
# reverse("admin:API_*") resolves correctly inside unit tests that
# do not spin up the full ROOT_URLCONF.

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path

# Force admin autodiscover so all ModelAdmin instances are registered
# before any test tries to reverse an admin URL.
admin.autodiscover()


def _dummy(request):
    return HttpResponse("ok")


urlpatterns = [
    path("admin/", admin.site.urls),
    # Stub required by InsultReviewForm.__init__ → reverse("report-joke")
    path("report/", _dummy, name="report-joke"),
]

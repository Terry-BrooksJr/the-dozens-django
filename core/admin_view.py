from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse
import os


@staff_member_required
def grafana_dashboard_view(request):
    context = {
        **admin.site.each_context(request),
        "title": "Observability Dashboard",
        "grafana_url": (os.environ.get("GRAFANA_DASHBOARD_URL")),
    }
    return TemplateResponse(request, "admin/grafana_dashboard.html", context)

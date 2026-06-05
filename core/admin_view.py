from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse


@staff_member_required
def grafana_dashboard_view(request):
    context = {
        **admin.site.each_context(request),
        "title": "Observability Dashboard",
        "grafana_url": (
            "https://grafana.yo-momma.io/public-dashboards/3691683c85b749c989b9f3339b52a600"
        ),
    }
    return TemplateResponse(request, "admin/grafana_dashboard.html", context)

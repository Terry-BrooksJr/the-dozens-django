from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse


@staff_member_required
def grafana_dashboard_view(request):
    context = {
        **admin.site.each_context(request),
        "title": "Observability Dashboard",
        "grafana_url": (
            "https://brooksjr.grafana.net/public-dashboards/53837066b22a437db5eb980adfe484bc"
        ),
    }
    return TemplateResponse(request, "admin/grafana_dashboard.html", context)

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def grafana_dashboard_view(request):
    context = {
        "title": "Observability Dashboard",
        "grafana_url": (
            "https://brooksjr.grafana.net/public-dashboards/"
            "53837066b22a437db5eb980adfe484bc?var-DS_PROMETHEUS="
        ),
    }
    return render(request, "admin/grafana_dashboard.html", context)
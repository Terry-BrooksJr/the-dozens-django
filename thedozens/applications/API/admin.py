from django.contrib import admin

from .forms import invalidate_insult_cache
from .models import Insult


class InsultAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_insult_cache()


admin.site.register(Insult, InsultAdmin)

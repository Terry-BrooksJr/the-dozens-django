"""
applications.API.admin
This module registers the Insult and InsultReview models with the Django admin interface.
It provides custom admin interfaces for managing insults and their reviews, including inline editing of reviews within the Insult admin page.
It also includes functionality to invalidate the insult cache whenever an Insult is saved.
It uses Django's admin features to enhance the management of these models, making it easier for administrators
to view, edit, and manage insults and their associated reviews.
It also provides a link to view all reports associated with an insult directly from the Insult admin page.

"""

from django import forms as django_forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.db.models import Count, Q
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from .forms import invalidate_insult_cache
from .models import Insult, InsultCategory, InsultReview

# applications/API/admin.py


class RecategorizeForm(django_forms.Form):
    new_category = django_forms.ModelChoiceField(
        # objects.none() at class definition avoids evaluating the queryset at
        # import time (before migrations run, during test collection, etc.).
        # The live queryset is assigned in __init__ so every instantiation
        # hits the DB freshly and picks up any categories added at runtime.
        queryset=InsultCategory.objects.none(),
        label="New Category",
        help_text="Select the new category to assign to the selected insults.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_category"].queryset = InsultCategory.objects.all()


class InsultReviewInline(admin.TabularInline):  # Or admin.StackedInline for more detail
    """
    Provides an inline admin interface for editing InsultReview objects within the Insult admin page.

    This class allows administrators to view and edit reviews related to an insult directly from the insult's admin detail page.
    """

    model = InsultReview
    extra = 0  # Don't show extra empty forms


class HasPendingReviewFilter(admin.SimpleListFilter):
    """
    Provides a filter for the Insult admin to show insults with or without pending reviews.

    This filter allows administrators to quickly view insults that have at least one associated review with a pending status, or those with none.
    """

    title = "Has Pending Reviews"
    parameter_name = "has_pending_reviews"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has Pending Reviews"),
            ("no", "No Pending Reviews"),
        )

    def queryset(self, request, queryset):
        annotated_queryset = queryset.annotate(
            pending_review_count=Count("reports", filter=Q(reports__status="P"))
        )
        if self.value() == "yes":
            return annotated_queryset.filter(pending_review_count__gt=0)
        if self.value() == "no":
            return annotated_queryset.filter(pending_review_count=0)
        # If no filter is selected, return the original queryset
        return annotated_queryset


class InsultAdmin(admin.ModelAdmin):
    # inlines: ClassVar = [InsultReviewInline]
    list_display = (
        "insult_id",
        "reference_id",
        "nsfw",
        "added_by",
        "content",
        "category",
        "reports_count",
        "status",
        "view_reports_link",
    )
    actions = [
        "approve_insult",
        "remove_insult",
        "mark_insult_for_review",
        "reclassify_as_nsfw",
        "reclassify_as_sfw",
        "re_categorize",
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_insult_cache(reason="admin_save")

    # ------------------------------------------------------------------
    # Admin actions — delegate to model methods
    # ------------------------------------------------------------------

    @admin.action(description="Approve selected insults")
    def approve_insult(self, request, queryset):
        count = queryset.count()
        for insult in queryset:
            insult.approve_insult()
        self.message_user(request, f"{count} insult(s) approved successfully.")

    @admin.action(description="Remove selected insults (soft delete)")
    def remove_insult(self, request, queryset):
        count = queryset.count()
        for insult in queryset:
            insult.remove_insult()
        self.message_user(request, f"{count} insult(s) removed.")

    @admin.action(description="Mark selected insults for review")
    def mark_insult_for_review(self, request, queryset):
        count = queryset.count()
        for insult in queryset:
            insult.mark_insult_for_review()
        self.message_user(request, f"{count} insult(s) marked for review.")

    @admin.action(description="Reclassify selected insults as NSFW")
    def reclassify_as_nsfw(self, request, queryset):
        count = queryset.count()
        for insult in queryset:
            insult.reclassify(True)
        self.message_user(request, f"{count} insult(s) reclassified as NSFW.")

    @admin.action(description="Reclassify selected insults as SFW")
    def reclassify_as_sfw(self, request, queryset):
        count = queryset.count()
        for insult in queryset:
            insult.reclassify(False)
        self.message_user(request, f"{count} insult(s) reclassified as SFW.")

    def re_categorize(self, request, queryset):
        """Intermediate-form action: prompts for a new category before applying."""
        if request.POST.get("apply"):
            form = RecategorizeForm(request.POST)
            if form.is_valid():
                new_category = form.cleaned_data["new_category"]
                selected_ids = request.POST.getlist("_selected_ids")
                target_qs = Insult.objects.filter(pk__in=selected_ids)
                count = target_qs.count()
                for insult in target_qs:
                    insult.re_categorize(new_category)
                self.message_user(
                    request,
                    f"{count} insult(s) re-categorized to '{new_category}'.",
                )
                return None
        else:
            form = RecategorizeForm()

        return TemplateResponse(
            request,
            "admin/insult_re_categorize.html",
            {
                "title": "Re-categorize Insults",
                "insults": queryset,
                "form": form,
                "selected_ids": list(queryset.values_list("pk", flat=True)),
                "opts": self.model._meta,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
        )

    re_categorize.short_description = "Re-categorize selected insults"

    def view_reports_link(self, obj):
        """
        Returns an HTML link to the admin changelist for all reports associated with a specific insult.

        This method generates a clickable link labeled "View Reports" with the number of reports, allowing administrators to quickly access all reviews for the given insult.

        Args:
            obj: The Insult instance for which to generate the reports link.

        Returns:
            str: An HTML anchor tag linking to the filtered InsultReview admin changelist.
        """
        url = (
            reverse("admin:API_insultreview_changelist")
            + f"?insult__id__exact={obj.insult_id}"
        )
        return format_html('<a href="{}">View Reports ({})</a>', url, obj.reports_count)


class ManyReportsFilter(admin.SimpleListFilter):
    title = "Number of Reports"
    parameter_name = "many_reports"

    def lookups(self, request, model_admin):
        return (
            ("3+", "3 or more reports"),
            ("less", "Fewer than 3 reports"),
        )

    def queryset(self, request, queryset):
        # Note: queryset is for InsultReview
        if self.value() == "3+":
            return queryset.filter(insult__reports_count__gte=3)
        if self.value() == "less":
            return queryset.filter(insult__reports_count__lt=3)
        return queryset


class InsultReviewAdmin(admin.ModelAdmin):
    """
    Customizes the Django admin interface for InsultReview objects.

    This class defines how InsultReview entries are displayed, filtered, and searched in the admin panel.
    """

    list_display = ("id", "insult", "review_type", "status", "date_submitted")
    list_filter = (
        "review_type",
        "insult_reference_id",
        "status",
        ManyReportsFilter,
        "date_submitted",
    )
    search_fields = ("insult__content", "insult_reference_id", "review_type", "status")


admin.site.register(InsultReview, InsultReviewAdmin)
admin.site.register(Insult, InsultAdmin)

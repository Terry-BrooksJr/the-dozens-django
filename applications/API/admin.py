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
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from loguru import logger

from .emails import WelcomeEmail
from .forms import invalidate_insult_cache
from .models import Insult, InsultCategory, InsultReview

User = get_user_model()

# applications/API/admin.py


class RecategorizeForm(django_forms.Form):
    """Intermediate form for the admin "re-categorize" action.

    Presents a single category picker applied to every selected insult.
    """

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
        """Populate the category choices with a fresh queryset per instantiation."""
        super().__init__(*args, **kwargs)
        self.fields["new_category"].queryset = InsultCategory.objects.all()


class ModifyInsultForm(django_forms.Form):
    """Form for the admin "Modify" button: the edited joke plus the moderator's reason."""

    modified_content = django_forms.CharField(
        label="Modified Text",
        widget=django_forms.Textarea(attrs={"rows": 4, "cols": 80}),
        help_text="The joke as it should be published.",
    )
    reviewer_notes = django_forms.CharField(
        label="Reviewer Notes",
        widget=django_forms.Textarea(attrs={"rows": 4, "cols": 80}),
        help_text="Why the joke was changed. This is shown to the submitter.",
    )


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
        """Return the filter options shown in the admin sidebar."""
        return (
            ("yes", "Has Pending Reviews"),
            ("no", "No Pending Reviews"),
        )

    def queryset(self, request, queryset):
        """Filter insults by whether they have any pending reviews.

        The queryset is always annotated with ``pending_review_count``.
        """
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
    """Admin configuration for Insult moderation.

    Shows every insult regardless of status and exposes bulk actions for
    approving, removing, flagging, reclassifying, and re-categorizing.
    """

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
        "review_buttons",
    )
    readonly_fields = ("review_buttons",)
    search_fields = ("reference_id", "added_by__username", "added_by__email")
    list_filter = (HasPendingReviewFilter, "status", "nsfw", "category", "added_on")
    actions = [
        "approve_insult",
        "remove_insult",
        "mark_insult_for_review",
        "reclassify_as_nsfw",
        "reclassify_as_sfw",
        "re_categorize",
    ]

    def get_queryset(self, request):
        """Return all insults, bypassing the active-only default manager."""
        # The default manager is PublicInsultManager (active-only). Mirror what
        # super().get_queryset() does (ordering, etc.) but through the
        # unfiltered manager so every status is visible in the admin.
        qs = Insult.objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def save_model(self, request, obj, form, change):
        """Save the insult, then invalidate cached insult data."""
        super().save_model(request, obj, form, change)
        invalidate_insult_cache(reason="admin_save")

    # ------------------------------------------------------------------
    # Per-insult review buttons
    #   Pending - New:      Approve / Modify / Reject
    #   Flagged for Review: Reclassify / Recategorize / Remove / Do Nothing
    # ------------------------------------------------------------------

    # Success message shown for each review action; the keys are the
    # ``action`` values passed to _report_review_result().
    REVIEW_ACTION_MESSAGES = {
        "approved": "approved",
        "modified": "approved with modifications",
        "rejected": "rejected",
        "reclassified": "reclassified",
        "recategorized": "recategorized",
        "removed": "removed",
        "kept": "kept as-is and restored to the API",
    }

    def get_urls(self):
        """Add the single-insult review endpoints ahead of the default admin URLs."""

        def post_only(view):
            return self.admin_site.admin_view(require_POST(view))

        custom_urls = [
            # Pending - New
            path(
                "<int:insult_id>/approve/",
                post_only(self.approve_view),
                name="API_insult_approve",
            ),
            path(
                "<int:insult_id>/reject/",
                post_only(self.reject_view),
                name="API_insult_reject",
            ),
            path(
                "<int:insult_id>/modify/",
                self.admin_site.admin_view(self.modify_view),
                name="API_insult_modify",
            ),
            # Flagged for Review
            path(
                "<int:insult_id>/flagged/reclassify/",
                post_only(self.flagged_reclassify_view),
                name="API_insult_flagged_reclassify",
            ),
            path(
                "<int:insult_id>/flagged/recategorize/",
                self.admin_site.admin_view(self.flagged_recategorize_view),
                name="API_insult_flagged_recategorize",
            ),
            path(
                "<int:insult_id>/flagged/remove/",
                post_only(self.flagged_remove_view),
                name="API_insult_flagged_remove",
            ),
            path(
                "<int:insult_id>/flagged/keep/",
                post_only(self.flagged_keep_view),
                name="API_insult_flagged_keep",
            ),
        ]
        return custom_urls + super().get_urls()

    @admin.display(description="Review")
    def review_buttons(self, obj):
        """Render the review buttons for pending or flagged insults; blank otherwise.

        POST buttons use ``formaction`` so they post the surrounding admin form
        (changelist or change page), which already carries the CSRF token,
        instead of nesting a second ``<form>``. Buttons that need more input
        (Modify, Recategorize) are plain links to an intermediate form page.
        """
        if obj is None or obj.pk is None:
            return "-"

        style = "color:#fff;padding:4px 12px;margin:2px;border:0;display:inline-block;"

        def post_button(url_name, label, color):
            return format_html(
                '<button type="submit" formaction="{}" formnovalidate class="button" '
                'style="{}background:{};">{}</button>',
                reverse(f"admin:{url_name}", args=[obj.insult_id]),
                style,
                color,
                label,
            )

        def link_button(url_name, label, color):
            return format_html(
                '<a href="{}" class="button" style="{}background:{};">{}</a>',
                reverse(f"admin:{url_name}", args=[obj.insult_id]),
                style,
                color,
                label,
            )

        if obj.status == Insult.STATUS.PENDING:
            buttons = [
                post_button("API_insult_approve", "Approve", "#2e7d32"),
                link_button("API_insult_modify", "Modify", "#e69500"),
                post_button("API_insult_reject", "Reject", "#c62828"),
            ]
        elif obj.status == Insult.STATUS.FLAGGED:
            buttons = [
                post_button(
                    "API_insult_flagged_reclassify",
                    "Reclassify as SFW" if obj.nsfw else "Reclassify as NSFW",
                    "#6a1b9a",
                ),
                link_button(
                    "API_insult_flagged_recategorize", "Recategorize", "#1565c0"
                ),
                post_button("API_insult_flagged_remove", "Remove", "#c62828"),
                post_button("API_insult_flagged_keep", "Do Nothing", "#757575"),
            ]
        else:
            return "-"
        return format_html_join("", "{}", ((button,) for button in buttons))

    def _get_insult_in_status_or_redirect(self, request, insult_id, required_status):
        """Load an insult for review, enforcing change permission and its current status.

        Returns:
            tuple: ``(insult, None)`` when the insult can be reviewed, or
            ``(insult, redirect_response)`` when its status has already moved on
            (e.g. another moderator handled it first).
        """
        insult = get_object_or_404(Insult.objects.get_queryset(), pk=insult_id)
        if not self.has_change_permission(request, insult):
            raise PermissionDenied
        if insult.status != required_status:
            self.message_user(
                request,
                f"{insult.reference_id} is no longer "
                f"{Insult.STATUS(required_status).label}, so nothing was changed.",
                messages.WARNING,
            )
            return insult, self._redirect_back(request, insult)
        return insult, None

    def _redirect_back(self, request, insult):
        """Redirect to the same-host referer, falling back to the insult's change page."""
        referer = request.META.get("HTTP_REFERER")
        if referer and url_has_allowed_host_and_scheme(
            referer,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(referer)
        return redirect(reverse("admin:API_insult_change", args=[insult.insult_id]))

    def _report_review_result(self, request, insult, expected_status, action):
        """Confirm the model method actually changed the status and message the user.

        Every review button (pending and flagged) ends here, so this is the
        single place to hook result notifications.

        The model methods log failures instead of raising, so the saved status
        is the only reliable signal of success.

        Args:
            request: The admin request.
            insult: The reviewed insult.
            expected_status: The ``Insult.STATUS`` the action should have produced.
            action: What the moderator did; one of ``REVIEW_ACTION_MESSAGES``'
                keys: "approved", "modified", "rejected" (pending) or
                "reclassified", "recategorized", "removed", "kept" (flagged).

        Returns:
            bool: ``True`` when the insult reached ``expected_status``.
        """
        insult.refresh_from_db()
        if insult.status != expected_status:
            self.message_user(
                request,
                f"Could not update {insult.reference_id}. Check the server logs.",
                messages.ERROR,
            )
            return False

        invalidate_insult_cache(reason=f"admin_{action}")
        self.message_user(
            request,
            f"{insult.reference_id} {self.REVIEW_ACTION_MESSAGES[action]}.",
            messages.SUCCESS,
        )
        insult._notify_owner_joke_status_change(
            outcome=action,
            is_modified=insult.is_modified,
            modified_text=insult.modified_text,
            reviewers_notes=insult.reviewers_notes,
        )
        return True

    def _resolve_pending_reports(self, request, insult, resolve):
        """Close every pending InsultReview on this insult.

        Args:
            resolve: Callable taking ``(review, reviewer)`` that applies the
                matching ``InsultReview.mark_review_*`` method.
        """
        for review in insult.reports.filter(status=InsultReview.STATUS.PENDING):
            resolve(review, request.user)

    # -- Pending - New --------------------------------------------------

    def approve_view(self, request, insult_id):
        """Approve a single pending insult, then redirect back."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.PENDING
        )
        if response:
            return response
        insult.approve_insult()
        self._report_review_result(request, insult, Insult.STATUS.ACTIVE, "approved")
        return self._redirect_back(request, insult)

    def reject_view(self, request, insult_id):
        """Reject a single pending insult, then redirect back."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.PENDING
        )
        if response:
            return response
        insult.reject_insult()
        self._report_review_result(request, insult, Insult.STATUS.REJECTED, "rejected")
        return self._redirect_back(request, insult)

    def modify_view(self, request, insult_id):
        """Show the Modify form (GET) or approve the insult with the edits (POST)."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.PENDING
        )
        if response:
            return response

        if request.method == "POST":
            form = ModifyInsultForm(request.POST)
            if form.is_valid():
                insult.approve_with_modifications(
                    modified_content=form.cleaned_data["modified_content"],
                    reviewer_notes=form.cleaned_data["reviewer_notes"],
                )
                self._report_review_result(
                    request, insult, Insult.STATUS.ACTIVE, "modified"
                )
                return redirect(reverse("admin:API_insult_changelist"))
        else:
            form = ModifyInsultForm(
                initial={
                    "modified_content": insult.modified_content or insult.content,
                    "reviewer_notes": insult.reviewer_notes or "",
                }
            )

        return TemplateResponse(
            request,
            "admin/insult_modify.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Modify Insult {insult.reference_id}",
                "insult": insult,
                "form": form,
                "opts": self.model._meta,
            },
        )

    # -- Flagged for Review ---------------------------------------------

    def flagged_reclassify_view(self, request, insult_id):
        """Flip the NSFW flag on a flagged insult and restore it to the API."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.FLAGGED
        )
        if response:
            return response

        new_nsfw = not insult.nsfw
        insult.reclassify(new_nsfw)
        insult.refresh_from_db(fields=["nsfw"])
        if insult.nsfw != new_nsfw:
            self.message_user(
                request,
                f"Could not reclassify {insult.reference_id}. Check the server logs.",
                messages.ERROR,
            )
            return self._redirect_back(request, insult)

        insult.approve_insult()
        if self._report_review_result(
            request, insult, Insult.STATUS.ACTIVE, "reclassified"
        ):
            self._resolve_pending_reports(
                request,
                insult,
                lambda review, user: review.mark_review_reclassified(user),
            )
        return self._redirect_back(request, insult)

    def flagged_recategorize_view(self, request, insult_id):
        """Show the category picker (GET) or move the flagged insult and restore it (POST)."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.FLAGGED
        )
        if response:
            return response

        if request.method == "POST":
            form = RecategorizeForm(request.POST)
            if form.is_valid():
                new_category = form.cleaned_data["new_category"]
                insult.re_categorize(new_category)
                insult.refresh_from_db(fields=["category"])
                if insult.category_id != new_category.pk:
                    self.message_user(
                        request,
                        f"Could not recategorize {insult.reference_id}. Check the server logs.",
                        messages.ERROR,
                    )
                    return redirect(reverse("admin:API_insult_changelist"))

                insult.approve_insult()
                if self._report_review_result(
                    request, insult, Insult.STATUS.ACTIVE, "recategorized"
                ):
                    self._resolve_pending_reports(
                        request,
                        insult,
                        lambda review, user: review.mark_review_recategorized(user),
                    )
                return redirect(reverse("admin:API_insult_changelist"))
        else:
            form = RecategorizeForm(initial={"new_category": insult.category_id})

        return TemplateResponse(
            request,
            "admin/insult_flagged_recategorize.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Recategorize Insult {insult.reference_id}",
                "insult": insult,
                "open_reports": insult.reports.filter(
                    status=InsultReview.STATUS.PENDING
                ),
                "form": form,
                "opts": self.model._meta,
            },
        )

    def flagged_remove_view(self, request, insult_id):
        """Soft-delete a flagged insult."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.FLAGGED
        )
        if response:
            return response
        insult.remove_insult()
        if self._report_review_result(
            request, insult, Insult.STATUS.REMOVED, "removed"
        ):
            self._resolve_pending_reports(
                request, insult, lambda review, user: review.mark_review_removed(user)
            )
        return self._redirect_back(request, insult)

    def flagged_keep_view(self, request, insult_id):
        """Dismiss the reports and restore a flagged insult to the API unchanged."""
        insult, response = self._get_insult_in_status_or_redirect(
            request, insult_id, Insult.STATUS.FLAGGED
        )
        if response:
            return response
        insult.approve_insult()
        if self._report_review_result(request, insult, Insult.STATUS.ACTIVE, "kept"):
            self._resolve_pending_reports(request, insult, self._mark_review_no_change)
        return self._redirect_back(request, insult)

    @staticmethod
    def _mark_review_no_change(review, reviewer):
        """Close a report without acting on it, using the "no change" status that fits its type.

        Reclassification reports close as "same classification"; every other
        type (recategorization and removal requests) closes as "same category",
        since InsultReview has no dedicated "kept" status.
        """
        if review.review_type == InsultReview.REVIEW_TYPE.RECLASSIFY:
            review.mark_review_not_reclassified(reviewer)
        else:
            review.mark_review_not_recatagoized(reviewer)

    # ------------------------------------------------------------------
    # Admin actions — delegate to model methods
    # ------------------------------------------------------------------

    @admin.action(description="Approve selected insults")
    def approve_insult(self, request, queryset):
        """Admin action: approve each selected insult."""
        count = queryset.count()
        for insult in queryset:
            insult.approve_insult()
        self.message_user(request, f"{count} insult(s) approved successfully.")

    @admin.action(description="Remove selected insults (soft delete)")
    def remove_insult(self, request, queryset):
        """Admin action: soft-delete each selected insult."""
        count = queryset.count()
        for insult in queryset:
            insult.remove_insult()
        self.message_user(request, f"{count} insult(s) removed.")

    @admin.action(description="Mark selected insults for review")
    def mark_insult_for_review(self, request, queryset):
        """Admin action: flag each selected insult for review."""
        count = queryset.count()
        for insult in queryset:
            insult.mark_insult_for_review()
        self.message_user(request, f"{count} insult(s) marked for review.")

    @admin.action(description="Reclassify selected insults as NSFW")
    def reclassify_as_nsfw(self, request, queryset):
        """Admin action: mark each selected insult as NSFW."""
        count = queryset.count()
        for insult in queryset:
            insult.reclassify(True)
        self.message_user(request, f"{count} insult(s) reclassified as NSFW.")

    @admin.action(description="Reclassify selected insults as SFW")
    def reclassify_as_sfw(self, request, queryset):
        """Admin action: mark each selected insult as SFW."""
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
    """Admin list filter for reviews by how many reports their insult has."""

    title = "Number of Reports"
    parameter_name = "many_reports"

    def lookups(self, request, model_admin):
        """Return the filter options shown in the admin sidebar."""
        return (
            ("3+", "3 or more reports"),
            ("less", "Fewer than 3 reports"),
        )

    def queryset(self, request, queryset):
        """Filter reviews by their insult's report count (3+ or fewer than 3)."""
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


class UserAdmin(BaseUserAdmin):
    """User admin extended with an action to resend the welcome email."""

    actions = [*BaseUserAdmin.actions, "resend_welcome_email"]

    @admin.action(description="Resend welcome email to selected users")
    def resend_welcome_email(self, request, queryset):
        """Admin action: resend the welcome email to each selected user.

        Failures are logged per user and summarized in the admin message bar
        rather than aborting the whole batch.
        """
        sent, failed = 0, 0
        for user in queryset:
            try:
                WelcomeEmail(request=request, context={"user": user}).send(
                    to=[user.email]
                )
                sent += 1
            except Exception as exc:
                logger.error(
                    "Admin resend_welcome_email failed | user={} error={!r}",
                    user.username,
                    exc,
                )
                failed += 1

        if sent:
            self.message_user(
                request,
                f"Welcome email resent to {sent} user(s).",
                messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                f"Failed to send to {failed} user(s). Check the server logs.",
                messages.ERROR,
            )


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

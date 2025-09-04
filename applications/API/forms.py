"""
module: applications.API.forms
This module contains forms related to the API, specifically for handling insults and their reviews.
It uses the generalized caching framework for optimal performance.
"""

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Button, Column, Div, Layout, Row, Submit
from django.core.exceptions import ValidationError
from django.forms import BooleanField, CharField, ChoiceField, ModelForm, widgets
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_select2 import forms as s2forms
from loguru import logger

from applications.API.models import Insult, InsultReview
from common.cache_managers import create_form_choices_manager

# ===================================================================
# Cache Manager Setup
# ===================================================================


def insult_display_formatter(obj_dict: dict) -> str:
    """Format insult reference for display in form choices."""
    ref_id = obj_dict.get("reference_id", "Unknown")
    return f"Ref. ID: {ref_id}"


# Create and configure the insult choices cache manager
insult_choices_manager = create_form_choices_manager(
    model_class=Insult,
    choice_field="reference_id",
    display_formatter=insult_display_formatter,
    filter_kwargs={"status": "A"},  # Only active insults
    cache_prefix="Insult",
)


# ===================================================================
# Select2 Widget
# ===================================================================


class InsultReferenceSelect2(s2forms.ModelSelect2Widget):
    """Select2 widget for Insult reference with AJAX search."""

    search_fields = [
        "reference_id__icontains",
    ]
    attrs = {
        "data-minimum-input-length": 3,
        "data-placeholder": "Select an Insult by Ref ID…",
        "data-close-on-select": "true",
        "data-allow-clear": "true",
        "style": "width: 100%;",
    }


# ===================================================================
# Utility Functions (simplified using cache manager)
# ===================================================================


def get_cached_insult_data():
    """
    Get cached insult choices and queryset data.

    Returns:
        Tuple of (choices_list, queryset_json_string)
    """
    try:
        return insult_choices_manager.get_choices_and_queryset()
    except Exception as e:
        logger.error(f"Error getting cached insult data: {e}")
        return [], "[]"


def invalidate_insult_cache(reason: str = "manual") -> None:
    """
    Invalidate insult cache.

    Args:
        reason: Reason for invalidation
    """
    insult_choices_manager.invalidate_cache(reason)


def get_cache_stats() -> dict:
    """Get current cache statistics for insult data."""
    return insult_choices_manager.get_cache_stats()


# ===================================================================
# Form Definition
# ===================================================================


class InsultReviewForm(ModelForm):
    """
    Form for submitting reviews of insults with optimized caching.

    Uses the generalized caching framework for improved performance and maintainability.
    """

    insult_reference_id = CharField(
        required=True,
        label="Insult Reference ID",
        help_text="Start typing a reference ID (e.g., GIGGLE_…).",
    )

    review_type = ChoiceField(
        choices=InsultReview.REVIEW_TYPE.choices,
        required=True,
        label="Review Type",
    )

    anonymous = BooleanField(
        required=False,
        label="Anonymous",
        widget=widgets.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Check if you want to remain anonymous",
    )

    review_text = CharField(
        required=False,
        min_length=70,
        label="Review Text",
        widget=widgets.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure queryset is up-to-date at runtime using cache manager
        # try:
        # # The cache manager handles all the caching complexity
        # choices, _ = get_cached_insult_data()

        # # Update the queryset to ensure it's fresh
        # self.fields["insult_reference_id"].queryset = Insult.objects.filter(
        #     status="A"
        # ).only("reference_id")

        # logger.debug(f"Form initialized with {len(choices)} cached insult choices")

        # except Exception as e:
        #     logger.error(f"Error initializing form with cached data: {e}")
        #     # Fallback to standard queryset
        #     self.fields["insult_reference_id"].queryset = Insult.objects.filter(
        #         status="A"
        #     ).only("reference_id")

        # Setup form helper for crispy forms
        self.helper = FormHelper()
        self.helper.form_id = "report-joke-form"
        self.helper.form_method = "post"
        self.helper.form_action = reverse("report-joke")
        self.helper.layout = Layout(
            HTML(
                """
                <h3 class="application-text modal-title">Report Form</h3>
                <br/>
                <hr class="border border-primary border-3 opacity-75"/>
            """
            ),
            Row(
                Column("insult_reference_id", css_class="form-group col-md-6 mb-0"),
                Column("anonymous", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "review_type",
            Row(
                Column("reporter_first_name", css_class="form-group col-md-6 mb-0"),
                Column("reporter_last_name", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column(
                    "post_review_contact_desired", css_class="form-group col-md-6 mb-0"
                ),
                Column("reporter_email", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row("rationale_for_review", css_class="form-row"),
            Row(
                Div(
                    FormActions(
                        Submit(
                            name="report-joke",
                            css_class="btn btn-success",
                            value="Report Joke",
                        ),
                        Button("cancel", "Cancel", css_class="btn btn-danger"),
                    ),
                    css_class="modal-footer",
                ),
                css_class="form-row",
            ),
        )

    def clean(self):
        """
        Custom validation with improved error handling.
        """
        cleaned_data = super().clean()
        logger.debug(f"Type: {type(cleaned_data)} | Value: {cleaned_data}")

        # Normalize and coerce incoming values
        anonymous = bool(cleaned_data.get("anonymous", False))
        reporter_first_name = (cleaned_data.get("reporter_first_name") or "").strip()
        reporter_last_name = (cleaned_data.get("reporter_last_name") or "").strip()
        post_review_contact_desired = bool(
            cleaned_data.get("post_review_contact_desired", False)
        )
        reporter_email = (cleaned_data.get("reporter_email") or "").strip()
        insult_obj_or_value = cleaned_data.get("insult_reference_id")
        review_basis = (cleaned_data.get("rationale_for_review") or "").strip()
        # Support both ModelChoiceField (object) and pre-populated string values
        if hasattr(insult_obj_or_value, "reference_id"):
            ref_id = insult_obj_or_value.reference_id
        else:
            ref_id = str(insult_obj_or_value or "").strip()

        if not ref_id or Insult.get_by_reference_id(ref_id) is None:
            raise ValidationError(
                _("Invalid Insult ID"),
                code="invalid-insult-id",
            )

        # Ensure downstream code receives the reference-id string
        cleaned_data["insult_reference_id"] = ref_id
        cleaned_data["anonymous"] = anonymous
        cleaned_data["reporter_first_name"] = reporter_first_name
        cleaned_data["reporter_last_name"] = reporter_last_name
        # Validate non-anonymous submissions
        if not anonymous:
            if not reporter_first_name:
                raise ValidationError(
                    _("First name is required when not submitting anonymously"),
                    code="first-name-required",
                )
            if not reporter_last_name:
                raise ValidationError(
                    _("Last name is required when not submitting anonymously"),
                    code="last-name-required",
                )

        # Validate contact preference
        if post_review_contact_desired and not reporter_email:
            raise ValidationError(
                _("Email address is required"),
                code="email-required-for-contact",
            )

        # Validate Min Char Length only when provided
        if review_basis and len(review_basis) < 70:
            raise ValidationError(
                _(
                    "Please Ensure The Basis of your review request is 70 characters or more."
                )
            )
        return cleaned_data

    class Meta:
        model = InsultReview
        fields = (
            "insult_reference_id",
            "anonymous",
            "reporter_first_name",
            "reporter_last_name",
            "post_review_contact_desired",
            "reporter_email",
            "rationale_for_review",
            "review_type",
        )
        labels = {
            "post_review_contact_desired": "Do you want to be contacted with the review results?",
            "anonymous": "Submit anonymously?",
            "insult_reference_id": "Select the insult to review",
            "reporter_first_name": "First Name",
            "reporter_last_name": "Last Name or Initial",
            "rationale_for_review": "Reason for Review",
        }
        help_texts = {
            "insult_reference_id": "Select the insult you want reviewed",
            "reporter_first_name": "Your first name (required unless anonymous)",
            "reporter_last_name": "Your last name or initial (required unless anonymous)",
            "post_review_contact_desired": "Check if you want to be contacted with the review results",
            "reporter_email": "Your email address (required if you want to be contacted)",
            "rationale_for_review": "Provide a basis for review of the insult (minimum 70 characters)",
        }

# -*- coding: utf-8 -*-
import json
import threading

from applications.API.models import Insult, InsultReview
from common.metrics import metrics
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Button, Column, Div, Layout, Row, Submit
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms import ModelForm, fields, widgets
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from loguru import logger
from django.db.utils import ProgrammingError
# Module-level cache
_cached_choices = None
_cached_queryset = None
_cache_lock = threading.Lock()


def get_cached_insult_data():
    """
    Module-level function to get and cache insult data.
    Returns tuple of (choices, queryset).
    """
    global _cached_choices, _cached_queryset
    with _cache_lock:
        # First check module-level cache
        if _cached_choices is not None and _cached_queryset is not None:
            logger.debug("Module-level cache hit")
            return _cached_choices, _cached_queryset

    # Then check Redis cache
    cached_data = cache.get_many(["Insult:form_choices", "Insult:form_queryset"])
    if len(cached_data) == 2:
        logger.debug("Redis cache hit")
        metrics.increment_cache("Insult", "hit")
        _cached_choices = cached_data["Insult:form_choices"]
        _cached_queryset = cached_data["Insult:form_queryset"]
        return _cached_choices, _cached_queryset

    # Cache miss - query database
    logger.debug("Cache miss - querying database")
    metrics.increment_cache("Insult", "miss")
    # The following try block may raise a ProgrammingError if the database is not fully initialized.
    # This is expected during initial migrations or startup, and we handle it gracefully to avoid crashing.
    try:
        insult_queryset = Insult.objects.filter(status="A").values()
        _cached_choices = [(insult["id"], insult["id"]) for insult in insult_queryset]
        _cached_queryset = json.dumps(list(insult_queryset), cls=DjangoJSONEncoder)
    except ProgrammingError as e:
        logger.error(f"Error querying database: {e}")
        _cached_choices = []
        _cached_queryset = "[]"
    # Update both Redis and module-level cache
    cache_dict = {
        "Insult:form_choices": _cached_choices,
        "Insult:form_queryset": _cached_queryset,
    }
    cache.set_many(cache_dict, timeout=60 * 60 * 24)  # 24 hours

    return _cached_choices, _cached_queryset


def invalidate_insult_cache():
    """
    Invalidate both module-level and Redis cache.
    Call this when Insult data is modified.
    """
    
    global _cached_choices, _cached_queryset
    _cached_choices = None
    _cached_queryset = None
    cache.delete_many(["Insult:form_choices", "Insult:form_queryset"])


@receiver([post_save, post_delete], sender=Insult)
def handle_insult_change(sender, instance, **kwargs):
    """
    Invalidate caches when Insult model is modified.
    """
    invalidate_insult_cache()


class InsultReviewForm(ModelForm):
    insult = (
        fields.ChoiceField(
            choices=get_cached_insult_data()[1], required=True, label="Insult ID"
        ),
    )
    review_type = (
        fields.ChoiceField(
            choices=InsultReview.REVIEW_TYPE.choices,
            required=True,
            label="Review Type",
            widget=widgets.RadioSelect(),
        ),
    )
    anonymous = (
        fields.BooleanField(
            required=False,
            label="Anonymous",
            widget=widgets.CheckboxInput(attrs={"class": "form-check-input"}),
        ),
    )
    review_text = (
        fields.CharField(
            required=False,
            label="Review Text",
            widget=widgets.Textarea(attrs={"class": "form-control", "rows": 3}),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use the module-level cached data
        self.insult_choices, self.insult_queryset = get_cached_insult_data()

        self.helper = FormHelper()
        self.helper.form_id = "report-joke-form"
        self.helper.form_method = "post"
        self.helper.form_action = reverse("report-joke")
        self.helper.layout = Layout(
            HTML(
                """
        <h3 class="application-text modal-title">Report Form</strong></h3>
        <br/>
        <hr class="border border-primary border-3 opacity-75"/>"""
            ),
            Row(
                Column("insult", css_class="form-group col-md-6 mb-0"),
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
            Row(
                "rationale_for_review",
                css_class="form-row",
            ),
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
        cleaned_data = super().clean()
        anonymous = cleaned_data.get("anonymous")
        reporter_first_name = cleaned_data.get("reporter_first_name")
        reporter_last_name = cleaned_data.get("reporter_last_name")
        post_review_contact_desired = cleaned_data.get("post_review_contact_desired")
        reporter_email = cleaned_data.get("reporter_email")
        insult = cleaned_data.get("insult")
        # Use the module-level cached choices for validation
        if insult not in [choice[0] for choice in self.insult_choices]:
            raise ValidationError(
                _("Invalid Insult ID - Please confirm Insult ID"),
                code="invalid-insult-id",
            )
        if anonymous is False:
            if reporter_first_name in [None, " ", ""]:
                raise ValidationError(
                    _(
                        "Name Not Provided - You have selected that you do not wish to submit this report anonymously, but have not provided a first name. Please change your anonymity preference or enter a first name"
                    ),
                    code="invalid-first-name-not-provided",
                )

            if reporter_last_name in [None, " ", ""]:
                raise ValidationError(
                    _(
                        "Name Not Provided - You have selected that you do not wish to submit this report anonymously, but have not provided a last name, or last initial. Please change your anonymity preference or enter a last name"
                    ),
                    code="invalid-last-name-not-provided",
                )
        if post_review_contact_desired is True and reporter_email in [None, " ", ""]:
            raise ValidationError(
                _(
                    "Email Not Provided - You have selected that you wish to be contacted to know the desired outcome of the review, but have not provided an email address. Please change your results contact preference or enter a valid email address"
                ),
                code="invalid-email-not-provided",
            )
        return cleaned_data

    class Meta:
        model = InsultReview
        fields = (
            "insult",
            "anonymous",
            "reporter_first_name",
            "reporter_last_name",
            "post_review_contact_desired",
            "reporter_email",
            "rationale_for_review",
            "review_type",
        )
        labels = {
            "post_review_contact_desired": "Do You Want The Reviewer to Contact You With the Results of the Review?",
            "anonymous": "Do You Want to Remain Anonymous?",
            "insult": "What is the ID number of the Insult?",
            "reporter_first_name": "First Name",
            "reporter_last_name": "Last name or Last Initial",
        }

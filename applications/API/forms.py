"""
module: applications.API.forms
This module contains forms related to the API, specifically for handling insults and their reviews.
It includes a form for submitting reviews of insults, with validation and caching mechanisms.
"""


import json
import threading
import time
from typing import Any, Dict, List, Tuple, Union
from typing import Any, Dict, List, Tuple, Union

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Button, Column, Div, Layout, Row, Submit
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Button, Column, Div, Layout, Row, Submit
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.signals import post_delete, post_save
from django.db.utils import ProgrammingError
from django.dispatch import receiver
from django.forms import BooleanField, CharField, ChoiceField, ModelForm, widgets
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_select2 import forms as s2forms
from loguru import logger

from applications.API.models import Insult, InsultReview
from common.metrics import metrics
from common.metrics import metrics

# Module-level caches
_cached_choices: Union[None, List[Tuple[int, str]]] = None
_cached_queryset: Union[None, str] = None
# Module-level caches
_cached_choices: Union[None, List[Tuple[int, str]]] = None
_cached_queryset: Union[None, str] = None
_cache_lock = threading.Lock()

# Cache configurationtask
CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours
CACHE_KEYS = {
    "choices": "Insult:form_choices_v2",
    "queryset": "Insult:form_queryset_v2",
    "choices": "Insult:form_choices_v2",
    "queryset": "Insult:form_queryset_v2",
}


def get_cache_stats() -> Dict[str, Any]:
    """Helper function to get current cache statistics for monitoring.


    Returns:
        Dictionary with cache statistics suitable for Prometheus metrics.
    """
    global _cached_choices, _cached_queryset

    redis_keys = cache.get_many([CACHE_KEYS["choices"], CACHE_KEYS["queryset"]])


    redis_keys = cache.get_many([CACHE_KEYS["choices"], CACHE_KEYS["queryset"]])

    return {
        "module_cache_loaded": _cached_choices is not None and len(_cached_choices) > 0,
        "choices_count": len(_cached_choices) if _cached_choices else 0,
        "redis_keys": redis_keys,
        "redis_keys_count": len(redis_keys),
        "cache_timeout": CACHE_TIMEOUT,
        "timestamp": time.time(),
        "module_cache_loaded": _cached_choices is not None and len(_cached_choices) > 0,
        "choices_count": len(_cached_choices) if _cached_choices else 0,
        "redis_keys": redis_keys,
        "redis_keys_count": len(redis_keys),
        "cache_timeout": CACHE_TIMEOUT,
        "timestamp": time.time(),
    }


def get_cached_insult_data() -> Tuple[List[Tuple[int, str]], str]:
    """
    Multi-level caching function to get insult data with comprehensive metrics.
    Returns tuple of (choices_list, queryset_json_string).


    Caching strategy:
    1. Module-level cache (fastest)
    2. Redis cache (fast)
    2. Redis cache (fast)
    3. Database query (slowest - 15 seconds)
    """
    global _cached_choices, _cached_queryset


    # Start timing the overall cache operation
    time.time()

    time.time()

    with _cache_lock:
        try:
            with metrics.time_cache_operation("Insult", "load"):
                # Level 1: Module-level cache check
                if (
                    _cached_choices is not None
                    and _cached_queryset is not None
                    and len(_cached_choices) > 0
                ):

                    logger.debug("Module-level cache hit for insult data")
                    metrics.increment_cache("Insult", "hit")


                    # Update cache statistics
                    stats = get_cache_stats()
                    metrics.update_cache_stats("Insult", stats)

                    return _cached_choices, _cached_queryset

                # Level 2: Redis cache check
                cached_data = cache.get_many(
                    [CACHE_KEYS["choices"], CACHE_KEYS["queryset"]]
                )
                if len(cached_data) == 2:
                    logger.debug("Redis cache hit for insult data")
                    metrics.increment_cache("Insult", "hit")


                    _cached_choices = cached_data[CACHE_KEYS["choices"]]
                    _cached_queryset = cached_data[CACHE_KEYS["queryset"]]

                    # Update cache statistics
                    stats = get_cache_stats()
                    metrics.update_cache_stats("Insult", stats)

                    return _cached_choices, _cached_queryset

                # Level 3: Database query (cache miss)
                logger.info(
                    "Cache miss - querying database for insult data (this may take 15 seconds)"
                )
                metrics.increment_cache("Insult", "miss")

                # Time the database query separately
                db_start_time = time.time()

                try:
                    with metrics.time_database_query("Insult", "success"):
                        # Query active insults
                        insult_queryset = Insult.objects.filter(status="A").values(
                            "reference_id"
                        )

                        # Create choices for the form field (id, display_text)
                        _cached_choices = [
                            (
                                insult["reference_id"],
                                f"Ref. ID: {insult['reference_id']}",
                            )
                            for insult in insult_queryset
                        ]


                        # Store full queryset as JSON for potential other uses
                        _cached_queryset = json.dumps(
                            list(insult_queryset), cls=DjangoJSONEncoder
                        )

                        _cached_queryset = json.dumps(
                            list(insult_queryset), cls=DjangoJSONEncoder
                        )

                    db_duration = time.time() - db_start_time
                    logger.info(
                        f"Successfully cached {len(_cached_choices)} insult choices in {db_duration:.2f}s"
                    )

                except ProgrammingError as e:
                    db_duration = time.time() - db_start_time
                    logger.error(f"Database not ready during insult data query: {e}")

                    # Record the failed query time

                    metrics.record_database_query_time("Insult", db_duration, "error")

                    _cached_choices = []
                    _cached_queryset = "[]"


                except Exception as e:
                    db_duration = time.time() - db_start_time
                    logger.error(f"Unexpected error querying insult data: {e}")
                    # Record the failed query time
                    metrics.record_database_query_time("Insult", db_duration, "error")
                    _cached_choices = []
                    _cached_queryset = "[]"

                # Update Redis cache if we have data
                if _cached_choices:
                    cache_dict = {
                        CACHE_KEYS["choices"]: _cached_choices,
                        CACHE_KEYS["queryset"]: _cached_queryset,
                    }
                    cache.set_many(cache_dict, timeout=CACHE_TIMEOUT)
                    logger.debug(
                        f"Updated Redis cache with {len(_cached_choices)} insult choices"
                    )

                # Update final cache statistics
                stats = get_cache_stats()
                metrics.update_cache_stats("Insult", stats)

                return _cached_choices, _cached_queryset


        except Exception as e:
            logger.error(f"Error in get_cached_insult_data: {e}")
            # Still update metrics even on error
            stats = get_cache_stats()
            metrics.update_cache_stats("Insult", stats)
            raise


def invalidate_insult_cache(reason: str = "manual") -> None:
    """
    Invalidate both module-level and Redis cache with metrics tracking.


    Args:
        reason: Reason for invalidation ('post_save', 'post_delete', 'manual').
    """
    global _cached_choices, _cached_queryset


    logger.info(f"Invalidating insult cache (reason: {reason})")


    with metrics.time_cache_operation("Insult", "invalidate"):
        # Clear module-level cache
        _cached_choices = None
        _cached_queryset = None


        # Clear Redis cache
        cache.delete_many([CACHE_KEYS["choices"], CACHE_KEYS["queryset"]])


        # Record the invalidation
        metrics.increment_cache("Insult", "invalidated", reason)


        # Update cache statistics to reflect empty state
        stats = get_cache_stats()
        metrics.update_cache_stats("Insult", stats)


@receiver([post_save, post_delete], sender=Insult)
def handle_insult_change(sender, instance, **kwargs):
    """
    Invalidate caches when Insult model is modified with proper reason tracking.
    """
    # Determine the reason based on the signal
    if kwargs.get("created"):
        reason = "post_save_created"
    elif "post_save" in str(kwargs):
        reason = "post_save_updated"
    else:
        reason = "post_delete"


    logger.debug(f"Insult {instance.id} modified ({reason}), invalidating cache")
    invalidate_insult_cache(reason)


def get_cache_performance_summary() -> Dict[str, Any]:
    """
    Get a summary of cache performance for monitoring dashboards.


    Returns:
        Dictionary with cache performance metrics.
    """
    try:
        hit_rate = metrics.get_cache_hit_rate("Insult")
        current_stats = get_cache_stats()


        return {
            "hit_rate_percentage": hit_rate,
            "current_stats": current_stats,
            "cache_keys": list(CACHE_KEYS.values()),
            "cache_timeout_hours": CACHE_TIMEOUT / 3600,
            "hit_rate_percentage": hit_rate,
            "current_stats": current_stats,
            "cache_keys": list(CACHE_KEYS.values()),
            "cache_timeout_hours": CACHE_TIMEOUT / 3600,
        }
    except Exception as e:
        logger.error(f"Error getting cache performance summary: {e}")
        return {
            "hit_rate_percentage": 0.0,
            "current_stats": get_cache_stats(),
            "error": str(e),
            "hit_rate_percentage": 0.0,
            "current_stats": get_cache_stats(),
            "error": str(e),
        }




class InsultReviewForm(ModelForm):
    """
    Form for submitting reviews of insults with optimized caching.
    """


    # Dynamic choices will be set in __init__
    insult_reference_id = ChoiceField(
        widget=s2forms.ModelSelect2Widget(
            model=Insult,
            search_field=["insult_reference_id__icontains"],
            max_results=50,
            attrs={
                "data-minimum-input-length": 4,
                "data-placeholder": "Select an Insult",
                "data-close-on-select": "true",
            },
        ),
        required=True,
        label="Insult Reference ID",
        help_text="Select the insult you want to review",),

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


        # Setup form helper for crispy forms
        self.helper = FormHelper()
        self.helper.form_id = "report-joke-form"
        self.helper.form_method = "post"
        self.helper.form_action = reverse("report-joke")
        self.helper.layout = Layout(
            HTML("""
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
        ) # pyrefly:ignore

    def clean(self):
        """
        Custom validation with improved error handling.
        """
        cleaned_data = super().clean()


        # Get form data
        anonymous = cleaned_data.get("anonymous", False)
        reporter_first_name = cleaned_data.get("reporter_first_name", "").strip()
        reporter_last_name = cleaned_data.get("reporter_last_name", "").strip()
        post_review_contact_desired = cleaned_data.get(
            "post_review_contact_desired", False
        )
        post_review_contact_desired = cleaned_data.get(
            "post_review_contact_desired", False
        )
        reporter_email = cleaned_data.get("reporter_email", "").strip()
        insult_reference_id = cleaned_data.get("insult_reference_id")

        # Validate insult ID
        if Insult.get_by_reference_id(insult_reference_id) is None:
            raise ValidationError(
                _("Invalid Insult ID - Please select a valid insult from the dropdown"),
                code="invalid-insult-id",
            )

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
                _("Email address is required if you want to be contacted with results"),
                code="email-required-for-contact",
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
            "insult_reference_id": "Select the insult you want reviewed review",
            "reporter_first_name": "Your first name (required unless anonymous)",
            "reporter_last_name": "Your last name or initial (required unless anonymous)",
            "post_review_contact_desired": "Check if you want to be contacted with the review results",
            "reporter_email": "Your email address (required if you want to be contacted)",
            "rationale_for_review": "Provide a reason for your review",
        }

        help_texts = {
            "insult_reference_id": "Select the insult you want reviewed review",
            "reporter_first_name": "Your first name (required unless anonymous)",
            "reporter_last_name": "Your last name or initial (required unless anonymous)",
            "post_review_contact_desired": "Check if you want to be contacted with the review results",
            "reporter_email": "Your email address (required if you want to be contacted)",
            "rationale_for_review": "Provide a basis for review of the insult (minimum 70 characters)",
        }

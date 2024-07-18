# -*- coding: utf-8 -*-
from API.models import Insult, InsultReview
from django_recaptcha.fields import ReCaptchaField 
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Button, Column, Div, Field, Layout, Row, Submit
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from loguru import logger


class InsultReviewForm(ModelForm):
    recaptha = ReCaptchaField()
    ID_LIST = Insult.objects.filter(status="A").only("pk")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = "report-joke-form"
        self.helper.form_method = "post"
        self.helper.form_action = "/report"
        self.helper.layout = Layout(
            HTML(
                """
        <h3 class="application-text modal-title">Report Form</strong></h3>
        <br/>
        <hr class="border border-primary border-3 opacity-75"/>"""
            ),
            Row(
                Column("insult_id", css_class="form-group col-md-6 mb-0"),
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
            Field("recaptha"),
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
        insult_id = cleaned_data.get("insult_id")
        
        if insult_id not in ID_LIST:
            raise ValidationError(
                _("Invaild Insult ID - Please confirm Insult ID"),
                code="invaild-insult-id",
            )
        if anonymous is False:
            if reporter_first_name in [None, " ", ""]:
                raise ValidationError(
                    _(
                        "Name Not Provided - You have selected that you do not wish submit this report anonymously, but have not provided a first name. Please change your anonymity preference or enter a first name"
                    ),
                    code="invalid-first-name-not-provided",
                )

            if reporter_last_name in [None, " ", ""]:
                raise ValidationError(
                    _(
                        "Name Not Provided - You have selected that you do not wish submit this report anonymously, but have not provided a last name, or last inital. Please change your anonymity preference or enter a last name"
                    ),
                    code="invalid-last-name-not-provided",
                )
        if post_review_contact_desired is True:
            if reporter_email in [None, " ", ""]:
                raise ValidationError(
                    _(
                        "Email Not Provided - You have selected that you wish to be contacted to know the desired outcome of the review, but have not provided an email address. Please change your results contact preference or enter a vaild email addrwss"
                    ),
                    code="invalid-last-name-not-provided",
                )
        return clean_data

    class Meta:
        model = InsultReview
        fields = (
            "insult_id",
            "anonymous",
            "reporter_first_name",
            "reporter_last_name",
            "post_review_contact_desired",
            "reporter_email",
            "rationale_for_review",
            "review_type",
        )
        labels = {
            "post_review_contact_desired": "Do You Want The Reviewer to Contact You With the Reuslts of the Review?",
            "anonymous": "Do You Want to Remain Anonymous?",
            "insult_id": "What is the ID number of the Insult?",
            "reporter_first_name": "First Name",
            "reporter_last_name": "Last name or Last Inital",
        }

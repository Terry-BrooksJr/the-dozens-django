# -*- coding: utf-8 -*-
import pytest
from API.forms import InsultReviewForm
from API.models import Insult, InsultReview
from django.core.exceptions import ValidationError
from django.test import TestCase

ID_LIST = [1, 2, 3]  # Example ID list for testing


@pytest.mark.parametrize(
    "anonymous, reporter_first_name, reporter_last_name, post_review_contact_desired, reporter_email, insult_id, expected_exception, expected_message",
    [
        # Happy path tests
        (True, None, None, False, None, 1, None, None),
        (False, "John", "Doe", False, None, 2, None, None),
        (False, "Jane", "Smith", True, "jane@example.com", 3, None, None),
        # Edge cases
        (
            False,
            " ",
            "Doe",
            False,
            None,
            1,
            ValidationError,
            "Name Not Provided - You have selected that you do not wish submit this report anonymously, but have not provided a first name. Please change your anonymity preference or enter a first name",
        ),
        (
            False,
            "John",
            " ",
            False,
            None,
            2,
            ValidationError,
            "Name Not Provided - You have selected that you do not wish submit this report anonymously, but have not provided a last name, or last initial. Please change your anonymity preference or enter a last name",
        ),
        (
            False,
            "John",
            "Doe",
            True,
            " ",
            3,
            ValidationError,
            "Email Not Provided - You have selected that you wish to be contacted to know the desired outcome of the review, but have not provided an email address. Please change your results contact preference or enter a vaild email addrwss",
        ),
        # Error cases
        (
            True,
            None,
            None,
            False,
            None,
            999,
            ValidationError,
            "Invaild Insult ID - Please confirm Insult ID",
        ),
        (
            False,
            None,
            "Doe",
            False,
            None,
            1,
            ValidationError,
            "Name Not Provided - You have selected that you do not wish submit this report anonymously, but have not provided a first name. Please change your anonymity preference or enter a first name",
        ),
        (
            False,
            "John",
            None,
            False,
            None,
            2,
            ValidationError,
            "Name Not Provided - You have selected that you do not wish submit this report anonymously, but have not provided a last name, or last initial. Please change your anonymity preference or enter a last name",
        ),
        (
            False,
            "John",
            "Doe",
            True,
            None,
            3,
            ValidationError,
            "Email Not Provided - You have selected that you wish to be contacted to know the desired outcome of the review, but have not provided an email address. Please change your results contact preference or enter a vaild email addrwss",
        ),
    ],
    ids=[
        "happy_path_anonymous",
        "happy_path_non_anonymous",
        "happy_path_contact_desired",
        "edge_case_blank_first_name",
        "edge_case_blank_last_name",
        "edge_case_blank_email",
        "error_invalid_insult_id",
        "error_missing_first_name",
        "error_missing_last_name",
        "error_missing_email",
    ],
)
class InsultReviewTest(TestCase):
    def test_clean(
        self,
        anonymous,
        reporter_first_name,
        reporter_last_name,
        post_review_contact_desired,
        reporter_email,
        insult_id,
        expected_exception,
        expected_message,
    ):
        # Arrange
        form_data = {
            "anonymous": anonymous,
            "reporter_first_name": reporter_first_name,
            "reporter_last_name": reporter_last_name,
            "post_review_contact_desired": post_review_contact_desired,
            "reporter_email": reporter_email,
            "insult_id": insult_id,
        }
        form = InsultReviewForm(data=form_data)

        # Act
        if expected_exception:
            with pytest.raises(expected_exception) as exc_info:
                form.clean()

            # Assert
            assert str(exc_info.value) == expected_message
        else:
            cleaned_data = form.clean()

            # Assert
            assert cleaned_data == form_data

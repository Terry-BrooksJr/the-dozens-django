"""
module: applications.API.models


This module defines the Insult and InsultReview models, which are used to manage insults and their reviews in the system, as well as the InsultCategory model for insult resource categorization. Each model contains methods for manipulating the associated resource.
    
For instance, the Insult model's methods allow for removing, approving, and re-categorizing task. The models and their methods are designed to work with Django's ORM and include various fields and methods for managing the data effectively.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from typing import List, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin
from loguru import logger

INSULT_REFERENCE_ID_PREFIX_OPTIONS: List[str] = [
    "GIGGLE",
    "CHUCKLE",
    "SNORT",
    "SNICKER",
    "CACKLE",
]


class Base64DecoderException(Exception):
    """Custom exception for base64 decoding errors."""


class Base64EncoderException(Exception):
    """Custom exception for base64 encoding errors."""


def encode_base64(number: int) -> str:
    """
    Encodes a positive integer as a base64 string.

    This function takes a positive integer and returns its base64-encoded string representation.

    Args:
        number (int): The positive integer to encode.

    Returns:
        str: The base64-encoded string representation of the input number.

    Raises:
        Base64EncoderException: If the input number is not positive.
    """
    if number <= 0:
        raise Base64EncoderException("Number must be non-negative")
    try:
        return base64.b64encode(str(number).encode()).decode()
    except Exception as e:
        logger.exception(f"Unable to Encode Reference ID for Insult {number}: {str(e)}")
        raise Base64EncoderException(str(e))


class InsultCategory(ExportModelOperationsMixin("insult_categories"), models.Model):
    """
    Model representing a"{} category for insults. This model defines an insult category with a unique key and name. It is used to organize insults into different categories for easier management and retrieval.
    """

    category_key = models.CharField(max_length=5, unique=True, primary_key=True)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"{self.category_key} - {self.name}"

    def lower(self):
        """Returns the name of the category in lowercase."""
        return self.name.lower()

    class Meta:
        db_table = "insult_categories"
        verbose_name = _("Insult Category")
        verbose_name_plural = _("Insult Categories")
        managed = True
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category_key", "name"], name="unique_category_key_name"
            ),
        ]
        indexes = [
            models.Index(fields=["category_key"], name="idx_category_key"),
            models.Index(fields=["name"], name="idx_name"),
        ]


class Insult(ExportModelOperationsMixin("insult"), models.Model):
    """
    Model representing an Insult with various attributes and methods for manipulation. This model represents an Insult with fields like content, category, nsfw, added_on, added_by, last_modified, and status. It includes methods for removing, approving, marking for review, re-categorizing, and reclassifying insults.

    Methods:
        - remove_insult(): Removes insult visibility from the API (Soft Delete).
        - approve_insult(): Adds a Pending insult to the API.
        - mark_insult_for_review(): Removes insult visibility from the API.
        - re_categorize(new_category): Re-categorizes the object with a new category.
        - reclassify(nsfw_status): Changes the category of the insult.
    """

    class Meta:
        db_table = "insults"
        ordering = ["nsfw", "category"]
        verbose_name = "Insult/Joke"
        verbose_name_plural = "Insults/Jokes"
        managed = True
        indexes = [
            models.Index(fields=["category"], name="idx_category"),
            models.Index(fields=["category", "nsfw"], name="idx_nsfw_category"),
            models.Index(fields=["nsfw"], name="idx_nsfw"),
            models.Index(fields=["added_by"], name="idx_added_by"),
            models.Index(fields=["reference_id"], name="idx_reference_id"),
            models.Index(
                fields=["reference_id", "insult_id"], name="idx_reference_id_pk"
            ),
            models.Index(
                fields=["added_by", "status", "category"],
                name="idx_added_status_cat",
            ),
        ]

    class STATUS(models.TextChoices):
        """
        Enumeration of possible statuses for an Insult instance. This class defines the available status choices for insults, such as active, removed, pending, and rejected. These statuses are used to manage the visibility and workflow state of each insult in the system.

        Statuses:
            ACTIVE: The insult is currently active and visible.
            REMOVED: The insult has been removed from visibility (soft delete).
            PENDING: The insult is newly created awaiting review or approval.(Default for new insults)
            REJECTED: The insult has been rejected during review.
            FLAGGED: The insult has a pending review an is undiscoverable via the API
        """

        ACTIVE = "A", _("Active")
        REMOVED = "X", _("Inactive/Removed")
        PENDING = "P", _("Pending - New")
        REJECTED = "R", _("Rejected")
        FLAGGED = "F", _("Flagged for Review")

    content = models.CharField(
        max_length=65535,
        null=False,
        blank=False,
        error_messages={"required": "Insults must have content"},
    )
    insult_id = models.AutoField(primary_key=True)

    reference_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
        blank=True,
        null=True,
        verbose_name="Reference ID",
        db_comment="Unique reference ID for the insult, generated from the primary key.",
        help_text="Unique identifier for the insult, generated from the primary key.",
    )
    category = models.ForeignKey(InsultCategory, on_delete=models.PROTECT)
    nsfw = models.BooleanField()
    added_on = models.DateField(null=False, blank=False, auto_now_add=True)
    reports_count = models.PositiveIntegerField(default=0, blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.PROTECT)
    last_modified = models.DateTimeField(auto_now=True, blank=True, null=True)
    status = models.CharField(
        null=False,
        blank=False,
        max_length=2,
        default=STATUS.PENDING,
        choices=STATUS.choices,
        db_index=True,
    )

    def save(self, *args, **kwargs):
        # Only generate reference_id if it is not set and pk is None (new object)
        if self.pk is None and not self.reference_id:
            # Save first to get a PK
            super().save(*args, **kwargs)
            # Generate a unique reference_id
            while True:
                candidate = f"{secrets.choice(INSULT_REFERENCE_ID_PREFIX_OPTIONS)}_{encode_base64(self.pk)}"
                if not type(self).objects.filter(reference_id=candidate).exists():
                    self.reference_id = candidate  # pyrefly: ignore
                    break
            # Only update the reference_id field
            super().save(update_fields=["reference_id"])
        else:
            # Prevent regeneration of reference_id if already set
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.reference_id} - ({self.category}) - NSFW: {self.nsfw}"

    @property
    def open_report_count(self) -> int:
        """Returns the count of open reports for this insult."""
        return self.reports.filter(status=InsultReview.STATUS.PENDING).count()

    @classmethod
    def get_by_reference_id(cls: type[Insult], reference_id: str) -> Optional[Insult]:
        """
        Retrieves an Insult instance by its reference ID.

        This class method decodes the provided reference ID, extracts the primary key, and fetches the corresponding Insult object from the database. If the reference ID is invalid or the object does not exist, it returns None.

        Args:
            reference_id (str): The unique reference ID of the insult.

        Returns:
            Optional[Insult]: The Insult instance if found, otherwise None.
        """
        for prefix in INSULT_REFERENCE_ID_PREFIX_OPTIONS:
            if reference_id.startswith(prefix):
                # Extract base64 part and decode to PK
                if reference_id.startswith(f"{prefix}_"):
                    base64_part = reference_id[len(prefix) + 1 :]
                else:
                    base64_part = reference_id[len(prefix) :]
                try:
                    decoded_bytes = base64.b64decode(base64_part)
                    pk_str = decoded_bytes.decode("utf-8")
                    pk = int(pk_str)
                except (binascii.Error, ValueError) as e:
                    logger.warning(f"Invalid base64 part: {base64_part} ({e})")
                    return None
                try:
                    return cls.objects.get(pk=pk)
                except cls.DoesNotExist:
                    logger.warning(f"Insult with PK {pk} does not exist.")
                    return None

    def remove_insult(self):
        """Removes insult visibility from the API. (Soft Delete)
        Logs:
            Success: Logs the PK of the modified Insult Instance
            Exception: If the Insult unable top be removed.
        Returns:
            None
        """

        try:
            self.status = Insult.STATUS.REMOVED  # Set status to REMOVED
            self.last_modified = settings.GLOBAL_NOW
            self.save(update_fields=["status", "last_modified"])
            logger.success(f"Successfully Removed {self.reference_id}")
        except Exception as e:
            logger.error(f"Unable to Remove Insult ({self.reference_id}): {e}")

    def approve_insult(self):
        """Adds a Pending insult to the API.

        Updates the Insult.status of the current object to approved, making the current instance discoverable by the API Serializers and Filters.
        Logs:
            Success: Logs the PK of the modified Insult Instance
            Exception: If the Insult is unable to be removed.

        Returns:
            None
        """

        try:
            self.status = Insult.STATUS.ACTIVE  # Set status to ACTIVE
            self.last_modified = settings.GLOBAL_NOW
            self.save(update_fields=["status", "last_modified"])
            logger.success(f"Successfully Approved {self.reference_id}")
        except Exception as e:
            logger.error(f"Unable to Approve Insult({self.reference_id}): {e}")

    def mark_insult_for_review(self):
        """Removes insult visibility from the API.

        Logs:
            Exception: If the Insult is unable to be removed.

        Returns:
            None
        """

        try:
            self.status = Insult.STATUS.PENDING  # Set status to PENDING
            self.last_modified = settings.GLOBAL_NOW
            self.save(update_fields=["status", "last_modified"])
            logger.warning(f"Successfully Sent to Review {self.reference_id}")
        except Exception as e:
            logger.error(f"Unable to Send For Review({self.reference_id}): {e}")

    def re_categorize(self, new_category):
        """Re-categorizes the object with a new category.

        Args:
            new_category (str): The new category to assign to the Insult.

        Logs:
            Exception: If an error occurs while re-categorizing the object.

        Returns:
            None


        """

        try:
            self.category = new_category
            self.last_modified = settings.GLOBAL_NOW
            self.save(update_fields=["category", "last_modified"])
            logger.success(
                f"Successfully Re-Categorized {self.reference_id} to {self.category}"
            )
        except Exception:
            self.save(update_fields=["category", "last_modified"])
            logger.success(
                f"Successfully Re-Categorized {self.reference_id} to {self.category}"
            )

    def reclassify(self, nsfw_status):
        """Changes the category of the insult

        Logs:
            Exception: If the Insult is unable to be removed.

        Returns:
            None
        """
        try:
            self.nsfw = nsfw_status
            self.last_modified = settings.GLOBAL_NOW
            self.save(update_fields=["nsfw", "last_modified"])
            logger.success(
                f"Successfully reclassified {self.reference_id} to {self.nsfw}"
            )
        except Exception as e:
            logger.error(f"Unable to ReClassify Insult {self.reference_id}: {e}")


class InsultReview(ExportModelOperationsMixin("jokeReview"), models.Model):
    """
    Summary:
    Model representing an Insult Review with methods for marking different review types.

    Explanation:
    This model represents an Insult Review with fields like insult_id, anonymous, reporter_first_name, post_review_contact_desired, reporter_email, date_submitted, date_reviewed, rationale_for_review, review_type, and status. It includes methods for marking the review as reclassified, re-categorized, not reclassified, removed, and reclassified.

    Methods:
        - mark_review_not_reclassified(): Marks the review as Not reclassified.
        - mark_review_recatagoized(): Marks the review as re-categorized.
        - mark_review_not_recatagoized(): Marks the review as reclassified.
        - mark_review_removed(): Marks the review as removed.
        - mark_review_reclassified(): Marks the review as reclassified.
    """

    class REVIEW_TYPE(models.TextChoices):
        RECLASSIFY = "RE", _("Joke Reclassification")
        RECATEGORIZE = "RC", _("Joke Recategorization")
        REMOVAL = "RX", _("Joke Removal")

    class STATUS(models.TextChoices):
        PENDING = "P", _("Pending")
        NEW_CLASSIFICATION = "NCE", _("Completed - New Explicitly Setting")
        SAME_CLASSIFICATION = "SCE", _("Completed - No New Explicitly Setting")
        NEW_CATEGORY = "NJC", _("Completed - Assigned to New Category")
        SAME_CATEGORY = "SJC", _("Completed - No New Category Assigned")
        REMOVED = "X", _("Completed - Joke Removed")

    insult_reference_id = models.CharField(max_length=50)
    anonymous = models.BooleanField(default=False)
    insult = models.ForeignKey(
        Insult, on_delete=models.CASCADE, related_name="reports", blank=True, null=True
    )
    reporter_first_name = models.CharField(max_length=80, null=True, blank=True)
    reporter_last_name = models.CharField(max_length=80, null=True, blank=True)
    post_review_contact_desired = models.BooleanField(default=False)
    reporter_email = models.EmailField(null=True, blank=True)
    date_submitted = models.DateField(auto_now=True)
    date_reviewed = models.DateField(null=True, blank=True)
    rationale_for_review = models.TextField()
    reviewer = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, null=True, blank=True
    )
    review_type = models.CharField(choices=REVIEW_TYPE.choices, null=False, blank=False)
    status = models.CharField(
        max_length=3,  # Add max_length based on your choices
        choices=STATUS.choices,
        default=STATUS.PENDING,
        null=False,  # Remove null since we have a default
        blank=False,
    )

    def __str__(self):
        return f"Joke: {self.insult_reference_id} - Review Type: {self.review_type} - Submitted: {self.date_submitted}({self.status})"

    def set_insult(self) -> None:
        """Get the associated Insult instance."""
        try:
            # Decode the reference ID to get the insult ID
            if not self.insult_reference_id:
                raise IntegrityError(
                    "Insult Reference ID must be provided to set the related Insult."
                )
            if not self.insult:
                if found_insult := Insult.get_by_reference_id(self.insult_reference_id):
                    logger.info(
                        f"Setting Insult for Review {self.insult_reference_id} - {found_insult.insult_id}"
                    )
                    self.insult = found_insult
                    self.save(update_fields=["insult"])
        except Insult.DoesNotExist as e:
            logger.error(
                f"Insult with reference ID {self.insult_reference_id} does not exist."
            )
            raise IntegrityError(
                f"Reviews Must Be Associated with a VAILD Insult. Insult with reference ID {self.insult_reference_id} does not exist."
            ) from e
        except Base64DecoderException as base64_error:
            logger.error(
                f"Base64 decoding error for reference ID {self.insult_reference_id}: {base64_error}"
            )
            raise IntegrityError(
                f"Reviews Must include a valid insult reference id that conforms to a pre-fixed Base64 format. Either value after the prefix is invalid  for Insult Reference ID: {self.insult_reference_id}"
            ) from base64_error
        except Exception as e:
            logger.error(f"Generalized Insult Setting Error: {str(e)}")
            raise IntegrityError(f"Generalized Insult Setting Error: {str(e)}") from e

    class Meta:
        db_table = "reported_jokes"
        ordering = ["status", "-date_submitted"]
        verbose_name = "Joke Needing Review"
        verbose_name_plural = "Jokes Needing Review"
        get_latest_by = ["-date_submitted"]

        indexes = [
            models.Index(fields=["review_type"], name="idx_review_type"),
            models.Index(fields=["status"], name="idx_status"),
            models.Index(fields=["date_submitted"], name="idx_date_submitted"),
            models.Index(fields=["date_reviewed"], name="idx_date_reviewed"),
            models.Index(fields=["reviewer"], name="idx_reviewer"),
            models.Index(
                fields=["insult_reference_id"], name="idx_insult_reference_id"
            ),
            models.Index(
                fields=["insult", "insult_reference_id"], name="idx_insult_ref_id"
            ),
        ]

    def mark_review_not_reclassified(self, reviewer: User):
        """Marks the review as Not reclassified.

        This method sets the status of the review to "SCE" (Same Classification - nsfw) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Args:
            reviewer(User) User Type Representation of the API Administrator making the determination of the review.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = self.STATUS.SAME_CLASSIFICATION
            self.reviewer = reviewer
            self.date_reviewed = settings.GLOBAL_NOW
            logger.success(f"Marked {self.insult_reference_id} as Not Reclassified")
            self.save(update_fields=["status", "reviewer", "date_reviewed"])
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )

    def mark_review_recategorized(self, reviewer: User):
        try:
            self.status = self.STATUS.NEW_CATEGORY
            self.reviewer = reviewer
            self.date_reviewed = settings.GLOBAL_NOW
            logger.success(f"Marked {self.insult_reference_id} as Recategorized")
            self.save()
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )

    def mark_review_not_recatagoized(self):
        """Marks the review as reclassified.

        This method sets the status of the review to "SJC" (Same Joke Category) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Args:
            reviewer(User) User Type Representation of the API Administrator making the determination of the review.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = self.STATUS.SAME_CATEGORY
            self.date_reviewed = settings.GLOBAL_NOW
            self.save(update_fields=["status", "date_reviewed"])
            logger.success(f"Marked {self.insult_reference_id} as Reclassified")
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )

    def mark_review_removed(self):
        """Marks the review as removed.

        This method sets the status of the review to "x" and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.
        Args:
            reviewer(User) User Type Representation of the API Administrator making the determination of the review.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = self.STATUS.REMOVED
            self.date_reviewed = settings.GLOBAL_NOW
            self.save(update_fields=["status", "date_reviewed"])
            logger.success(f"Marked {self.insult_reference_id} as Reclassified")
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )

    def mark_review_reclassified(self, reviewer: User):
        """Marks the review as reclassified.

            This method sets the status of the review to "NCE" (New Classification - nsfw) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.
        `   Args:
                reviewer(User) User Type Representation of the API Administrator making the determination of the review.

            Logs:
                Exception: If there is an error updating the review.
        """

        try:
            self.status = self.STATUS.NEW_CLASSIFICATION
            self.reviewer = reviewer
            self.date_reviewed = settings.GLOBAL_NOW
            logger.success(f"Marked {self.insult_reference_id} as Reclassified")
            self.save(update_fields=["status", "reviewer", "date_reviewed"])
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )


@receiver(post_save, sender=InsultReview)
def increment_report_count(sender, instance, created, **kwargs):
    """
    Increments the report count for an insult when a new InsultReview is created.

    This signal handler updates the reports_count field of the related Insult instance
    whenever a new InsultReview is saved. It ensures the report count reflects the
    current number of reviews associated with the insult.
    """
    if created:
        if instance.insult_id:
            instance.insult.reports_count = instance.insult.reports.count()
            instance.insult.save(update_fields=["reports_count"])


@receiver(post_save, sender=InsultReview)
def flag_insult(sender, instance, created, **kwargs):
    """
    Flags the insult as needing review when a new InsultReview is created.

    This signal handler updates the status field of the related Insult instance
    whenever a new InsultReview is saved. It ensures the related Insult is flagged for review and is not visible in the API.

    Args:
        sender: The model class sending the signal.
        instance: The instance of InsultReview being saved.
        created: Boolean indicating if a new record was created.
        **kwargs: Additional keyword arguments.

    Returns:
        None
    """
    if created:
        # Connect InsultReview to Insult
        instance.set_insult()  # Ensure the related Insult is set
        # Set the insult status to FLAGGED
        instance.insult.status = Insult.STATUS.FLAGGED
        instance.insult.save(update_fields=["status", "reports_count"])


@receiver(post_delete, sender=InsultReview)
def decrement_report_count(sender, instance, **kwargs):
    """
    Decrements the report count for an insult when an InsultReview is deleted.

    This signal handler updates the reports_count field of the related Insult instance
    whenever an InsultReview is deleted. It ensures the report count reflects the
    current number of reviews associated with the insult.
    """
    if instance.insult_id:
        insult = instance.insult
        if insult:
            insult.reports_count = insult.reports.count()
            insult.save(update_fields=["reports_count"])
        return

"""
module: applications.API.models


This module defines the Insult and InsultReview models, which are used to manage insults and their reviews in the system, as well as the InsultCategory model for insult resource categorization. Each model contains methods for manipulating the associated resource.
    
For instance, the Insult model's methods allow for removing, approving, and re-categorizing task. The models and their methods are designed to work with Django's ORM and include various fields and methods for managing the data effectively.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, models
from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin
from loguru import logger


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
        raise Base64EncoderException(str(e)) from e


class PublicInsultCategoryManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .exclude(category_key__in=settings.IGNORED_INSULT_CATEGORIES)
        )


class InsultCategory(ExportModelOperationsMixin("insult_categories"), models.Model):

    category_key = models.CharField(max_length=5, unique=True, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    theme = models.ForeignKey(
        "Theme", on_delete=models.CASCADE, related_name="insult_categories"
    )

    def __str__(self):
        return f"{self.category_key}"

    def lower(self):
        """Returns the name of the category in lowercase."""
        return self.name.lower()

    @property
    def count(self) -> int:
        """
        Returns the count of active insults in this category.

        NOTE: This property can cause N+1 queries when serializing multiple categories.
        Consider using QuerySet annotation instead:

        Example:
            from django.db.models import Count, Q
            categories = InsultCategory.objects.annotate(
                active_insult_count=Count('insult', filter=Q(insult__status=Insult.STATUS.ACTIVE))
            )
            # Then access: category.active_insult_count instead of category.count
        """
        return Insult.objects.filter(category=self, status=Insult.STATUS.ACTIVE).count()

    public = PublicInsultCategoryManager()
    objects = models.Manager()

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


class Theme(models.Model):
    theme_key = models.CharField(max_length=5, unique=True, primary_key=True)
    theme_name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return f"{self.theme_name}({self.theme_key})"

    def lower(self):
        """Returns the name of the theme in lowercase."""
        return self.theme_name.lower()

    class Meta:
        db_table = "themes"
        verbose_name = _("Theme")
        verbose_name_plural = _("Themes")
        managed = True
        ordering = ["theme_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["theme_key", "theme_name"], name="unique_theme_key_name"
            ),
        ]
        indexes = [
            models.Index(fields=["theme_key"], name="idx_theme_key"),
            models.Index(fields=["theme_name"], name="idx_theme_name"),
        ]


class PublicInsultManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status=Insult.STATUS.ACTIVE)
            .exclude(category__category_key__in=settings.IGNORED_INSULT_CATEGORIES)
        )


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

    content = models.TextField(
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
    theme = models.ForeignKey(Theme, on_delete=models.PROTECT)
    category = models.ForeignKey(InsultCategory, on_delete=models.PROTECT)
    nsfw = models.BooleanField()
    added_on = models.DateField(null=False, blank=False, auto_now_add=True)
    reports_count = models.PositiveIntegerField(default=0, null=True)
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

    def set_reference_id(self):
        """
        Generates and assigns a unique reference ID for the insult if it does not already have one.

        This method creates a unique reference ID using a random prefix and a base64-encoded insult_id pk.
        Since the insult_id is unique, the reference ID will be unique by design.

        Returns:
            str: The generated reference ID
        """
        # Only generate reference_id if it is not set and insult_id exists
        if self.insult_id and not self.reference_id:
            # Generate reference_id - unique by design since based on unique PK
            prefix = secrets.choice(settings.INSULT_REFERENCE_ID_PREFIX_OPTIONS)
            self.reference_id = f"{prefix}_{encode_base64(int(self.insult_id))}"
            # Only update the reference_id field
            self.save(update_fields=["reference_id"])
            return self.reference_id

    def __str__(self) -> str:
        return f"{self.reference_id} - ({self.category}) - NSFW: {self.nsfw}"

    def clean(self):
        """
        Validates that the insult's theme matches its category's theme.

        This method is called during form validation and when full_clean() is called.
        It ensures data consistency by enforcing that an insult's theme must always
        match the theme of its category.

        Raises:
            ValidationError: If theme doesn't match category's theme.
        """
        super().clean()
        if self.category and self.theme:
            if self.category.theme_id != self.theme_id:
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    {
                        "theme": f"Insult theme must match category theme. "
                        f'Category "{self.category.name}" belongs to theme "{self.category.theme.theme_name}", '
                        f'but insult is assigned to theme "{self.theme.theme_name}".'
                    }
                )

    def save(self, *args, **kwargs):
        """
        Override save to automatically set theme from category.

        This ensures that the insult's theme always matches its category's theme,
        preventing data inconsistency. If a category is set, the theme will be
        automatically derived from it.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        # Automatically set theme from category to ensure consistency
        if self.category_id and not self.theme_id:
            self.theme = self.category.theme
        elif self.category_id and self.theme_id:
            # If both are set, ensure they match
            if self.category.theme_id != self.theme_id:
                logger.warning(
                    f"Insult theme mismatch detected for {self.reference_id or 'new insult'}. "
                    f"Automatically updating theme to match category's theme."
                )
                self.theme = self.category.theme

        super().save(*args, **kwargs)

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
        for prefix in settings.INSULT_REFERENCE_ID_PREFIX_OPTIONS:
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

        Also automatically updates the theme to match the new category's theme,
        ensuring data consistency.

        Args:
            new_category (InsultCategory): The new category to assign to the Insult.

        Logs:
            Exception: If an error occurs while re-categorizing the object.

        Returns:
            None
        """
        try:
            self.category = new_category
            # Automatically update theme to match new category's theme
            self.theme = new_category.theme
            self.last_modified = settings.GLOBAL_NOW
            self.save(update_fields=["category", "theme", "last_modified"])
            logger.success(
                f"Successfully Re-Categorized {self.reference_id} to {self.category} "
                f"(theme: {self.theme.theme_name})"
            )
        except Exception as e:
            logger.error(
                f"Unable to Re-Categorize {self.reference_id} to {new_category}: {e}"
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

    # NOTE: Add the PublicInsultManager to the Insult model
    public = PublicInsultManager()
    objects = models.Manager()

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


class InsultReview(ExportModelOperationsMixin("jokeReview"), models.Model):
    """
    Model representing an Insult Review with methods for marking different review types.

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
    review_type = models.CharField(
        max_length=2, choices=REVIEW_TYPE.choices, null=False, blank=False
    )
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
                f"Reviews Must Be Associated with a VALID Insult. Insult with reference ID {self.insult_reference_id} does not exist."
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

    def mark_review_recategorized(self, reviewer: User):
        try:
            self.status = self.STATUS.NEW_CATEGORY
            self.reviewer = reviewer
            self.date_reviewed = settings.GLOBAL_NOW
            logger.success(f"Marked {self.insult_reference_id} as Recategorized")
            self.save(update_fields=["status", "reviewer", "date_reviewed"])
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )

    def mark_review_not_recatagoized(self, reviewer: Optional[User] = None):
        """Marks the review as not requiring recategorization.

        This method sets the status of the review to "SJC" (Same Joke Category) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as not recategorized.

        Args:
            reviewer (User, optional): User Type Representation of the API Administrator making the determination of the review.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = self.STATUS.SAME_CATEGORY
            if reviewer:
                self.reviewer = reviewer
            self.date_reviewed = settings.GLOBAL_NOW
            self.save(update_fields=["status", "reviewer", "date_reviewed"])
            logger.success(f"Marked {self.insult_reference_id} as Not Recategorized")
        except Exception as e:
            logger.error(
                f"ERROR: Unable to Update {self.insult_reference_id}: {str(e)}"
            )

    def mark_review_removed(self, reviewer: Optional[User] = None):
        """Marks the review as removed.

        This method sets the status of the review to "REMOVED" and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as removed.

        Args:
            reviewer (User, optional): User Type Representation of the API Administrator making the determination of the review.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = self.STATUS.REMOVED
            if reviewer:
                self.reviewer = reviewer
            self.date_reviewed = settings.GLOBAL_NOW
            self.save(update_fields=["status", "reviewer", "date_reviewed"])
            logger.success(f"Marked {self.insult_reference_id} as Removed")
        except Exception as e:
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
            # Composite indexes for common queries
            models.Index(
                fields=["status", "-date_submitted"], name="idx_status_date_sub"
            ),
        ]


# SECTION - Model Signals


@receiver(post_save, sender=Insult)
def generate_reference_id(sender, instance, created, **kwargs):
    if created:
        ref_id = instance.set_reference_id()
        logger.info(
            f"Successfully Created and Set Reference ID for {instance.insult_id} -> {ref_id}"
        )


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
        if not instance.insult:
            instance.set_insult()  # Ensure the related Insult is set

        # Use atomic update with F() expression for performance
        if instance.insult_id:
            Insult.objects.filter(pk=instance.insult_id).update(
                status=Insult.STATUS.FLAGGED, reports_count=F("reports_count") + 1
            )


@receiver(post_delete, sender=InsultReview)
def decrement_report_count(sender, instance, **kwargs):
    """
    Decrements the report count for an insult when an InsultReview is deleted.

    This signal handler updates the reports_count field of the related Insult instance
    whenever an InsultReview is deleted. It ensures the report count reflects the
    current number of reviews associated with the insult.
    """
    if instance.insult_id:
        # Use atomic update with F() expression for performance
        Insult.objects.filter(pk=instance.insult_id).update(
            reports_count=F("reports_count") - 1
        )

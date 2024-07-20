import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from loguru import logger

NOW = datetime.datetime.now()


class Insult(models.Model):
    """
    Summary:
    Model representing an Insult with various attributes and methods for manipulation.

    Explanation:
    This model represents an Insult with fields like content, category, explicit, added_on, added_by, last_modified, and status. It includes methods for removing, approving, marking for review, re-categorizing, and reclassifying insults.

    Methods:
        - remove_insult(): Removes insult visibility from the API (Soft Delete).
        - approve_insult(): Adds a Pending insult to the API.
        - mark_insult_for_review(): Removes insult visibility from the API.
        - re_categorize(new_category): Re-categorizes the object with a new category.
        - reclassify(explicit_status): Changes the category of the insult.
    """

    class Meta:
        db_table = "insults"
        ordering = ["explicit", "category"]
        verbose_name = "Insult/Joke"
        verbose_name_plural = "Insults/Jokes"
        managed = True
        indexes = [
            models.Index(fields=["category"], name="idx_category"),
            models.Index(fields=["category", "explicit"], name="idx_explicit_category"),
            models.Index(fields=["explicit"], name="idx_explicit"),
            models.Index(fields=["added_by"], name="idx_added_by"),
        ]
        indexes = [
            models.Index(fields=["category"], name="idx_category"),
            models.Index(fields=["category", "explicit"], name="idx_explicit_category"),
            models.Index(fields=["explicit"], name="idx_explicit"),
            models.Index(fields=["added_by"], name="idx_added_by"),
        ]

    class CATEGORY(models.TextChoices):
        POOR = "P", _("poor")
        FAT = "F", _("fat")
        UGLY = "U", _("ugly")
        STUPID = "S", _("stupid")
        SNOWFLAKE = "SNWF", _("snowflake")
        OLD = "O", _("old")
        DADDY_OLD = "DO", _("old_daddy")
        DADDY_STUPID = "DS", _("stupid_daddy")
        NASTY = "N", _("nasty")
        TALL = "T", _("tall")
        TEST_CATEGORY = "TEST", _("testing")
        SKINNY = "SKN", _("skinny")
        BALD = "B", _("bald")
        HAIRY = "H", _("hairy")
        LAZY = "L", _("lazy")
        SHORT = "SRT", _("short")

    class STATUS(models.TextChoices):
        ACTIVE = "A", _("Active")
        REMOVED = "X", _("Inactive/Removed")
        PENDING = "P", _("Pending")
        REJECTED = "R", _("Rejected")

    content = models.CharField(
        max_length=65535,
        null=False,
        blank=False,
        error_messages="Insults must have content",
    )
    category = models.CharField(
        null=False, blank=False, max_length=5, choices=CATEGORY.choices
    )
    explicit = models.BooleanField(default=False)
    added_on = models.DateField(null=False, blank=False, auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.PROTECT)
    last_modified = models.DateTimeField(auto_now=True, blank=True, null=True)
    status = models.CharField(
        null=False,
        blank=False,
        max_length=2,
        default=STATUS.PENDING,
        choices=STATUS.choices,
    )

    def __str__(self):
        return (
            f"({self.category}) - NSFW: {self.explicit} - {self.pk} ({self.added_by}) "
        )

    def remove_insult(self):
        """Removes insult visibility from the API. (Soft Delete)
        Logs:
            Success: Logs the PK of the modified Insult Instance
            Exception: If the Insult unable top be removed.
            Exception: If the Insult unable top be removed.
        Returns:
            None
        """

        try:
            self.status = "X"
            self.last_modified = settings.GLOBAL_NOW
            logger.success(f"Successfully Removed {self.pk}")
        except Exception as e:
            logger.error(f"Unable to Remove Insult ({self.pk}): {e}")

    def approve_insult(self):
        """Adds a Pending insult to the API.

        Updates the Insult.status of the current object to approved, making the current instance discoverable by the API Serializers and Filters.
        Logs:
            Success: Logs the PK of the modified Insult Instance
            Exception: If the Insult is unable top be removed.

        Returns:
            None
        """

        try:
            self.status = "A"
            self.last_modified = settings.GLOBAL_NOW
            logger.success(f"Successfully Approved {self.pk}")
        except Exception as e:
            logger.error(f"Unable to Approve Insult({self.pk}): {e}")

    def mark_insult_for_review(self):
        """Removes insult visibility from from the API.

        Logs:
            Exception: If the Insult is unable top be removed.

        Returns:
            None
        """

        try:
            self.status = "P"
            logger.warning(f"Successfully Sent to Review {self.pk}")
        except Exception as e:
            logger.error(f"Unable to Send For Review({self.pk}): {e}")

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
            logger.success(f"Successfully Re-Categorized {self.pk} to {self.category}")
            self.category = new_category
            logger.success(f"Successfully Re-Categorized {self.pk} to {self.category}")
        except Exception as e:
            logger.error(f"Unable to RE-Categorized Insult {self.pk}: {e}")
            logger.error(f"Unable to RE-Categorized Insult {self.pk}: {e}")

    def reclassify(self, explicit_status):
        """Changes the category of the insult

        Logs:
            Exception: If the Insult is unable top be removed.

        Returns:
            None
        """
        try:
            self.explicit = explicit_status
            self.explicit = explicit_status
            logger.success(f"Successfully reclassified {self.pk} to {self.explicit}")
        except Exception as e:
            logger.error(f"Unable to ReClassify Insult {self.pk}: {e}")


class InsultReview(models.Model):
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
        RECATAGORIZE = "RC", _("Joke Recategorization")
        REMOVAL = "RX", _("Joke Removal")

    class STATUS(models.TextChoices):
        PENDING = "P", _("Pending")
        NEW_CLASSIFICATION = "NCE", _("Completed - New Explicitly Setting")
        SAME_CLASSIFICATION = "SCE", _("Completed - No New Explicitly Setting")
        NEW_CATAGORY = "NJC", _("Completed - Assigned to New Catagory")
        SAME_CATAGORY = "SJC", _("Completed - No New Catagory Assigned")
        REMOVED = "X", _("Completed - Joke Removed")

    insult_id = models.ForeignKey(Insult, on_delete=models.CASCADE)
    anonymous = models.BooleanField(default=False)
    reporter_first_name = models.CharField(max_length=80, null=True, blank=True)
    reporter_last_name = models.CharField(max_length=80, null=True, blank=True)
    post_review_contact_desired = models.BooleanField(default=False)
    reporter_email = models.EmailField(null=True, blank=True)
    date_submitted = models.DateField(auto_now=True)
    date_reviewed = models.DateField(null=True, blank=True)
    rationale_for_review = models.TextField()
    review_type = models.CharField(choices=REVIEW_TYPE.choices, null=False, blank=False)
    status = models.CharField(
        choices=STATUS.choices, default=STATUS.PENDING, null=True, blank=True
    )

    def __str__(self):
        return f"Joke: {self.insult_id} - Review Type: {self.review_type} - Submitted: {self.date_submitted}({self.status})"

    class Meta:
        db_table = "reported_jokes"
        ordering = ["status", "-date_submitted"]
        verbose_name = "Joke Needing Review"
        verbose_name_plural = "Jokes Needing Review"
        get_latest_by = ["-date_submitted"]

    def mark_review_not_reclassified(self):
        """Marks the review as Not reclassified.

        This method sets the status of the review to "SCE" (Same Classification - Explicit) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = "SCE"
            self.date_reviewed = NOW
            logger.success(f"Marked {self.pk} as Not Reclassified")
        except Exception as e:
            logger.error(f"ERROR: Unable to Update {self.pk}: {str(e)}")

    def mark_review_recatagoized(self):
        """Marks the review as re-categorized.

        This method sets the status of the review to "NJC" (New Joke Category) and updates the `date_reviewed` attribute to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Logs:
            Exception: If there is an error updating the review.

        """

        try:
            self.status = "NJC"
            self.date_reviewed = NOW
            logger.success(f"Marked {self.pk} as Reclassified")
        except Exception as e:
            logger.error(f"ERROR: Unable to Update {self.pk}: {str(e)}")

    def mark_review_not_recatagoized(self):
        """Marks the review as reclassified.

        This method sets the status of the review to "SJC" (Same Joke Category) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = "SJC"
            self.date_reviewed = NOW
            logger.success(f"Marked {self.pk} as Reclassified")
        except Exception as e:
            logger.error(f"ERROR: Unable to Update {self.pk}: {str(e)}")

    def mark_review_removed(self):
        """Marks the review as removed.

        This method sets the status of the review to "x" and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = "x"
            self.date_reviewed = NOW
            logger.success(f"Marked {self.pk} as Reclassified")
        except Exception as e:
            logger.error(f"ERROR: Unable to Update {self.pk}: {str(e)}")

    def mark_review_reclassified(self):
        """Marks the review as reclassified.

        This method sets the status of the review to "NCE" (New Classification - Explicit) and updates the date_reviewed field to the current date and time. It also logs a success message indicating that the review has been marked as reclassified.

        Logs:
            Exception: If there is an error updating the review.
        """

        try:
            self.status = "NCE"
            self.date_reviewed = NOW
            logger.success(f"Marked {self.pk} as Reclassified")
        except Exception as e:
            logger.error(f"ERROR: Unable to Update {self.pk}: {str(e)}")

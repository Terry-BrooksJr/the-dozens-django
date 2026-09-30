"""Transactional email classes for API user accounts."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.context import make_context
from django.template.loader import get_template
from django.template.loader_tags import BlockNode
from django.templatetags.static import static
from djoser.email import ConfirmationEmail
from loguru import logger
from rest_framework.authtoken.models import Token


def email_asset_url(path, site_url):
    """Public URL for a static asset referenced from an email.

    Mail clients load images and fonts from their own servers, so the URL
    must not depend on which environment sent the email. Prefers
    ``EMAIL_ASSET_BASE_URL``; otherwise falls back to ``static()``, prefixing
    relative URLs (local storage) with ``site_url``.
    """
    base = getattr(settings, "EMAIL_ASSET_BASE_URL", "")
    if base:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"
    url = static(path)
    if url.startswith(("http://", "https://")):
        return url
    return f"{site_url.rstrip('/')}/{url.lstrip('/')}"


def email_font_urls(site_url):
    """Template context entries for the brand fonts used by the email templates."""
    return {
        "header_font_url": email_asset_url("fonts/caloriesuit.woff2", site_url),
        "body_font_url": email_asset_url(
            "fonts/JuliusSansOne-Regular.woff2", site_url
        ),
    }


class WelcomeEmail(ConfirmationEmail):
    """Account confirmation email that doubles as an API onboarding message.

    Adds the user's API token and links to the API docs and GraphQL
    playground to the template context.
    """

    template_name = "email/welcome.html"

    def get_context_data(self):
        """Extend the Djoser context with the API key and documentation URLs.

        Creates the user's DRF token if one does not already exist.
        """
        context = super().get_context_data()
        user = context["user"]

        token, created = Token.objects.get_or_create(user=user)

        logger.info(
            "Welcome email context prepared | user={} token_status={}",
            user.username,
            "created" if created else "existing",
        )

        protocol = context.get("protocol", "https")
        domain = context.get("domain")
        base = f"{protocol}://{domain}"

        context.update(
            {
                "api_key": token.key,
                "site_url": base,
                "site_domain": domain,
                "docs_url": f"{base}/api/redoc",
                "swagger_url": f"{base}/api/swagger/",
                "graphql_url": f"{base}/graphql/playground",
                **email_font_urls(base),
            }
        )
        return context

    def send(self, to=None, fail_silently=False, **kwargs):
        """Send the email, logging the attempt and its outcome.

        When ``to`` is omitted the message is assumed to be already rendered
        (the django-mailer delivery path) and is sent directly.

        Args:
            to: Recipient addresses; falls back to ``self.to``.
            fail_silently: Suppress send errors when ``True``.
            **kwargs: Passed through to Djoser's ``send``.

        Raises:
            Exception: Re-raises any delivery failure after logging it.
        """
        recipients = to or getattr(self, "to", None) or []
        logger.info("Welcome email send attempt | to={}", recipients)

        try:
            if to is not None:
                if fail_silently is False and not kwargs:
                    result = super().send(to)
                else:
                    result = super().send(to, fail_silently=fail_silently, **kwargs)
            else:
                # django-mailer delivery path: email already rendered, self.to already set.
                result = EmailMultiAlternatives.send(self, fail_silently=fail_silently)

            logger.info("Welcome email send success | to={}", recipients)
            return result

        except Exception:
            logger.error("Welcome email send failure | to={}", recipients)
            raise


# Per-outcome presentation for email/submission_review.html. Every key the
# template reads from ``o`` must exist on every outcome.
REVIEW_OUTCOMES = {
    # -- Pending - New ---------------------------------------------------
    "approved": {
        "subject": "Your joke made the cut! 🎉",
        "preheader": "Your joke is officially in the collection.",
        "ribbon_label": "✅ Approved",
        "ribbon_color": "#beda00",
        "ribbon_text_color": "#3a0038",
        "headline": "Look at you, {name}! 🔥",
        "body": "Your joke passed review and is now live in the Yo' Momma API. "
        "Developers everywhere can pull it into their apps starting today. "
        "Thanks for adding to the collection.",
        "is_live": True,
    },
    "modified": {
        "subject": "Your joke is live, with a little touch-up ✏️",
        "preheader": "Approved with a quick edit from our moderators.",
        "ribbon_label": "✏️ Approved with Edits",
        "ribbon_color": "#ffb020",
        "ribbon_text_color": "#3a0038",
        "headline": "Nice one, {name}!",
        "body": "Your joke passed review and is now live. Our moderators made a small "
        "edit first, usually for clarity, spelling, or to fit the collection's "
        "guidelines. Here's what changed.",
        "is_live": True,
    },
    "rejected": {
        "subject": "An update on your joke submission",
        "preheader": "Thanks for submitting. Here's what our moderators decided.",
        "ribbon_label": "🚫 Not Accepted",
        "ribbon_color": "#e0364a",
        "ribbon_text_color": "#ffffff",
        "headline": "Hey {name},",
        "body": "Thanks for sending this in. After review, our moderators decided not "
        "to add it to the collection this time. It happens to the best of us, "
        "and we'd still like to see your next one.",
        "is_live": False,
    },
    # -- Flagged for Review ----------------------------------------------
    "reclassified": {
        "subject": "Your joke's rating was updated",
        "preheader": "After a community report, we changed your joke's NSFW rating.",
        "ribbon_label": "🔞 Rating Updated",
        "ribbon_color": "#6a1b9a",
        "ribbon_text_color": "#ffffff",
        "headline": "Hey {name},",
        "body": "Someone reported your joke, and after review our moderators changed "
        "its NSFW rating. It's still live in the collection with the rating "
        "shown below.",
        "is_live": True,
    },
    "recategorized": {
        "subject": "Your joke found a new home",
        "preheader": "After a community report, we moved your joke to a new category.",
        "ribbon_label": "🗂️ Category Updated",
        "ribbon_color": "#1565c0",
        "ribbon_text_color": "#ffffff",
        "headline": "Hey {name},",
        "body": "Someone reported your joke, and after review our moderators moved it "
        "to a better-fitting category. It's still live in the collection under "
        "the category shown below.",
        "is_live": True,
    },
    "removed": {
        "subject": "Your joke was removed from the collection",
        "preheader": "After a community report, we removed your joke.",
        "ribbon_label": "🗑️ Removed",
        "ribbon_color": "#e0364a",
        "ribbon_text_color": "#ffffff",
        "headline": "Hey {name},",
        "body": "Someone reported your joke, and after review our moderators removed "
        "it from the collection. It's no longer available through the API. "
        "We'd still love to see your next one.",
        "is_live": False,
    },
    "kept": {
        "subject": "Good news: your joke stays",
        "preheader": "A report on your joke was reviewed and dismissed.",
        "ribbon_label": "🛡️ Report Dismissed",
        "ribbon_color": "#beda00",
        "ribbon_text_color": "#3a0038",
        "headline": "You're in the clear, {name}!",
        "body": "Someone reported your joke, but after review our moderators decided "
        "no changes were needed. It's back in the collection exactly as it was.",
        "is_live": True,
    },
}


class SubmissionReviewEmail(EmailMultiAlternatives):
    """Tells a joke's author the outcome of a moderator review.

    Renders the ``subject``, ``text_body`` and ``html_body`` blocks of
    ``email/submission_review.html`` separately (like Djoser's templated
    emails) but builds a plain ``EmailMultiAlternatives``, so django-mailer
    can pickle it and later call ``send()`` with no arguments.

    Args:
        outcome: One of ``REVIEW_OUTCOMES``' keys.
        context: Template context (see the template for the keys it reads).
            ``site_url`` is required; ``hero_image_url`` defaults to the
            outcome's image under ``assets/``, served from
            ``EMAIL_ASSET_BASE_URL`` when set.
        to: Recipient addresses.

    Raises:
        KeyError: If ``outcome`` is not a known review outcome.
    """

    template_name = "email/submission_review.html"

    def __init__(self, outcome, context, to):
        outcome_config = REVIEW_OUTCOMES[outcome]
        context = {
            **context,
            "outcome": outcome,
            "o": {
                **outcome_config,
                "headline": outcome_config["headline"].format(
                    name=context.get("submitter_name", "")
                ),
            },
        }
        context.setdefault(
            "hero_image_url",
            email_asset_url(f"assets/{outcome}.png", context["site_url"]),
        )
        for key, url in email_font_urls(context["site_url"]).items():
            context.setdefault(key, url)

        blocks = self._render_blocks(context)
        super().__init__(
            subject=blocks["subject"],
            body=blocks["text_body"],
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
        )
        self.attach_alternative(blocks["html_body"], "text/html")

    def _render_blocks(self, context):
        """Render each top-level ``{% block %}`` of the template on its own."""
        template = get_template(self.template_name).template
        ctx = make_context(context)
        with ctx.bind_template(template):
            return {
                node.name: node.render(ctx).strip()
                for node in template.nodelist.get_nodes_by_type(BlockNode)
            }

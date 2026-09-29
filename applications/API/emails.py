"""Transactional email classes for API user accounts."""

from django.core.mail import EmailMultiAlternatives
from djoser.email import ConfirmationEmail
from loguru import logger
from rest_framework.authtoken.models import Token


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

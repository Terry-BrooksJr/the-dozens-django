from django.core.mail import EmailMultiAlternatives
from djoser.email import ConfirmationEmail
from loguru import logger
from rest_framework.authtoken.models import Token


class WelcomeEmail(ConfirmationEmail):
    template_name = "email/welcome.html"

    def get_context_data(self):
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

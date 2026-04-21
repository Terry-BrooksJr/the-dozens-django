"""
Django management command to perform a health check on the LaunchDarkly client integration. This command initializes the client, evaluates a specified feature flag, and reports the result. It is designed for use in operational monitoring and diagnostics to confirm that the LaunchDarkly client is properly configured and can successfully evaluate flags.
"""

from django.core.management.base import BaseCommand
from ldclient import Context

from applications.ld_integration.client import get_client


class Command(BaseCommand):
    """
    Management command that verifies the LaunchDarkly client is operational. It evaluates a simple feature flag and reports the result to stdout.

    The command is intended for health checks and diagnostics, allowing operators or monitoring systems to confirm connectivity and flag evaluation behavior with minimal impact.

    Args:
        parser: The argument parser instance used to define command-line options.

    """

    help = "Checks LaunchDarkly client initialization and evaluates a harmless flag"

    def add_arguments(self, parser):
        parser.add_argument("--flag", default="ld-healthcheck-flag")

    def handle(self, *args, **opts):
        flag_key = opts["flag"]
        client = get_client()
        ctx = Context.builder("healthcheck").build()
        val = client.variation(flag_key, ctx, False)
        self.stdout.write(self.style.SUCCESS(f"LD ok. {flag_key}={val!r}"))

"""
Tests for the `ld_healthcheck` management command.

Covers:
- Default flag key ("ld-healthcheck-flag") is used when --flag is omitted
- A custom --flag value is passed through to client.variation()
- The evaluated flag value is written to stdout via self.style.SUCCESS
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase


class LdHealthcheckCommandTests(TestCase):
    @patch("applications.ld_integration.management.commands.ld_healthcheck.get_client")
    def test_default_flag_key_is_used(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.variation.return_value = True
        mock_get_client.return_value = mock_client

        out = StringIO()
        call_command("ld_healthcheck", stdout=out)

        call_args = mock_client.variation.call_args
        self.assertEqual(call_args.args[0], "ld-healthcheck-flag")
        self.assertIn("ld-healthcheck-flag=True", out.getvalue())

    @patch("applications.ld_integration.management.commands.ld_healthcheck.get_client")
    def test_custom_flag_key_is_used(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.variation.return_value = False
        mock_get_client.return_value = mock_client

        out = StringIO()
        call_command("ld_healthcheck", "--flag", "custom-flag", stdout=out)

        call_args = mock_client.variation.call_args
        self.assertEqual(call_args.args[0], "custom-flag")
        self.assertIn("custom-flag=False", out.getvalue())

    @patch("applications.ld_integration.management.commands.ld_healthcheck.get_client")
    def test_default_variation_value_is_false(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.variation.return_value = False
        mock_get_client.return_value = mock_client

        call_command("ld_healthcheck", stdout=StringIO())

        call_args = mock_client.variation.call_args
        self.assertEqual(call_args.args[-1], False)

"""Tests for applications.API.errors

Covers:
- ERROR_TEMPLATES / YO_MOMMA_OVERRIDES shape and consistency.
- _build_payload payload construction.
- StandardErrorResponses OpenAPI examples match runtime templates.
- Response-set helpers (classmethods + module-level convenience functions).
- yo_momma_exception_handler for unhandled exceptions, themed overrides,
  non-themed normalization, header preservation, and logging levels.
"""

from unittest.mock import MagicMock, patch

from django.http import Http404
from django.test import SimpleTestCase
from drf_spectacular.utils import OpenApiResponse
from rest_framework import exceptions, serializers, status

from applications.API.errors import (
    ERROR_TEMPLATES,
    YO_MOMMA_OVERRIDES,
    StandardErrorResponses,
    _build_payload,
    get_category_list_responses,
    get_insult_crud_responses,
    get_public_list_responses,
    yo_momma_exception_handler,
)

LOGGER_TARGET = "applications.API.errors.logger"


def _example_value(response: OpenApiResponse) -> dict:
    """Return the single example payload attached to an OpenApiResponse."""
    assert len(response.examples) == 1
    return response.examples[0].value


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class ErrorTemplatesTests(SimpleTestCase):
    def test_every_template_has_detail_and_code_strings(self):
        for status_code, template in ERROR_TEMPLATES.items():
            with self.subTest(status_code=status_code):
                self.assertEqual(set(template), {"detail", "code"})
                self.assertIsInstance(template["detail"], str)
                self.assertTrue(template["detail"])
                self.assertIsInstance(template["code"], str)
                self.assertTrue(template["code"])

    def test_templates_cover_expected_status_codes(self):
        self.assertEqual(
            set(ERROR_TEMPLATES),
            {400, 401, 403, 404, 405, 429, 500, 503},
        )

    def test_template_codes_are_unique(self):
        codes = [t["code"] for t in ERROR_TEMPLATES.values()]
        self.assertEqual(len(codes), len(set(codes)))

    def test_overrides_reuse_templates(self):
        self.assertEqual(set(YO_MOMMA_OVERRIDES), {400, 401, 403, 404, 500})
        for status_code, template in YO_MOMMA_OVERRIDES.items():
            with self.subTest(status_code=status_code):
                self.assertIs(template, ERROR_TEMPLATES[status_code])


# ---------------------------------------------------------------------------
# _build_payload
# ---------------------------------------------------------------------------


class BuildPayloadTests(SimpleTestCase):
    def test_minimal_payload(self):
        self.assertEqual(
            _build_payload(status_code=418, detail="teapot"),
            {"detail": "teapot", "code": "error", "status_code": 418},
        )

    def test_custom_code(self):
        payload = _build_payload(status_code=400, detail="bad", code="bad_request")
        self.assertEqual(payload["code"], "bad_request")

    def test_extra_is_merged(self):
        payload = _build_payload(
            status_code=400, detail="bad", extra={"errors": {"field": ["req"]}}
        )
        self.assertEqual(payload["errors"], {"field": ["req"]})
        self.assertEqual(payload["detail"], "bad")

    def test_empty_extra_is_ignored(self):
        payload = _build_payload(status_code=400, detail="bad", extra={})
        self.assertEqual(set(payload), {"detail", "code", "status_code"})

    def test_extra_can_override_base_keys(self):
        payload = _build_payload(status_code=400, detail="bad", extra={"code": "x"})
        self.assertEqual(payload["code"], "x")


# ---------------------------------------------------------------------------
# OpenAPI documentation responses
# ---------------------------------------------------------------------------


class StandardErrorResponsesTests(SimpleTestCase):
    # attribute name -> (status code, overridden detail or None for template)
    EXPECTED = {
        "UNAUTHORIZED": (401, None),
        "PERMISSION_DENIED": (403, None),
        "OWNER_ONLY_ACCESS": (403, "You can only modify resources that you own."),
        "RESOURCE_NOT_FOUND": (404, None),
        "INSULT_NOT_FOUND": (404, "Insult not found."),
        "CATEGORY_NOT_FOUND": (404, "Category not found."),
        "NO_RESULTS_FOUND": (
            404,
            "No results found matching the provided criteria.",
        ),
        "METHOD_NOT_ALLOWED": (405, None),
        "BAD_REQUEST": (400, None),
        "RATE_LIMIT_EXCEEDED": (429, None),
        "INTERNAL_SERVER_ERROR": (500, None),
        "SERVICE_UNAVAILABLE": (503, None),
    }

    def test_examples_match_runtime_templates(self):
        for attr, (status_code, detail_override) in self.EXPECTED.items():
            with self.subTest(response=attr):
                response = getattr(StandardErrorResponses, attr)
                self.assertIsInstance(response, OpenApiResponse)
                self.assertTrue(response.description)

                value = _example_value(response)
                template = ERROR_TEMPLATES[status_code]
                self.assertEqual(value["status_code"], status_code)
                self.assertEqual(value["code"], template["code"])
                self.assertEqual(value["detail"], detail_override or template["detail"])

    def test_examples_are_response_only(self):
        for attr in self.EXPECTED:
            with self.subTest(response=attr):
                example = getattr(StandardErrorResponses, attr).examples[0]
                self.assertTrue(example.response_only)
                self.assertTrue(example.name)
                self.assertTrue(example.summary)

    def test_overriding_detail_does_not_mutate_templates(self):
        self.assertNotEqual(
            ERROR_TEMPLATES[status.HTTP_403_FORBIDDEN]["detail"],
            "You can only modify resources that you own.",
        )
        self.assertNotIn("status_code", ERROR_TEMPLATES[status.HTTP_404_NOT_FOUND])


class ResponseSetTests(SimpleTestCase):
    def test_common_error_responses(self):
        self.assertEqual(
            StandardErrorResponses.get_common_error_responses(),
            {
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
                503: StandardErrorResponses.SERVICE_UNAVAILABLE,
            },
        )

    def test_authenticated_endpoint_responses(self):
        self.assertEqual(
            StandardErrorResponses.get_authenticated_endpoint_responses(),
            {
                401: StandardErrorResponses.UNAUTHORIZED,
                403: StandardErrorResponses.PERMISSION_DENIED,
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
                503: StandardErrorResponses.SERVICE_UNAVAILABLE,
            },
        )

    def test_crud_endpoint_responses(self):
        self.assertEqual(
            StandardErrorResponses.get_crud_endpoint_responses(),
            {
                401: StandardErrorResponses.UNAUTHORIZED,
                403: StandardErrorResponses.OWNER_ONLY_ACCESS,
                404: StandardErrorResponses.RESOURCE_NOT_FOUND,
                400: StandardErrorResponses.BAD_REQUEST,
                405: StandardErrorResponses.METHOD_NOT_ALLOWED,
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
                503: StandardErrorResponses.SERVICE_UNAVAILABLE,
            },
        )

    def test_list_endpoint_responses(self):
        self.assertEqual(
            StandardErrorResponses.get_list_endpoint_responses(),
            {
                400: StandardErrorResponses.BAD_REQUEST,
                404: StandardErrorResponses.NO_RESULTS_FOUND,
                429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
                503: StandardErrorResponses.SERVICE_UNAVAILABLE,
            },
        )

    def test_insult_crud_responses(self):
        self.assertEqual(
            get_insult_crud_responses(),
            {
                401: StandardErrorResponses.UNAUTHORIZED,
                403: StandardErrorResponses.OWNER_ONLY_ACCESS,
                404: StandardErrorResponses.INSULT_NOT_FOUND,
                405: StandardErrorResponses.METHOD_NOT_ALLOWED,
                429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
            },
        )

    def test_category_list_responses(self):
        self.assertEqual(
            get_category_list_responses(),
            {
                404: StandardErrorResponses.CATEGORY_NOT_FOUND,
                429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
            },
        )

    def test_public_list_responses(self):
        self.assertEqual(
            get_public_list_responses(),
            {
                404: StandardErrorResponses.NO_RESULTS_FOUND,
                429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
                500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
            },
        )

    def test_helpers_return_fresh_dicts(self):
        first = get_public_list_responses()
        first.pop(404)
        self.assertIn(404, get_public_list_responses())


# ---------------------------------------------------------------------------
# Runtime exception handler
# ---------------------------------------------------------------------------


class FakeView:
    pass


class ExceptionHandlerTestCase(SimpleTestCase):
    def setUp(self):
        patcher = patch(LOGGER_TARGET)
        self.logger = patcher.start()
        self.addCleanup(patcher.stop)

        self.request = MagicMock(method="POST", path="/api/insults/")
        self.context = {"view": FakeView(), "request": self.request}

    def handle(self, exc, context=None):
        return yo_momma_exception_handler(
            exc, self.context if context is None else context
        )

    def assertThemed(self, response, status_code):
        template = ERROR_TEMPLATES[status_code]
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response.data["status_code"], status_code)
        self.assertEqual(response.data["detail"], template["detail"])
        self.assertEqual(response.data["code"], template["code"])


class UnhandledExceptionTests(ExceptionHandlerTestCase):
    def test_non_drf_exception_becomes_themed_500(self):
        response = self.handle(RuntimeError("boom"))
        self.assertThemed(response, 500)
        self.assertEqual(set(response.data), {"detail", "code", "status_code"})

    def test_internal_error_text_is_not_leaked(self):
        response = self.handle(ValueError("secret db password"))
        self.assertNotIn("secret", str(response.data))

    def test_unhandled_exception_is_logged_with_context(self):
        exc = KeyError("missing")
        self.handle(exc)
        self.logger.error.assert_called_once()
        kwargs = self.logger.error.call_args.kwargs
        self.assertEqual(kwargs["view"], "FakeView")
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["path"], "/api/insults/")
        self.assertEqual(kwargs["exc_type"], "KeyError")
        self.assertIs(kwargs["exc"], exc)

    def test_missing_view_and_request_use_placeholders(self):
        response = self.handle(RuntimeError("boom"), context={})
        self.assertEqual(response.status_code, 500)
        kwargs = self.logger.error.call_args.kwargs
        self.assertEqual(kwargs["view"], "unknown")
        self.assertEqual(kwargs["method"], "?")
        self.assertEqual(kwargs["path"], "?")


class ThemedOverrideTests(ExceptionHandlerTestCase):
    def test_not_authenticated_is_themed_401(self):
        response = self.handle(exceptions.NotAuthenticated())
        self.assertThemed(response, 401)
        # DRF's own message differs from the template, so it is preserved
        self.assertEqual(
            response.data["errors"], exceptions.NotAuthenticated.default_detail
        )

    def test_authentication_failed_is_themed_401(self):
        response = self.handle(exceptions.AuthenticationFailed("Invalid token."))
        self.assertThemed(response, 401)
        self.assertEqual(response.data["errors"], "Invalid token.")

    def test_permission_denied_is_themed_403(self):
        response = self.handle(exceptions.PermissionDenied("Not yours."))
        self.assertThemed(response, 403)
        self.assertEqual(response.data["errors"], "Not yours.")

    def test_drf_not_found_is_themed_404(self):
        response = self.handle(exceptions.NotFound())
        self.assertThemed(response, 404)

    def test_django_http404_is_themed_404(self):
        response = self.handle(Http404("No Insult matches the given query."))
        self.assertThemed(response, 404)
        self.assertIn("errors", response.data)

    def test_field_validation_error_is_themed_400_with_errors(self):
        errors = {"content": ["This field is required."]}
        response = self.handle(serializers.ValidationError(errors))
        self.assertThemed(response, 400)
        self.assertEqual(response.data["errors"], errors)

    def test_non_field_string_validation_error_is_themed_400(self):
        response = self.handle(serializers.ValidationError("Bad payload."))
        self.assertThemed(response, 400)
        self.assertEqual(response.data["errors"], ["Bad payload."])

    def test_non_field_list_validation_error_is_themed_400(self):
        response = self.handle(serializers.ValidationError(["one", "two"]))
        self.assertThemed(response, 400)
        self.assertEqual(response.data["errors"], ["one", "two"])

    def test_parse_error_is_themed_400(self):
        response = self.handle(exceptions.ParseError())
        self.assertThemed(response, 400)

    def test_detail_matching_template_is_not_duplicated(self):
        template_detail = ERROR_TEMPLATES[status.HTTP_403_FORBIDDEN]["detail"]
        response = self.handle(exceptions.PermissionDenied(template_detail))
        self.assertThemed(response, 403)
        self.assertNotIn("errors", response.data)

    def test_api_exception_with_500_status_is_themed(self):
        response = self.handle(exceptions.APIException("upstream exploded"))
        self.assertThemed(response, 500)
        self.assertEqual(response.data["errors"], "upstream exploded")


class NonThemedNormalizationTests(ExceptionHandlerTestCase):
    def test_method_not_allowed_keeps_drf_detail(self):
        response = self.handle(exceptions.MethodNotAllowed("DELETE"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            response.data,
            {
                "detail": 'Method "DELETE" not allowed.',
                "code": "method_not_allowed",
                "status_code": 405,
            },
        )

    def test_throttled_keeps_detail_code_and_retry_after_header(self):
        response = self.handle(exceptions.Throttled(wait=30))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["code"], "throttled")
        self.assertEqual(response.data["status_code"], 429)
        self.assertIn("30", response.data["detail"])
        self.assertEqual(response["Retry-After"], "30")

    def test_unsupported_media_type_uses_exception_code(self):
        response = self.handle(exceptions.UnsupportedMediaType("text/xml"))
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["code"], "unsupported_media_type")

    def test_custom_status_with_structured_detail(self):
        class Conflict(exceptions.APIException):
            status_code = status.HTTP_409_CONFLICT
            default_code = "conflict"

        errors = {"reference_id": ["Already exists."]}
        response = self.handle(Conflict(errors))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["detail"],
            "Request could not be processed due to validation errors.",
        )
        self.assertEqual(response.data["errors"], errors)
        self.assertEqual(response.data["status_code"], 409)

    def test_custom_code_argument_is_respected(self):
        class Gone(exceptions.APIException):
            status_code = status.HTTP_410_GONE
            default_detail = "It's gone."
            default_code = "gone"

        response = self.handle(Gone(code="insult_retired"))
        self.assertEqual(response.data["code"], "insult_retired")
        self.assertEqual(response.data["detail"], "It's gone.")

    def test_get_codes_failure_is_suppressed(self):
        class Teapot(exceptions.APIException):
            status_code = 418
            default_detail = "I'm a teapot."

        with patch.object(Teapot, "get_codes", side_effect=RuntimeError):
            response = self.handle(Teapot())
        # get_codes failure is suppressed; default_code is still used
        self.assertEqual(response.data["code"], Teapot.default_code)
        self.assertEqual(response.status_code, 418)


class ExceptionHandlerLoggingTests(ExceptionHandlerTestCase):
    def test_client_errors_log_warning(self):
        self.handle(exceptions.NotFound())
        self.logger.warning.assert_called_once()
        self.logger.error.assert_not_called()
        kwargs = self.logger.warning.call_args.kwargs
        self.assertEqual(kwargs["status_code"], 404)
        self.assertEqual(kwargs["exc_type"], "NotFound")
        self.assertEqual(kwargs["view"], "FakeView")
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["path"], "/api/insults/")

    def test_raw_detail_is_logged_before_theming(self):
        self.handle(exceptions.PermissionDenied("Not yours."))
        kwargs = self.logger.warning.call_args.kwargs
        self.assertEqual(kwargs["raw_detail"], {"detail": "Not yours."})

    def test_server_errors_log_error(self):
        self.handle(exceptions.APIException())
        self.logger.error.assert_called_once()
        self.logger.warning.assert_not_called()
        self.assertEqual(self.logger.error.call_args.kwargs["status_code"], 500)

    def test_service_unavailable_logs_error(self):
        class Unavailable(exceptions.APIException):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        response = self.handle(Unavailable())
        self.assertEqual(response.status_code, 503)
        self.logger.error.assert_called_once()

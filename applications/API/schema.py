"""drf-spectacular extensions for the public insult API.

Extensions register themselves on import, so this module is imported from
``ApiConfig.ready()``.
"""

from drf_spectacular.extensions import (
    OpenApiAuthenticationExtension,
    OpenApiViewExtension,
)
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers


class FlexibleTokenScheme(OpenApiAuthenticationExtension):
    """Document ``FlexibleTokenAuthentication`` as the ``TokenAuth`` scheme.

    ``FlexibleTokenAuthentication`` subclasses DRF's ``TokenAuthentication``,
    which drf-spectacular's built-in ``TokenScheme`` (priority ``-1``,
    ``match_subclasses=True``) would otherwise claim under the name
    ``tokenAuth``. The default priority of ``0`` wins that match, and the name
    lines up with ``SPECTACULAR_SETTINGS["SECURITY"]`` and the
    ``auth=[{"TokenAuth": []}]`` overrides in ``endpoints.py``.
    """

    target_class = "applications.API.authentication.FlexibleTokenAuthentication"
    name = "TokenAuth"
    match_subclasses = True

    def get_security_definition(self, auto_schema):
        """Return an ``apiKey`` header scheme; the keyword prefix is optional.

        ``build_bearer_security_scheme_object`` isn't used because its
        non-Bearer fallback describes the prefix as required, while
        ``FlexibleTokenAuthentication`` also accepts a bare key.
        """
        keyword = self.target.keyword
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": (
                "Token-based authentication. Supply your token like so:\n\n"
                f"`Authorization: {keyword} <your_token>`\n\n"
                f"The `{keyword}` prefix is optional; a bare token is also accepted."
            ),
        }


# ---------------------------------------------------------------------------
# Third-party views
# ---------------------------------------------------------------------------
# OpenApiViewExtension swaps in a subclass during schema generation only, so
# these @extend_schema_view declarations document djoser's and
# drf-spectacular's own views without changing how they run.

_NO_CONTENT = OpenApiResponse(description="Done; no response body.")


def _unauthorized():
    from applications.API.errors import StandardErrorResponses

    return StandardErrorResponses.UNAUTHORIZED


class DjoserUserViewSetScheme(OpenApiViewExtension):
    """Document djoser's ``UserViewSet`` (``/auth/users/...``)."""

    target_class = "djoser.views.UserViewSet"

    def view_replacement(self):
        """Return the viewset with every action documented."""
        tags = ["Users"]
        token = [{"TokenAuth": []}]
        unauthorized = _unauthorized()

        @extend_schema_view(
            list=extend_schema(
                tags=tags,
                auth=token,
                summary="List users",
                description=(
                    "Staff see every user; anyone else gets a list containing only "
                    "themselves."
                ),
                responses={200: self.target_class.serializer_class, 401: unauthorized},
            ),
            create=extend_schema(
                tags=tags,
                auth=[],
                summary="Register an account",
                description=(
                    "Create an account; it can sign in immediately and a welcome "
                    "email is sent. An account is needed to submit insults."
                ),
            ),
            retrieve=extend_schema(
                tags=tags,
                auth=token,
                summary="Retrieve a user",
                description="Only the user themselves or staff; anyone else gets `404`.",
                responses={200: self.target_class.serializer_class, 401: unauthorized},
            ),
            update=extend_schema(
                tags=tags,
                auth=token,
                summary="Replace a user's profile",
                description="Only the user themselves or staff.",
            ),
            partial_update=extend_schema(
                tags=tags,
                auth=token,
                summary="Update part of a user's profile",
                description="Only the user themselves or staff.",
            ),
            destroy=extend_schema(
                tags=tags,
                auth=token,
                summary="Delete a user",
                description=(
                    "Permanently delete the account. Requires the account's "
                    "`current_password`."
                ),
                responses={204: _NO_CONTENT, 401: unauthorized},
            ),
            me=[
                extend_schema(
                    methods=["GET"],
                    tags=tags,
                    auth=token,
                    summary="Get my account",
                    description="The signed-in user's profile.",
                ),
                extend_schema(
                    methods=["PUT"],
                    tags=tags,
                    auth=token,
                    summary="Replace my profile",
                    description="Replace the signed-in user's editable profile fields.",
                ),
                extend_schema(
                    methods=["PATCH"],
                    tags=tags,
                    auth=token,
                    summary="Update part of my profile",
                    description="Update only the fields sent.",
                ),
                extend_schema(
                    methods=["DELETE"],
                    tags=tags,
                    auth=token,
                    summary="Delete my account",
                    description=(
                        "Permanently delete the signed-in user's account. Requires "
                        "`current_password`."
                    ),
                    responses={204: _NO_CONTENT, 401: unauthorized},
                ),
            ],
            activation=extend_schema(
                tags=tags,
                auth=[],
                summary="Activate an account",
                description=(
                    "Activate an account with the `uid` and `token` from an "
                    "activation email. Activation emails are off, so new accounts "
                    "are already active."
                ),
                responses={204: _NO_CONTENT},
            ),
            resend_activation=extend_schema(
                tags=tags,
                auth=[],
                summary="Resend the activation email",
                description=(
                    "Activation emails are off, so this always returns `400`."
                ),
                responses={
                    204: _NO_CONTENT,
                    400: OpenApiResponse(description="Activation emails are disabled."),
                },
            ),
            set_password=extend_schema(
                tags=tags,
                auth=token,
                summary="Change my password",
                description="Requires `current_password` and `new_password`.",
                responses={204: _NO_CONTENT, 401: unauthorized},
            ),
            reset_password=extend_schema(
                tags=tags,
                auth=[],
                summary="Request a password reset email",
                description=(
                    "Emails a reset link to the account with this address. Returns "
                    "`204` whether or not the address exists, so it can't be used "
                    "to discover accounts."
                ),
                responses={204: _NO_CONTENT},
            ),
            reset_password_confirm=extend_schema(
                tags=tags,
                auth=[],
                summary="Set a new password from a reset email",
                description="Uses the `uid` and `token` from the reset email.",
                responses={204: _NO_CONTENT},
            ),
            set_username=extend_schema(
                tags=tags,
                auth=token,
                summary="Change my username",
                description="Requires `current_password` and the new username.",
                responses={204: _NO_CONTENT, 401: unauthorized},
            ),
            reset_username=extend_schema(
                tags=tags,
                auth=[],
                summary="Request a username reset email",
                description="Emails a reset link to the account with this address.",
                responses={204: _NO_CONTENT},
            ),
            reset_username_confirm=extend_schema(
                tags=tags,
                auth=[],
                summary="Set a new username from a reset email",
                description="Uses the `uid` and `token` from the reset email.",
                responses={204: _NO_CONTENT},
            ),
        )
        class DocumentedUserViewSet(self.target_class):
            pass

        return DocumentedUserViewSet


class DjoserTokenCreateViewScheme(OpenApiViewExtension):
    """Document djoser's ``TokenCreateView`` (``/auth/token/login/``)."""

    target_class = "djoser.views.TokenCreateView"

    def view_replacement(self):
        """Return the login view with its request and response documented."""

        @extend_schema_view(
            post=extend_schema(
                tags=["Authentication"],
                auth=[],
                operation_id="auth_token_login",
                summary="Log in and get a token",
                description=(
                    "Exchange a username and password for an API token. Send it as "
                    "`Authorization: Token <token>` on requests that need an account."
                ),
                responses={
                    200: OpenApiResponse(
                        response=inline_serializer(
                            name="AuthToken",
                            fields={"auth_token": serializers.CharField()},
                        ),
                        description="The account's API token.",
                        examples=[
                            OpenApiExample(
                                "Token",
                                value={
                                    "auth_token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
                                },
                                response_only=True,
                            )
                        ],
                    ),
                    400: OpenApiResponse(description="Wrong username or password."),
                },
            )
        )
        class DocumentedTokenCreateView(self.target_class):
            pass

        return DocumentedTokenCreateView


class SpectacularSchemaViewScheme(OpenApiViewExtension):
    """Document ``/api/schema/`` itself."""

    target_class = "drf_spectacular.views.SpectacularAPIView"

    def view_replacement(self):
        """Return the schema view with a summary and tag."""

        @extend_schema_view(
            get=extend_schema(
                tags=["Documentation"],
                auth=[],
                operation_id="openapi_schema",
                summary="Download the OpenAPI schema",
                description=(
                    "This API's OpenAPI 3 description: YAML by default, JSON with "
                    "`?format=json`. Browse it at `/api/swagger/` or `/api/redoc/`."
                ),
            )
        )
        class DocumentedSchemaView(self.target_class):
            pass

        return DocumentedSchemaView

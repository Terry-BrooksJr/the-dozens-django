"""drf-spectacular extensions for the public insult API.

Extensions register themselves on import, so this module is imported from
``ApiConfig.ready()``.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


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

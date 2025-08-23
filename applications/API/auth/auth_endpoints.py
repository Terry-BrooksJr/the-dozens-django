# in e.g. applications/API/views_auth.py
from djoser.views import TokenDestroyView as DjoserTokenDestroyView
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view


@extend_schema_view(
    post=extend_schema(
        operation_id="auth_token_destroy",
        responses=OpenApiResponse(description="Token deleted"),
        auth=[{"TokenAuth": []}],
    )
)
class TokenDestroyView(DjoserTokenDestroyView):
    pass

"""Ad-hoc smoke tester that fires category requests at the public API.

Iterates over ``TEST_CASES`` and issues one authenticated request per case,
used to generate traffic for the Grafana dashboards.
"""

import requests
from test_cases import TEST_CASES


class ApiRequest:
    """Minimal token-authenticated client for the insult-by-category endpoint."""

    def __init__(self, base_url, user_token):
        """Store the API base URL and the DRF token used to authenticate."""
        self._base_url = base_url
        self._token = user_token

    def get_token(self) -> str:
        """Return the ``Authorization`` header value for the stored token."""
        return f"Token {self._token}"

    def get_url(self) -> str:
        """Return the configured API base URL."""
        return self._base_url

    def set_headers(self) -> dict:
        """Build the request headers carrying the auth token."""
        return {"Authorization": self.get_token()}

    def test_endpoint(self, category, nsfw):
        """Request insults for ``category``, filtered by ``nsfw``.

        Args:
            category: Category key or name to request.
            nsfw: NSFW filter value passed as a query parameter.

        Returns:
            requests.Response: The raw HTTP response.
        """
        return requests.get(
            url=f"{self.get_url}/api/{category}",
            params={"nsfw": nsfw},
            headers=self.set_headers(),
            timeout=60,
        )


if __name__ == "__main__":
    tester = ApiRequest(
        "https://api.yo-momma.io/", "b31ec6397d8b3c8f959f5b6150f27c47bc02acec"
    )
    for case in TEST_CASES:
        tester.test_endpoint(category=case["category"], nsfw=case["nsfw"])

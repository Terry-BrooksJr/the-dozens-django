import requests
from test_cases import TEST_CASES


class ApiRequest:
    def __init__(self, base_url, user_token):
        self._base_url = base_url
        self._token = user_token

    def get_token(self) -> str:
        return f"Token {self._token}"

    def get_url(self) -> str:
        return self._base_url

    def set_headers(self) -> dict:
        return {"Authorization": self.get_token()}

    def test_endpoint(self, category, nsfw):
        return requests.get(
            url=f"{self.get_url}/api/{category}",
            params={"nsfw": nsfw},
            headers=self.set_headers(),
        )


if __name__ == "__main__":
    tester = ApiRequest(
        "https://api.yo-momma.io/", "b31ec6397d8b3c8f959f5b6150f27c47bc02acec"
    )
    for case in TEST_CASES:
        tester.test_endpoint(category=case["category"], nsfw=case["nsfw"])

from integrations.onet.auth import OnetApiKeyAuth


def test_onet_auth_applies_x_api_key_header():
    headers = {"Accept": "application/json"}
    auth = OnetApiKeyAuth("test-key")

    auth.apply(headers)

    assert headers["X-API-Key"] == "test-key"
    assert "Authorization" not in headers

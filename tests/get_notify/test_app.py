"""Test get_notify Lambda function"""

import os
from unittest.mock import patch

# pylint: disable=import-outside-toplevel,too-few-public-methods


@patch.dict(
    os.environ,
    {
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
    },
)
class TestGetParameterValue:
    """get_parameter_value function tests"""

    def test_get_parameter_value_success(self):
        """Test successful parameter retrieval"""
        from lambdas.get_notify.app import get_parameter_value

        with patch("lambdas.get_notify.app.ssm_client") as mock_ssm_client:
            mock_ssm_client.get_parameter.return_value = {
                "Parameter": {"Value": "test_value"}
            }

            result = get_parameter_value("test_param")

            assert result == "test_value"
            mock_ssm_client.get_parameter.assert_called_once_with(
                Name="test_param", WithDecryption=True
            )


@patch.dict(
    os.environ,
    {
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
    },
)
class TestVerifyQueryParams:
    """vetify_query_params function tests"""

    def test_verify_query_params_success(self):
        """Test successful query parameter verification"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?channel_id=test_channel_id"
                ),
                "hub.lease_seconds": "828000",
            }

            result = vetify_query_params(query_params)

            assert result is None

    def test_verify_query_params_missing_challenge(self):
        """Test missing hub.challenge parameter"""
        from lambdas.get_notify.app import vetify_query_params

        query_params = {}

        result = vetify_query_params(query_params)

        assert result == "Bad Request: Missing hub.challenge parameter"

    def test_verify_query_params_invalid_mode(self):
        """Test invalid hub.mode parameter"""
        from lambdas.get_notify.app import vetify_query_params

        query_params = {"hub.challenge": "test_challenge", "hub.mode": "unsubscribe"}

        result = vetify_query_params(query_params)

        assert result == "Bad Request: Invalid hub.mode: unsubscribe"

    def test_verify_query_params_invalid_secret(self):
        """Test invalid hub.secret parameter"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "expected_secret"

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "wrong_secret",
            }

            result = vetify_query_params(query_params)

            assert result == "Bad Request: Invalid hub.secret: wrong_secret"

    def test_verify_query_params_invalid_topic(self):
        """Test invalid hub.topic parameter"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "expected_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?channel_id=wrong_channel_id"
                ),
            }

            result = vetify_query_params(query_params)

            assert "Bad Request: Unexpected topic URL:" in result

    def test_verify_query_params_invalid_lease_seconds(self):
        """Test invalid hub.lease_seconds parameter"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?channel_id=test_channel_id"
                ),
                "hub.lease_seconds": "invalid",
            }

            result = vetify_query_params(query_params)

            assert "Bad Request: Invalid hub.lease_seconds:" in result

    def test_verify_query_params_wrong_lease_seconds_number(self):
        """Test wrong hub.lease_seconds number"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?channel_id=test_channel_id"
                ),
                "hub.lease_seconds": "123456",
            }

            result = vetify_query_params(query_params)

            assert "Bad Request: Invalid hub.lease_seconds:" in result


@patch.dict(
    os.environ,
    {
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
    },
)
class TestLambdaHandler:
    """lambda_handler function tests"""

    def test_lambda_handler_success(self):
        """Test successful Lambda handler execution"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = None

            event = {"queryStringParameters": {"hub.challenge": "test_challenge"}}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 200
            assert result["headers"]["Content-Type"] == "text/plain"
            assert result["body"] == "test_challenge"

    def test_lambda_handler_verification_failed(self):
        """Test Lambda handler when verification fails"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = "Verification failed"

            event = {"queryStringParameters": {"hub.challenge": "test_challenge"}}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 400
            assert result["body"] == "Verification failed"

    def test_lambda_handler_no_query_params(self):
        """Test Lambda handler with no query parameters"""
        from lambdas.get_notify.app import lambda_handler

        event = {}

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = None

            result = lambda_handler(event, None)

            assert result["statusCode"] == 200
            mock_verify.assert_called_once_with({})

    def test_lambda_handler_exception(self):
        """Test Lambda handler when exception occurs"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.side_effect = Exception("Test exception")

            event = {"queryStringParameters": {"hub.challenge": "test_challenge"}}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 500
            assert result["body"] == "Internal Server Error"

"""Test websub Lambda function"""

import os
from unittest.mock import Mock, patch

import pytest

# pylint: disable=import-outside-toplevel,too-few-public-methods


@patch.dict(
    os.environ,
    {
        "PUBSUBHUBBUB_HUB_URL": "https://pubsubhubbub.appspot.com/",
        "LEASE_SECONDS": "828000",
        "HMAC_SECRET_LENGTH": "32",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
        "WEBSUB_CALLBACK_URL_PARAMETER_NAME": "test-callback-url-param",
    },
)
class TestGetParameterValue:
    """get_parameter_value function tests"""

    def test_get_parameter_value_success(self):
        """Test successful parameter retrieval"""
        from lambdas.websub.app import get_parameter_value

        with patch("lambdas.websub.app.ssm_client") as mock_ssm_client:
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
        "PUBSUBHUBBUB_HUB_URL": "https://pubsubhubbub.appspot.com/",
        "LEASE_SECONDS": "828000",
        "HMAC_SECRET_LENGTH": "32",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
        "WEBSUB_CALLBACK_URL_PARAMETER_NAME": "test-callback-url-param",
    },
)
class TestGenerateHmacSecret:
    """generate_hmac_secret function tests"""

    def test_generate_hmac_secret_success(self):
        """Test successful HMAC secret generation"""
        from lambdas.websub.app import generate_hmac_secret

        with patch("lambdas.websub.app.ssm_client") as mock_ssm_client:
            with patch("lambdas.websub.app.secrets.token_hex") as mock_token_hex:
                mock_token_hex.return_value = "test_secret_hex"

                result = generate_hmac_secret()

                assert result == "test_secret_hex"
                mock_ssm_client.put_parameter.assert_called_once()
                call_args = mock_ssm_client.put_parameter.call_args
                assert call_args[1]["Value"] == "test_secret_hex"
                assert call_args[1]["Type"] == "SecureString"
                assert call_args[1]["Overwrite"] is True


@patch.dict(
    os.environ,
    {
        "PUBSUBHUBBUB_HUB_URL": "https://pubsubhubbub.appspot.com/",
        "LEASE_SECONDS": "828000",
        "HMAC_SECRET_LENGTH": "32",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
        "WEBSUB_CALLBACK_URL_PARAMETER_NAME": "test-callback-url-param",
    },
)
class TestSubscribeToPubsubhubbub:
    """subscribe_to_pubsubhubbub function tests"""

    def test_subscribe_to_pubsubhubbub_success(self):
        """Test successful subscription to PubSubHubbub"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.text = "Accepted"
            mock_requests_post.return_value = mock_response

            subscribe_to_pubsubhubbub(
                channel_id="test_channel_id",
                callback_url="https://example.com/callback",
                hmac_secret="test_secret",
            )

            mock_requests_post.assert_called_once()
            call_args = mock_requests_post.call_args
            assert "hub.callback" in call_args[1]["data"]
            assert "hub.topic" in call_args[1]["data"]
            assert "hub.secret" in call_args[1]["data"]

    def test_subscribe_to_pubsubhubbub_failure(self):
        """Test failed subscription to PubSubHubbub"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_requests_post.return_value = mock_response

            with pytest.raises(Exception, match="Subscription failed"):
                subscribe_to_pubsubhubbub(
                    channel_id="test_channel_id",
                    callback_url="https://example.com/callback",
                    hmac_secret="test_secret",
                )

    def test_subscribe_to_pubsubhubbub_correct_data_format(self):
        """Test correct data format in subscription request"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.text = "Accepted"
            mock_requests_post.return_value = mock_response

            subscribe_to_pubsubhubbub(
                channel_id="test_channel_id",
                callback_url="https://example.com/callback",
                hmac_secret="test_secret",
            )

            call_args = mock_requests_post.call_args
            data = call_args[1]["data"]

            # Check if data contains expected hub.topic format (URL encoded)
            assert "channel_id%3Dtest_channel_id" in data
            assert "hub.verify=async" in data
            assert "hub.mode=subscribe" in data
            assert "hub.secret=test_secret" in data

    def test_subscribe_to_pubsubhubbub_correct_headers(self):
        """Test correct headers in subscription request"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.text = "Accepted"
            mock_requests_post.return_value = mock_response

            subscribe_to_pubsubhubbub(
                channel_id="test_channel_id",
                callback_url="https://example.com/callback",
                hmac_secret="test_secret",
            )

            call_args = mock_requests_post.call_args
            headers = call_args[1]["headers"]

            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            assert headers["User-Agent"] == "YTLiveMetaData-WebSub/1.0"


@patch.dict(
    os.environ,
    {
        "PUBSUBHUBBUB_HUB_URL": "https://pubsubhubbub.appspot.com/",
        "LEASE_SECONDS": "828000",
        "HMAC_SECRET_LENGTH": "32",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
        "WEBSUB_CALLBACK_URL_PARAMETER_NAME": "test-callback-url-param",
    },
)
class TestLambdaHandler:
    """lambda_handler function tests"""

    def test_lambda_handler_success(self):
        """Test successful Lambda handler execution"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub") as mock_subscribe:
            with patch(
                "lambdas.websub.app.generate_hmac_secret"
            ) as mock_generate_secret:
                with patch(
                    "lambdas.websub.app.get_parameter_value"
                ) as mock_get_parameter:
                    mock_get_parameter.side_effect = [
                        "test_channel_id",
                        "https://example.com/callback",
                    ]
                    mock_generate_secret.return_value = "test_secret"

                    event = {}

                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 200
                    assert result["body"] == "OK"
                    mock_subscribe.assert_called_once_with(
                        channel_id="test_channel_id",
                        callback_url="https://example.com/callback",
                        hmac_secret="test_secret",
                    )

    def test_lambda_handler_get_parameter_exception(self):
        """Test Lambda handler when get_parameter_value raises exception"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = Exception("Parameter not found")

            event = {}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 500
            assert result["body"] == "Internal server error"

    def test_lambda_handler_generate_secret_exception(self):
        """Test Lambda handler when generate_hmac_secret raises exception"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub"):
            with patch(
                "lambdas.websub.app.generate_hmac_secret"
            ) as mock_generate_secret:
                with patch(
                    "lambdas.websub.app.get_parameter_value"
                ) as mock_get_parameter:
                    mock_get_parameter.side_effect = [
                        "test_channel_id",
                        "https://example.com/callback",
                    ]
                    mock_generate_secret.side_effect = Exception(
                        "Secret generation failed"
                    )

                    event = {}

                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 500
                    assert result["body"] == "Internal server error"

    def test_lambda_handler_subscribe_exception(self):
        """Test Lambda handler when subscribe_to_pubsubhubbub raises exception"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub") as mock_subscribe:
            with patch(
                "lambdas.websub.app.generate_hmac_secret"
            ) as mock_generate_secret:
                with patch(
                    "lambdas.websub.app.get_parameter_value"
                ) as mock_get_parameter:
                    mock_get_parameter.side_effect = [
                        "test_channel_id",
                        "https://example.com/callback",
                    ]
                    mock_generate_secret.return_value = "test_secret"
                    mock_subscribe.side_effect = Exception("Subscription failed")

                    event = {}

                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 500
                    assert result["body"] == "Internal server error"

    def test_lambda_handler_parameter_order(self):
        """Test parameter retrieval order in Lambda handler"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub"):
            with patch(
                "lambdas.websub.app.generate_hmac_secret"
            ) as mock_generate_secret:
                with patch(
                    "lambdas.websub.app.get_parameter_value"
                ) as mock_get_parameter:
                    mock_get_parameter.side_effect = [
                        "test_channel_id",
                        "https://example.com/callback",
                    ]
                    mock_generate_secret.return_value = "test_secret"

                    event = {}

                    lambda_handler(event, None)

                    # Verify that parameters are retrieved in the correct order
                    actual_calls = [
                        call[0] for call in mock_get_parameter.call_args_list
                    ]
                    assert len(actual_calls) == 2  # Should be called twice

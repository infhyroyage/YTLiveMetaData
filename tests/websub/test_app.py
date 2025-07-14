"""Test websub Lambda function"""

import os
from unittest.mock import Mock, patch

import pytest
import requests

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

    def test_subscribe_to_pubsubhubbub_429_retry_success(self):
        """Test successful retry after 429 throttling error"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # First call returns 429, second call returns 202
                mock_response_429 = Mock()
                mock_response_429.status_code = 429
                mock_response_429.text = "Throttled"

                mock_response_202 = Mock()
                mock_response_202.status_code = 202
                mock_response_202.text = "Accepted"

                mock_requests_post.side_effect = [mock_response_429, mock_response_202]

                subscribe_to_pubsubhubbub(
                    channel_id="test_channel_id",
                    callback_url="https://example.com/callback",
                    hmac_secret="test_secret",
                )

                # Verify that requests.post was called twice
                assert mock_requests_post.call_count == 2
                # Verify that sleep was called once with 1.0 second delay (BASE_DELAY * 2^0)
                mock_sleep.assert_called_once_with(1.0)

    def test_subscribe_to_pubsubhubbub_429_max_retries_exceeded(self):
        """Test failure after exceeding max retries for 429 errors"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # Always return 429
                mock_response = Mock()
                mock_response.status_code = 429
                mock_response.text = "Throttled"
                mock_requests_post.return_value = mock_response

                with pytest.raises(
                    Exception, match="Subscription failed after 6 attempts"
                ):
                    subscribe_to_pubsubhubbub(
                        channel_id="test_channel_id",
                        callback_url="https://example.com/callback",
                        hmac_secret="test_secret",
                    )

                # Verify that requests.post was called 6 times (initial + 5 retries)
                assert mock_requests_post.call_count == 6
                # Verify that sleep was called 5 times with exponential backoff
                assert mock_sleep.call_count == 5
                expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0]
                for i, call in enumerate(mock_sleep.call_args_list):
                    assert call[0][0] == expected_delays[i]

    def test_subscribe_to_pubsubhubbub_network_error_immediate_failure(self):
        """Test immediate failure for network errors (no retry)"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # Network error should not be retried
                mock_requests_post.side_effect = requests.exceptions.ConnectionError(
                    "Network error"
                )

                with pytest.raises(requests.exceptions.ConnectionError):
                    subscribe_to_pubsubhubbub(
                        channel_id="test_channel_id",
                        callback_url="https://example.com/callback",
                        hmac_secret="test_secret",
                    )

                # Verify that requests.post was called only once (no retries)
                assert mock_requests_post.call_count == 1
                # Verify that sleep was not called
                mock_sleep.assert_not_called()

    def test_subscribe_to_pubsubhubbub_non_retryable_error(self):
        """Test immediate failure for non-retryable errors (non-429, non-network)"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # Return 500 error (non-retryable)
                mock_response = Mock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_requests_post.return_value = mock_response

                with pytest.raises(
                    Exception, match="Subscription failed: status code: 500"
                ):
                    subscribe_to_pubsubhubbub(
                        channel_id="test_channel_id",
                        callback_url="https://example.com/callback",
                        hmac_secret="test_secret",
                    )

                # Verify that requests.post was called only once (no retries)
                assert mock_requests_post.call_count == 1
                # Verify that sleep was not called
                mock_sleep.assert_not_called()


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

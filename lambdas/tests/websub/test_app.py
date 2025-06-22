"""Test websub Lambda function"""

import json
from unittest.mock import Mock, patch

import pytest

from lambdas.websub.app import (
    generate_hmac_secret,
    get_parameter_value,
    lambda_handler,
    subscribe_to_pubsubhubbub,
)


class TestGetParameterValue:
    """get_parameter_value function tests"""

    @patch("lambdas.websub.app.ssm_client")
    def test_get_parameter_value_success(self, mock_ssm_client):
        """Test successful parameter retrieval"""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "test_value"}
        }
        
        result = get_parameter_value("test_param")
        
        assert result == "test_value"
        mock_ssm_client.get_parameter.assert_called_once_with(
            Name="test_param", WithDecryption=True
        )


class TestGenerateHmacSecret:
    """generate_hmac_secret function tests"""

    @patch("lambdas.websub.app.ssm_client")
    @patch("lambdas.websub.app.secrets.token_hex")
    def test_generate_hmac_secret_success(self, mock_token_hex, mock_ssm_client):
        """Test successful HMAC secret generation"""
        mock_token_hex.return_value = "test_secret_hex"
        
        result = generate_hmac_secret()
        
        assert result == "test_secret_hex"
        mock_ssm_client.put_parameter.assert_called_once()
        call_args = mock_ssm_client.put_parameter.call_args
        assert call_args[1]["Value"] == "test_secret_hex"
        assert call_args[1]["Type"] == "SecureString"
        assert call_args[1]["Overwrite"] is True


class TestSubscribeToPubsubhubbub:
    """subscribe_to_pubsubhubbub function tests"""

    @patch("lambdas.websub.app.requests.post")
    def test_subscribe_to_pubsubhubbub_success(self, mock_requests_post):
        """Test successful subscription to PubSubHubbub"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = "Accepted"
        mock_requests_post.return_value = mock_response
        
        subscribe_to_pubsubhubbub(
            channel_id="test_channel_id",
            callback_url="https://example.com/callback",
            hmac_secret="test_secret"
        )
        
        mock_requests_post.assert_called_once()
        call_args = mock_requests_post.call_args
        assert "hub.callback" in call_args[1]["data"]
        assert "hub.topic" in call_args[1]["data"]
        assert "hub.secret" in call_args[1]["data"]

    @patch("lambdas.websub.app.requests.post")
    def test_subscribe_to_pubsubhubbub_failure(self, mock_requests_post):
        """Test failed subscription to PubSubHubbub"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_requests_post.return_value = mock_response
        
        with pytest.raises(Exception, match="Subscription failed"):
            subscribe_to_pubsubhubbub(
                channel_id="test_channel_id",
                callback_url="https://example.com/callback",
                hmac_secret="test_secret"
            )

    @patch("lambdas.websub.app.requests.post")
    def test_subscribe_to_pubsubhubbub_correct_data_format(self, mock_requests_post):
        """Test correct data format in subscription request"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = "Accepted"
        mock_requests_post.return_value = mock_response
        
        subscribe_to_pubsubhubbub(
            channel_id="test_channel_id",
            callback_url="https://example.com/callback",
            hmac_secret="test_secret"
        )
        
        call_args = mock_requests_post.call_args
        data = call_args[1]["data"]
        
        # Check if data contains expected hub.topic format (URL encoded)
        assert "channel_id%3Dtest_channel_id" in data
        assert "hub.verify=async" in data
        assert "hub.mode=subscribe" in data
        assert "hub.secret=test_secret" in data

    @patch("lambdas.websub.app.requests.post")
    def test_subscribe_to_pubsubhubbub_correct_headers(self, mock_requests_post):
        """Test correct headers in subscription request"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = "Accepted"
        mock_requests_post.return_value = mock_response
        
        subscribe_to_pubsubhubbub(
            channel_id="test_channel_id",
            callback_url="https://example.com/callback",
            hmac_secret="test_secret"
        )
        
        call_args = mock_requests_post.call_args
        headers = call_args[1]["headers"]
        
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert headers["User-Agent"] == "YTLiveMetaData-WebSub/1.0"


class TestLambdaHandler:
    """lambda_handler function tests"""

    @patch("lambdas.websub.app.subscribe_to_pubsubhubbub")
    @patch("lambdas.websub.app.generate_hmac_secret")
    @patch("lambdas.websub.app.get_parameter_value")
    def test_lambda_handler_success(self, mock_get_parameter, mock_generate_secret, mock_subscribe):
        """Test successful Lambda handler execution"""
        mock_get_parameter.side_effect = ["test_channel_id", "https://example.com/callback"]
        mock_generate_secret.return_value = "test_secret"
        
        event = {}
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 200
        assert result["body"] == "OK"
        mock_subscribe.assert_called_once_with(
            channel_id="test_channel_id",
            callback_url="https://example.com/callback",
            hmac_secret="test_secret"
        )

    @patch("lambdas.websub.app.get_parameter_value")
    def test_lambda_handler_get_parameter_exception(self, mock_get_parameter):
        """Test Lambda handler when get_parameter_value raises exception"""
        mock_get_parameter.side_effect = Exception("Parameter not found")
        
        event = {}
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 500
        assert result["body"] == "Internal server error"

    @patch("lambdas.websub.app.subscribe_to_pubsubhubbub")
    @patch("lambdas.websub.app.generate_hmac_secret")
    @patch("lambdas.websub.app.get_parameter_value")
    def test_lambda_handler_generate_secret_exception(self, mock_get_parameter, mock_generate_secret, mock_subscribe):
        """Test Lambda handler when generate_hmac_secret raises exception"""
        mock_get_parameter.side_effect = ["test_channel_id", "https://example.com/callback"]
        mock_generate_secret.side_effect = Exception("Secret generation failed")
        
        event = {}
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 500
        assert result["body"] == "Internal server error"

    @patch("lambdas.websub.app.subscribe_to_pubsubhubbub")
    @patch("lambdas.websub.app.generate_hmac_secret")
    @patch("lambdas.websub.app.get_parameter_value")
    def test_lambda_handler_subscribe_exception(self, mock_get_parameter, mock_generate_secret, mock_subscribe):
        """Test Lambda handler when subscribe_to_pubsubhubbub raises exception"""
        mock_get_parameter.side_effect = ["test_channel_id", "https://example.com/callback"]
        mock_generate_secret.return_value = "test_secret"
        mock_subscribe.side_effect = Exception("Subscription failed")
        
        event = {}
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 500
        assert result["body"] == "Internal server error"

    @patch("lambdas.websub.app.subscribe_to_pubsubhubbub")
    @patch("lambdas.websub.app.generate_hmac_secret")
    @patch("lambdas.websub.app.get_parameter_value")
    def test_lambda_handler_parameter_order(self, mock_get_parameter, mock_generate_secret, mock_subscribe):
        """Test parameter retrieval order in Lambda handler"""
        mock_get_parameter.side_effect = ["test_channel_id", "https://example.com/callback"]
        mock_generate_secret.return_value = "test_secret"
        
        event = {}
        
        lambda_handler(event, None)
        
        # Verify that parameters are retrieved in the correct order
        expected_calls = [
            ("YOUTUBE_CHANNEL_ID_PARAMETER_NAME",),
            ("WEBSUB_CALLBACK_URL_PARAMETER_NAME",)
        ]
        actual_calls = [call[0] for call in mock_get_parameter.call_args_list]
        assert len(actual_calls) == 2  # Should be called twice
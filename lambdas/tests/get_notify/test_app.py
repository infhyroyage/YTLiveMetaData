"""Test get_notify Lambda function"""

import json
from unittest.mock import Mock, patch

import pytest

from lambdas.get_notify.app import get_parameter_value, lambda_handler, vetify_query_params


class TestGetParameterValue:
    """get_parameter_value function tests"""

    @patch("lambdas.get_notify.app.ssm_client")
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


class TestVerifyQueryParams:
    """vetify_query_params function tests"""

    @patch("lambdas.get_notify.app.get_parameter_value")
    def test_verify_query_params_success(self, mock_get_parameter):
        """Test successful query parameter verification"""
        mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]
        
        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "subscribe",
            "hub.secret": "test_secret",
            "hub.topic": "https://www.youtube.com/xml/feeds/videos.xml?channel_id=test_channel_id",
            "hub.lease_seconds": "828000"
        }
        
        result = vetify_query_params(query_params)
        
        assert result is None

    def test_verify_query_params_missing_challenge(self):
        """Test missing hub.challenge parameter"""
        query_params = {}
        
        result = vetify_query_params(query_params)
        
        assert result == "Bad Request: Missing hub.challenge parameter"

    def test_verify_query_params_invalid_mode(self):
        """Test invalid hub.mode parameter"""
        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "unsubscribe"
        }
        
        result = vetify_query_params(query_params)
        
        assert result == "Bad Request: Invalid hub.mode: unsubscribe"

    @patch("lambdas.get_notify.app.get_parameter_value")
    def test_verify_query_params_invalid_secret(self, mock_get_parameter):
        """Test invalid hub.secret parameter"""
        mock_get_parameter.return_value = "expected_secret"
        
        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "subscribe",
            "hub.secret": "wrong_secret"
        }
        
        result = vetify_query_params(query_params)
        
        assert result == "Bad Request: Invalid hub.secret: wrong_secret"

    @patch("lambdas.get_notify.app.get_parameter_value")
    def test_verify_query_params_invalid_topic(self, mock_get_parameter):
        """Test invalid hub.topic parameter"""
        mock_get_parameter.side_effect = ["test_secret", "expected_channel_id"]
        
        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "subscribe",
            "hub.secret": "test_secret",
            "hub.topic": "https://www.youtube.com/xml/feeds/videos.xml?channel_id=wrong_channel_id"
        }
        
        result = vetify_query_params(query_params)
        
        assert "Bad Request: Unexpected topic URL:" in result

    @patch("lambdas.get_notify.app.get_parameter_value")
    def test_verify_query_params_invalid_lease_seconds(self, mock_get_parameter):
        """Test invalid hub.lease_seconds parameter"""
        mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]
        
        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "subscribe",
            "hub.secret": "test_secret",
            "hub.topic": "https://www.youtube.com/xml/feeds/videos.xml?channel_id=test_channel_id",
            "hub.lease_seconds": "invalid"
        }
        
        result = vetify_query_params(query_params)
        
        assert "Bad Request: Invalid hub.lease_seconds:" in result

    @patch("lambdas.get_notify.app.get_parameter_value")
    def test_verify_query_params_wrong_lease_seconds_number(self, mock_get_parameter):
        """Test wrong hub.lease_seconds number"""
        mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]
        
        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "subscribe",
            "hub.secret": "test_secret",
            "hub.topic": "https://www.youtube.com/xml/feeds/videos.xml?channel_id=test_channel_id",
            "hub.lease_seconds": "123456"
        }
        
        result = vetify_query_params(query_params)
        
        assert "Bad Request: Invalid hub.lease_seconds:" in result


class TestLambdaHandler:
    """lambda_handler function tests"""

    @patch("lambdas.get_notify.app.vetify_query_params")
    def test_lambda_handler_success(self, mock_verify):
        """Test successful Lambda handler execution"""
        mock_verify.return_value = None
        
        event = {
            "queryStringParameters": {
                "hub.challenge": "test_challenge"
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 200
        assert result["headers"]["Content-Type"] == "text/plain"
        assert result["body"] == "test_challenge"

    @patch("lambdas.get_notify.app.vetify_query_params")
    def test_lambda_handler_verification_failed(self, mock_verify):
        """Test Lambda handler when verification fails"""
        mock_verify.return_value = "Verification failed"
        
        event = {
            "queryStringParameters": {
                "hub.challenge": "test_challenge"
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 400
        assert result["body"] == "Verification failed"

    def test_lambda_handler_no_query_params(self):
        """Test Lambda handler with no query parameters"""
        event = {}
        
        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = None
            
            result = lambda_handler(event, None)
            
            assert result["statusCode"] == 200
            mock_verify.assert_called_once_with({})

    @patch("lambdas.get_notify.app.vetify_query_params")
    def test_lambda_handler_exception(self, mock_verify):
        """Test Lambda handler when exception occurs"""
        mock_verify.side_effect = Exception("Test exception")
        
        event = {
            "queryStringParameters": {
                "hub.challenge": "test_challenge"
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 500
        assert result["body"] == "Internal Server Error"
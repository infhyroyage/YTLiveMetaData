"""Test post_notify Lambda function"""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest

from lambdas.post_notify.app import (
    check_if_live_streaming,
    check_if_notified,
    get_parameter_value,
    lambda_handler,
    parse_websub_xml,
    record_notified,
    send_sms_notification,
    verify_hmac_signature,
)


class TestGetParameterValue:
    """get_parameter_value function tests"""

    @patch("lambdas.post_notify.app.ssm_client")
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


class TestVerifyHmacSignature:
    """verify_hmac_signature function tests"""

    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_verify_hmac_signature_success(self, mock_get_parameter):
        """Test successful HMAC signature verification"""
        mock_get_parameter.return_value = "secret_key"
        
        # Calculate expected signature
        import hmac
        import hashlib
        body = "test_body"
        expected_signature = hmac.new(
            "secret_key".encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha1
        ).hexdigest()
        
        event = {
            "headers": {
                "X-Hub-Signature": f"sha1={expected_signature}"
            },
            "body": body
        }
        
        result = verify_hmac_signature(event)
        
        assert result is None

    def test_verify_hmac_signature_missing_header(self):
        """Test missing X-Hub-Signature header"""
        event = {
            "headers": {},
            "body": "test_body"
        }
        
        result = verify_hmac_signature(event)
        
        assert result == "Missing X-Hub-Signature header"

    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_verify_hmac_signature_unsupported_method(self, mock_get_parameter):
        """Test unsupported signature method"""
        mock_get_parameter.return_value = "secret_key"
        
        event = {
            "headers": {
                "X-Hub-Signature": "md5=invalidhash"
            },
            "body": "test_body"
        }
        
        result = verify_hmac_signature(event)
        
        assert result == "Unsupported signature method: md5"

    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_verify_hmac_signature_verification_failed(self, mock_get_parameter):
        """Test HMAC signature verification failure"""
        mock_get_parameter.return_value = "secret_key"
        
        event = {
            "headers": {
                "X-Hub-Signature": "sha1=invalidhash"
            },
            "body": "test_body"
        }
        
        result = verify_hmac_signature(event)
        
        assert result == "HMAC signature verification failed"

    def test_verify_hmac_signature_case_insensitive_headers(self):
        """Test case insensitive header handling"""
        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "secret_key"
            
            import hmac
            import hashlib
            body = "test_body"
            expected_signature = hmac.new(
                "secret_key".encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha1
            ).hexdigest()
            
            event = {
                "headers": {
                    "x-hub-signature": f"sha1={expected_signature}"  # lowercase
                },
                "body": body
            }
            
            result = verify_hmac_signature(event)
            
            assert result is None


class TestParseWebsubXml:
    """parse_websub_xml function tests"""

    def test_parse_websub_xml_success(self):
        """Test successful XML parsing"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <yt:videoId>test_video_id</yt:videoId>
                <title>Test Video Title</title>
            </entry>
        </feed>'''
        
        result = parse_websub_xml(xml_content)
        
        assert result["video_id"] == "test_video_id"
        assert result["title"] == "Test Video Title"
        assert result["url"] == "https://www.youtube.com/watch?v=test_video_id"

    def test_parse_websub_xml_no_entry(self):
        """Test XML parsing with no entry"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
        </feed>'''
        
        with pytest.raises(ValueError, match="No entry found in XML"):
            parse_websub_xml(xml_content)

    def test_parse_websub_xml_no_video_id(self):
        """Test XML parsing with no video ID"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <title>Test Video Title</title>
            </entry>
        </feed>'''
        
        with pytest.raises(ValueError, match="No videoId found in XML"):
            parse_websub_xml(xml_content)

    def test_parse_websub_xml_no_title(self):
        """Test XML parsing with no title"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <yt:videoId>test_video_id</yt:videoId>
            </entry>
        </feed>'''
        
        with pytest.raises(ValueError, match="No title found in XML"):
            parse_websub_xml(xml_content)


class TestCheckIfLiveStreaming:
    """check_if_live_streaming function tests"""

    @patch("lambdas.post_notify.app.requests.get")
    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_check_if_live_streaming_live(self, mock_get_parameter, mock_requests):
        """Test live streaming check when video is live"""
        mock_get_parameter.return_value = "test_api_key"
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{
                "snippet": {
                    "liveBroadcastContent": "live",
                    "thumbnails": {
                        "high": {"url": "https://example.com/high.jpg"},
                        "medium": {"url": "https://example.com/medium.jpg"},
                        "default": {"url": "https://example.com/default.jpg"}
                    }
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        result = check_if_live_streaming("test_video_id")
        
        assert result == "https://example.com/high.jpg"

    @patch("lambdas.post_notify.app.requests.get")
    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_check_if_live_streaming_not_live(self, mock_get_parameter, mock_requests):
        """Test live streaming check when video is not live"""
        mock_get_parameter.return_value = "test_api_key"
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{
                "snippet": {
                    "liveBroadcastContent": "none"
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        result = check_if_live_streaming("test_video_id")
        
        assert result is None

    @patch("lambdas.post_notify.app.requests.get")
    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_check_if_live_streaming_no_thumbnails(self, mock_get_parameter, mock_requests):
        """Test live streaming check when no thumbnails are available"""
        mock_get_parameter.return_value = "test_api_key"
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{
                "snippet": {
                    "liveBroadcastContent": "live"
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        result = check_if_live_streaming("test_video_id")
        
        assert result == ""

    @patch("lambdas.post_notify.app.requests.get")
    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_check_if_live_streaming_no_items(self, mock_get_parameter, mock_requests):
        """Test live streaming check when no items are returned"""
        mock_get_parameter.return_value = "test_api_key"
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        with pytest.raises(ValueError, match="Video not found"):
            check_if_live_streaming("test_video_id")


class TestCheckIfNotified:
    """check_if_notified function tests"""

    @patch("lambdas.post_notify.app.dynamodb_client")
    def test_check_if_notified_true(self, mock_dynamodb_client):
        """Test check if notified returns True"""
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "is_notified": {"BOOL": True}
            }
        }
        
        result = check_if_notified("test_video_id")
        
        assert result is True

    @patch("lambdas.post_notify.app.dynamodb_client")
    def test_check_if_notified_false(self, mock_dynamodb_client):
        """Test check if notified returns False"""
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "is_notified": {"BOOL": False}
            }
        }
        
        result = check_if_notified("test_video_id")
        
        assert result is False

    @patch("lambdas.post_notify.app.dynamodb_client")
    def test_check_if_notified_no_item(self, mock_dynamodb_client):
        """Test check if notified when no item exists"""
        mock_dynamodb_client.get_item.return_value = {}
        
        result = check_if_notified("test_video_id")
        
        assert result is False

    @patch("lambdas.post_notify.app.dynamodb_client")
    def test_check_if_notified_none_response(self, mock_dynamodb_client):
        """Test check if notified when response is None"""
        mock_dynamodb_client.get_item.return_value = None
        
        result = check_if_notified("test_video_id")
        
        assert result is False


class TestRecordNotified:
    """record_notified function tests"""

    @patch("lambdas.post_notify.app.dynamodb_client")
    @patch("time.time")
    def test_record_notified_success(self, mock_time, mock_dynamodb_client):
        """Test successful record notified"""
        mock_time.return_value = 1234567890
        
        record_notified("test_video_id", "Test Title", "test_url", "test_thumbnail")
        
        mock_dynamodb_client.update_item.assert_called_once()


class TestSendSmsNotification:
    """send_sms_notification function tests"""

    @patch("lambdas.post_notify.app.sns_client")
    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_send_sms_notification_with_thumbnail(self, mock_get_parameter, mock_sns_client):
        """Test SMS notification with thumbnail"""
        mock_get_parameter.return_value = "+1234567890"
        
        send_sms_notification("Test Title", "test_url", "test_thumbnail")
        
        assert mock_sns_client.publish.call_count == 3

    @patch("lambdas.post_notify.app.sns_client")
    @patch("lambdas.post_notify.app.get_parameter_value")
    def test_send_sms_notification_without_thumbnail(self, mock_get_parameter, mock_sns_client):
        """Test SMS notification without thumbnail"""
        mock_get_parameter.return_value = "+1234567890"
        
        send_sms_notification("Test Title", "test_url", "")
        
        assert mock_sns_client.publish.call_count == 2


class TestLambdaHandler:
    """lambda_handler function tests"""

    @patch("lambdas.post_notify.app.record_notified")
    @patch("lambdas.post_notify.app.send_sms_notification")
    @patch("lambdas.post_notify.app.check_if_notified")
    @patch("lambdas.post_notify.app.check_if_live_streaming")
    @patch("lambdas.post_notify.app.parse_websub_xml")
    @patch("lambdas.post_notify.app.verify_hmac_signature")
    def test_lambda_handler_success(self, mock_verify, mock_parse, mock_check_live, 
                                    mock_check_notified, mock_send_sms, mock_record):
        """Test successful Lambda handler execution"""
        mock_verify.return_value = None
        mock_parse.return_value = {
            "video_id": "test_video_id",
            "title": "Test Title",
            "url": "test_url"
        }
        mock_check_live.return_value = "test_thumbnail"
        mock_check_notified.return_value = False
        
        event = {
            "body": "test_xml_content"
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 200
        assert result["body"] == "OK"

    @patch("lambdas.post_notify.app.verify_hmac_signature")
    def test_lambda_handler_hmac_verification_failed(self, mock_verify):
        """Test Lambda handler when HMAC verification fails"""
        mock_verify.return_value = "HMAC verification failed"
        
        event = {
            "body": "test_xml_content"
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 400
        assert result["body"] == "HMAC verification failed"

    @patch("lambdas.post_notify.app.check_if_live_streaming")
    @patch("lambdas.post_notify.app.parse_websub_xml")
    @patch("lambdas.post_notify.app.verify_hmac_signature")
    def test_lambda_handler_not_live_stream(self, mock_verify, mock_parse, mock_check_live):
        """Test Lambda handler when video is not live stream"""
        mock_verify.return_value = None
        mock_parse.return_value = {
            "video_id": "test_video_id",
            "title": "Test Title",
            "url": "test_url"
        }
        mock_check_live.return_value = None
        
        event = {
            "body": "test_xml_content"
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 200
        assert result["body"] == "OK"

    @patch("lambdas.post_notify.app.check_if_notified")
    @patch("lambdas.post_notify.app.check_if_live_streaming")
    @patch("lambdas.post_notify.app.parse_websub_xml")
    @patch("lambdas.post_notify.app.verify_hmac_signature")
    def test_lambda_handler_already_notified(self, mock_verify, mock_parse, 
                                             mock_check_live, mock_check_notified):
        """Test Lambda handler when already notified"""
        mock_verify.return_value = None
        mock_parse.return_value = {
            "video_id": "test_video_id",
            "title": "Test Title",
            "url": "test_url"
        }
        mock_check_live.return_value = "test_thumbnail"
        mock_check_notified.return_value = True
        
        event = {
            "body": "test_xml_content"
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 200
        assert result["body"] == "OK"

    @patch("lambdas.post_notify.app.verify_hmac_signature")
    def test_lambda_handler_exception(self, mock_verify):
        """Test Lambda handler when exception occurs"""
        mock_verify.side_effect = Exception("Test exception")
        
        event = {
            "body": "test_xml_content"
        }
        
        result = lambda_handler(event, None)
        
        assert result["statusCode"] == 500
        assert result["body"] == "Internal Server Error"
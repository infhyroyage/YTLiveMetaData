"""Test post_notify Lambda function"""

import hashlib
import hmac
import os
from unittest.mock import Mock, patch

import pytest

# pylint: disable=import-outside-toplevel,too-few-public-methods


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestGetParameterValue:
    """get_parameter_value function tests"""

    def test_get_parameter_value_success(self):
        """Test successful parameter retrieval"""
        from lambdas.post_notify.app import get_parameter_value

        with patch("lambdas.post_notify.app.ssm_client") as mock_ssm_client:
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
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestVerifyHmacSignature:
    """verify_hmac_signature function tests"""

    def test_verify_hmac_signature_success(self):
        """Test successful HMAC signature verification"""
        from lambdas.post_notify.app import verify_hmac_signature

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "secret_key"

            # Calculate expected signature
            body = "test_body"
            expected_signature = hmac.new(
                "secret_key".encode("utf-8"), body.encode("utf-8"), hashlib.sha1
            ).hexdigest()

            event = {
                "headers": {"X-Hub-Signature": f"sha1={expected_signature}"},
                "body": body,
            }

            result = verify_hmac_signature(event)

            assert result is None

    def test_verify_hmac_signature_missing_header(self):
        """Test missing X-Hub-Signature header"""
        from lambdas.post_notify.app import verify_hmac_signature

        event = {"headers": {}, "body": "test_body"}

        result = verify_hmac_signature(event)

        assert result == "Missing X-Hub-Signature header"

    def test_verify_hmac_signature_unsupported_method(self):
        """Test unsupported signature method"""
        from lambdas.post_notify.app import verify_hmac_signature

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "secret_key"

            event = {
                "headers": {"X-Hub-Signature": "md5=invalidhash"},
                "body": "test_body",
            }

            result = verify_hmac_signature(event)

            assert result == "Unsupported signature method: md5"

    def test_verify_hmac_signature_verification_failed(self):
        """Test HMAC signature verification failure"""
        from lambdas.post_notify.app import verify_hmac_signature

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "secret_key"

            event = {
                "headers": {"X-Hub-Signature": "sha1=invalidhash"},
                "body": "test_body",
            }

            result = verify_hmac_signature(event)

            assert result == "HMAC signature verification failed"

    def test_verify_hmac_signature_case_insensitive_headers(self):
        """Test case insensitive header handling"""
        from lambdas.post_notify.app import verify_hmac_signature

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "secret_key"

            body = "test_body"
            expected_signature = hmac.new(
                "secret_key".encode("utf-8"), body.encode("utf-8"), hashlib.sha1
            ).hexdigest()

            event = {
                "headers": {
                    "x-hub-signature": f"sha1={expected_signature}"  # lowercase
                },
                "body": body,
            }

            result = verify_hmac_signature(event)

            assert result is None


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestParseWebsubXml:
    """parse_websub_xml function tests"""

    def test_parse_websub_xml_success(self):
        """Test successful XML parsing"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <yt:videoId>test_video_id</yt:videoId>
                <title>Test Video Title</title>
            </entry>
        </feed>"""

        result = parse_websub_xml(xml_content)

        assert result["video_id"] == "test_video_id"
        assert result["title"] == "Test Video Title"
        assert result["url"] == "https://www.youtube.com/watch?v=test_video_id"

    def test_parse_websub_xml_no_entry(self):
        """Test XML parsing with no entry"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
        </feed>"""

        with pytest.raises(ValueError, match="No entry found in XML"):
            parse_websub_xml(xml_content)

    def test_parse_websub_xml_no_video_id(self):
        """Test XML parsing with no video ID"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <title>Test Video Title</title>
            </entry>
        </feed>"""

        with pytest.raises(ValueError, match="No videoId found in XML"):
            parse_websub_xml(xml_content)

    def test_parse_websub_xml_no_title(self):
        """Test XML parsing with no title"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <yt:videoId>test_video_id</yt:videoId>
            </entry>
        </feed>"""

        with pytest.raises(ValueError, match="No title found in XML"):
            parse_websub_xml(xml_content)


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestCheckIfLiveStreaming:
    """check_if_live_streaming function tests"""

    def test_check_if_live_streaming_live(self):
        """Test live streaming check when video is live"""
        from lambdas.post_notify.app import check_if_live_streaming

        with patch("lambdas.post_notify.app.requests.get") as mock_requests:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "test_api_key"
                mock_response = Mock()
                mock_response.json.return_value = {
                    "items": [
                        {
                            "snippet": {
                                "liveBroadcastContent": "live",
                                "thumbnails": {
                                    "high": {"url": "https://example.com/high.jpg"},
                                    "medium": {"url": "https://example.com/medium.jpg"},
                                    "default": {
                                        "url": "https://example.com/default.jpg"
                                    },
                                },
                            }
                        }
                    ]
                }
                mock_response.raise_for_status.return_value = None
                mock_requests.return_value = mock_response

                result = check_if_live_streaming("test_video_id")

                assert result == "https://example.com/high.jpg"

    def test_check_if_live_streaming_not_live(self):
        """Test live streaming check when video is not live"""
        from lambdas.post_notify.app import check_if_live_streaming

        with patch("lambdas.post_notify.app.requests.get") as mock_requests:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "test_api_key"
                mock_response = Mock()
                mock_response.json.return_value = {
                    "items": [{"snippet": {"liveBroadcastContent": "none"}}]
                }
                mock_response.raise_for_status.return_value = None
                mock_requests.return_value = mock_response

                result = check_if_live_streaming("test_video_id")

                assert result is None

    def test_check_if_live_streaming_no_thumbnails(self):
        """Test live streaming check when no thumbnails are available"""
        from lambdas.post_notify.app import check_if_live_streaming

        with patch("lambdas.post_notify.app.requests.get") as mock_requests:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "test_api_key"
                mock_response = Mock()
                mock_response.json.return_value = {
                    "items": [{"snippet": {"liveBroadcastContent": "live"}}]
                }
                mock_response.raise_for_status.return_value = None
                mock_requests.return_value = mock_response

                result = check_if_live_streaming("test_video_id")

                assert result == ""

    def test_check_if_live_streaming_no_items(self):
        """Test live streaming check when no items are returned"""
        from lambdas.post_notify.app import check_if_live_streaming

        with patch("lambdas.post_notify.app.requests.get") as mock_requests:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "test_api_key"
                mock_response = Mock()
                mock_response.json.return_value = {}
                mock_response.raise_for_status.return_value = None
                mock_requests.return_value = mock_response

                with pytest.raises(ValueError, match="Video not found"):
                    check_if_live_streaming("test_video_id")

    def test_check_if_live_streaming_no_snippet(self):
        """Test live streaming check when no snippet is returned"""
        from lambdas.post_notify.app import check_if_live_streaming

        with patch("lambdas.post_notify.app.requests.get") as mock_requests:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "test_api_key"
                mock_response = Mock()
                mock_response.json.return_value = {"items": [{}]}
                mock_response.raise_for_status.return_value = None
                mock_requests.return_value = mock_response

                with pytest.raises(ValueError, match="snippet not found"):
                    check_if_live_streaming("test_video_id")

    def test_check_if_live_streaming_no_live_broadcast_content(self):
        """Test live streaming check when no liveBroadcastContent is returned"""
        from lambdas.post_notify.app import check_if_live_streaming

        with patch("lambdas.post_notify.app.requests.get") as mock_requests:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "test_api_key"
                mock_response = Mock()
                mock_response.json.return_value = {"items": [{"snippet": {}}]}
                mock_response.raise_for_status.return_value = None
                mock_requests.return_value = mock_response

                with pytest.raises(ValueError, match="liveBroadcastContent not found"):
                    check_if_live_streaming("test_video_id")


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestCheckIfNotified:
    """check_if_notified function tests"""

    def test_check_if_notified_true(self):
        """Test check if notified returns True"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = {
                "Item": {"is_notified": {"BOOL": True}}
            }

            result = check_if_notified("test_video_id")

            assert result is True

    def test_check_if_notified_false(self):
        """Test check if notified returns False"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = {
                "Item": {"is_notified": {"BOOL": False}}
            }

            result = check_if_notified("test_video_id")

            assert result is False

    def test_check_if_notified_no_item(self):
        """Test check if notified when no item exists"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = {}

            result = check_if_notified("test_video_id")

            assert result is False

    def test_check_if_notified_none_response(self):
        """Test check if notified when response is None"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = None

            result = check_if_notified("test_video_id")

            assert result is False


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestRecordNotified:
    """record_notified function tests"""

    def test_record_notified_success(self):
        """Test successful record notified"""
        from lambdas.post_notify.app import record_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            with patch("time.time") as mock_time:
                mock_time.return_value = 1234567890

                record_notified(
                    "test_video_id", "Test Title", "test_url", "test_thumbnail"
                )

                mock_dynamodb_client.update_item.assert_called_once()


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestSendSmsNotification:
    """send_sms_notification function tests"""

    def test_send_sms_notification_with_thumbnail(self):
        """Test SMS notification with thumbnail"""
        from lambdas.post_notify.app import send_sms_notification

        with patch("lambdas.post_notify.app.sns_client") as mock_sns_client:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "+1234567890"

                send_sms_notification("Test Title", "test_url", "test_thumbnail")

                assert mock_sns_client.publish.call_count == 3

    def test_send_sms_notification_without_thumbnail(self):
        """Test SMS notification without thumbnail"""
        from lambdas.post_notify.app import send_sms_notification

        with patch("lambdas.post_notify.app.sns_client") as mock_sns_client:
            with patch(
                "lambdas.post_notify.app.get_parameter_value"
            ) as mock_get_parameter:
                mock_get_parameter.return_value = "+1234567890"

                send_sms_notification("Test Title", "test_url", "")

                assert mock_sns_client.publish.call_count == 2


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestLambdaHandler:
    """lambda_handler function tests"""

    def test_lambda_handler_success(self):
        """Test successful Lambda handler execution"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.record_notified"):
            with patch("lambdas.post_notify.app.send_sms_notification"):
                with patch(
                    "lambdas.post_notify.app.check_if_notified"
                ) as mock_check_notified:
                    with patch(
                        "lambdas.post_notify.app.check_if_live_streaming"
                    ) as mock_check_live:
                        with patch(
                            "lambdas.post_notify.app.parse_websub_xml"
                        ) as mock_parse:
                            with patch(
                                "lambdas.post_notify.app.verify_hmac_signature"
                            ) as mock_verify:
                                mock_verify.return_value = None
                                mock_parse.return_value = {
                                    "video_id": "test_video_id",
                                    "title": "Test Title",
                                    "url": "test_url",
                                }
                                mock_check_live.return_value = "test_thumbnail"
                                mock_check_notified.return_value = False

                                event = {"body": "test_xml_content"}

                                result = lambda_handler(event, None)

                                assert result["statusCode"] == 200
                                assert result["body"] == "OK"

    def test_lambda_handler_hmac_verification_failed(self):
        """Test Lambda handler when HMAC verification fails"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.verify_hmac_signature") as mock_verify:
            mock_verify.return_value = "HMAC verification failed"

            event = {"body": "test_xml_content"}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 400
            assert result["body"] == "HMAC verification failed"

    def test_lambda_handler_not_live_stream(self):
        """Test Lambda handler when video is not live stream"""
        from lambdas.post_notify.app import lambda_handler

        with patch(
            "lambdas.post_notify.app.check_if_live_streaming"
        ) as mock_check_live:
            with patch("lambdas.post_notify.app.parse_websub_xml") as mock_parse:
                with patch(
                    "lambdas.post_notify.app.verify_hmac_signature"
                ) as mock_verify:
                    mock_verify.return_value = None
                    mock_parse.return_value = {
                        "video_id": "test_video_id",
                        "title": "Test Title",
                        "url": "test_url",
                    }
                    mock_check_live.return_value = None

                    event = {"body": "test_xml_content"}

                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 200
                    assert result["body"] == "OK"

    def test_lambda_handler_already_notified(self):
        """Test Lambda handler when already notified"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.check_if_notified") as mock_check_notified:
            with patch(
                "lambdas.post_notify.app.check_if_live_streaming"
            ) as mock_check_live:
                with patch("lambdas.post_notify.app.parse_websub_xml") as mock_parse:
                    with patch(
                        "lambdas.post_notify.app.verify_hmac_signature"
                    ) as mock_verify:
                        mock_verify.return_value = None
                        mock_parse.return_value = {
                            "video_id": "test_video_id",
                            "title": "Test Title",
                            "url": "test_url",
                        }
                        mock_check_live.return_value = "test_thumbnail"
                        mock_check_notified.return_value = True

                        event = {"body": "test_xml_content"}

                        result = lambda_handler(event, None)

                        assert result["statusCode"] == 200
                        assert result["body"] == "OK"

    def test_lambda_handler_exception(self):
        """Test Lambda handler when exception occurs"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.verify_hmac_signature") as mock_verify:
            mock_verify.side_effect = Exception("Test exception")

            event = {"body": "test_xml_content"}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 500
            assert result["body"] == "Internal Server Error"

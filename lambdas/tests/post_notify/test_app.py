"""WebSubでのYouTubeライブ配信通知情報をもとにSMS通知を送信するユニットテスト"""

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
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestVerifyHmacSignature:
    """verify_hmac_signature関数のテスト"""

    def test_verify_hmac_signature_missing_header(self):
        """X-Hub-Signatureヘッダーが欠如している場合のテスト"""
        from lambdas.post_notify.app import verify_hmac_signature

        event = {"headers": {}, "body": "test_body"}

        result = verify_hmac_signature(event)

        assert result == "Missing X-Hub-Signature header"

    def test_verify_hmac_signature_unsupported_method(self):
        """サポートされていない署名メソッドの場合のテスト"""
        from lambdas.post_notify.app import verify_hmac_signature

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_secret"

            event = {
                "headers": {"X-Hub-Signature": "md5=test_signature"},
                "body": "test_body",
            }

            result = verify_hmac_signature(event)

            assert result == "Unsupported signature method: md5"

    def test_verify_hmac_signature_verification_failed(self):
        """HMAC署名検証が失敗した場合のテスト"""
        from lambdas.post_notify.app import verify_hmac_signature

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_secret"

            event = {
                "headers": {"X-Hub-Signature": "sha1=invalid_signature"},
                "body": "test_body",
            }

            result = verify_hmac_signature(event)

            assert result == "HMAC signature verification failed"

    def test_verify_hmac_signature_success(self):
        """HMAC署名検証が成功した場合のテスト"""
        from lambdas.post_notify.app import verify_hmac_signature

        test_secret = "test_secret"
        test_body = "test_body"
        expected_signature = hmac.new(
            test_secret.encode("utf-8"), test_body.encode("utf-8"), hashlib.sha1
        ).hexdigest()

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = test_secret

            event = {
                "headers": {"X-Hub-Signature": f"sha1={expected_signature}"},
                "body": test_body,
            }

            result = verify_hmac_signature(event)

            assert result is None

    def test_verify_hmac_signature_case_insensitive_header(self):
        """ヘッダー名が大文字小文字を区別しない場合のテスト"""
        from lambdas.post_notify.app import verify_hmac_signature

        test_secret = "test_secret"
        test_body = "test_body"
        expected_signature = hmac.new(
            test_secret.encode("utf-8"), test_body.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = test_secret

            event = {
                "headers": {"x-hub-signature": f"sha256={expected_signature}"},
                "body": test_body,
            }

            result = verify_hmac_signature(event)

            assert result is None


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestParseWebsubXml:
    """parse_websub_xml関数のテスト"""

    def test_parse_websub_xml_success(self):
        """XMLの解析が成功した場合のテスト"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <yt:videoId>test_video_id</yt:videoId>
                <title>Test Video Title</title>
            </entry>
        </feed>"""

        result = parse_websub_xml(xml_content)

        expected = {
            "video_id": "test_video_id",
            "title": "Test Video Title",
            "url": "https://www.youtube.com/watch?v=test_video_id",
        }
        assert result == expected

    def test_parse_websub_xml_no_entry(self):
        """XMLにentryが存在しない場合のテスト"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015">
        </feed>"""

        with pytest.raises(ValueError, match="No entry found in XML"):
            parse_websub_xml(xml_content)

    def test_parse_websub_xml_no_video_id(self):
        """XMLにvideoIdが存在しない場合のテスト"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015">
            <entry>
                <title>Test Video Title</title>
            </entry>
        </feed>"""

        with pytest.raises(ValueError, match="No videoId found in XML"):
            parse_websub_xml(xml_content)

    def test_parse_websub_xml_no_title(self):
        """XMLにtitleが存在しない場合のテスト"""
        from lambdas.post_notify.app import parse_websub_xml

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015">
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
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestCheckIfLiveStreaming:
    """check_if_live_streaming関数のテスト"""

    def test_check_if_live_streaming_live_stream_with_thumbnail(self):
        """ライブ配信中でサムネイルがある場合のテスト"""
        from lambdas.post_notify.app import check_if_live_streaming

        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "snippet": {
                        "liveBroadcastContent": "live",
                        "thumbnails": {
                            "high": {"url": "https://example.com/high.jpg"},
                            "medium": {"url": "https://example.com/medium.jpg"},
                            "default": {"url": "https://example.com/default.jpg"},
                        },
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_api_key"
            with patch("lambdas.post_notify.app.requests.get") as mock_get:
                mock_get.return_value = mock_response

                result = check_if_live_streaming("test_video_id")

                assert result == "https://example.com/high.jpg"

    def test_check_if_live_streaming_live_stream_without_thumbnail(self):
        """ライブ配信中でサムネイルがない場合のテスト"""
        from lambdas.post_notify.app import check_if_live_streaming

        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{"snippet": {"liveBroadcastContent": "live"}}]
        }
        mock_response.raise_for_status.return_value = None

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_api_key"
            with patch("lambdas.post_notify.app.requests.get") as mock_get:
                mock_get.return_value = mock_response

                result = check_if_live_streaming("test_video_id")

                assert result == ""

    def test_check_if_live_streaming_not_live(self):
        """ライブ配信中でない場合のテスト"""
        from lambdas.post_notify.app import check_if_live_streaming

        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{"snippet": {"liveBroadcastContent": "none"}}]
        }
        mock_response.raise_for_status.return_value = None

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_api_key"
            with patch("lambdas.post_notify.app.requests.get") as mock_get:
                mock_get.return_value = mock_response

                result = check_if_live_streaming("test_video_id")

                assert result is None

    def test_check_if_live_streaming_video_not_found(self):
        """動画が見つからない場合のテスト"""
        from lambdas.post_notify.app import check_if_live_streaming

        mock_response = Mock()
        mock_response.json.return_value = {"items": None}
        mock_response.raise_for_status.return_value = None

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_api_key"
            with patch("lambdas.post_notify.app.requests.get") as mock_get:
                mock_get.return_value = mock_response

                with pytest.raises(ValueError, match="Video not found"):
                    check_if_live_streaming("test_video_id")

    def test_check_if_live_streaming_snippet_not_found(self):
        """snippetが見つからない場合のテスト"""
        from lambdas.post_notify.app import check_if_live_streaming

        mock_response = Mock()
        mock_response.json.return_value = {"items": [{}]}
        mock_response.raise_for_status.return_value = None

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_api_key"
            with patch("lambdas.post_notify.app.requests.get") as mock_get:
                mock_get.return_value = mock_response

                with pytest.raises(ValueError, match="snippet not found"):
                    check_if_live_streaming("test_video_id")

    def test_check_if_live_streaming_live_broadcast_content_not_found(self):
        """liveBroadcastContentが見つからない場合のテスト"""
        from lambdas.post_notify.app import check_if_live_streaming

        mock_response = Mock()
        mock_response.json.return_value = {"items": [{"snippet": {}}]}
        mock_response.raise_for_status.return_value = None

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "test_api_key"
            with patch("lambdas.post_notify.app.requests.get") as mock_get:
                mock_get.return_value = mock_response

                with pytest.raises(ValueError, match="liveBroadcastContent not found"):
                    check_if_live_streaming("test_video_id")


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestCheckIfNotified:
    """check_if_notified関数のテスト"""

    def test_check_if_notified_not_notified(self):
        """通知されていない場合のテスト"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = {}

            result = check_if_notified("test_video_id")

            assert result is False
            mock_dynamodb_client.get_item.assert_called_once_with(
                TableName="test-dynamodb-table",
                Key={"video_id": {"S": "test_video_id"}},
                ConsistentRead=True,
            )

    def test_check_if_notified_already_notified(self):
        """すでに通知済みの場合のテスト"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = {
                "Item": {"is_notified": {"BOOL": True}}
            }

            result = check_if_notified("test_video_id")

            assert result is True
            mock_dynamodb_client.get_item.assert_called_once_with(
                TableName="test-dynamodb-table",
                Key={"video_id": {"S": "test_video_id"}},
                ConsistentRead=True,
            )

    def test_check_if_notified_is_notified_false(self):
        """is_notifiedがFalseの場合のテスト"""
        from lambdas.post_notify.app import check_if_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            mock_dynamodb_client.get_item.return_value = {
                "Item": {"is_notified": {"BOOL": False}}
            }

            result = check_if_notified("test_video_id")

            assert result is False


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestRecordNotified:
    """record_notified関数のテスト"""

    def test_record_notified_success(self):
        """記録が成功した場合のテスト"""
        from lambdas.post_notify.app import record_notified

        with patch("lambdas.post_notify.app.dynamodb_client") as mock_dynamodb_client:
            with patch("lambdas.post_notify.app.time.time") as mock_time:
                mock_time.return_value = 1234567890

                record_notified(
                    "test_video_id",
                    "test_title",
                    "https://example.com/video",
                    "https://example.com/thumbnail.jpg",
                )

                mock_dynamodb_client.update_item.assert_called_once_with(
                    TableName="test-dynamodb-table",
                    Key={"video_id": {"S": "test_video_id"}},
                    UpdateExpression=(
                        "SET notified_timestamp = :notified_timestamp, "
                        "is_notified = :is_notified, "
                        "title = :title, "
                        "#url = :url, "
                        "thumbnail_url = :thumbnail_url"
                    ),
                    ExpressionAttributeNames={"#url": "url"},
                    ExpressionAttributeValues={
                        ":notified_timestamp": {"N": "1234567890"},
                        ":is_notified": {"BOOL": True},
                        ":title": {"S": "test_title"},
                        ":url": {"S": "https://example.com/video"},
                        ":thumbnail_url": {"S": "https://example.com/thumbnail.jpg"},
                    },
                )


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestSendSmsNotification:
    """send_sms_notification関数のテスト"""

    def test_send_sms_notification_with_thumbnail(self):
        """サムネイルありでSMS通知を送信した場合のテスト"""
        from lambdas.post_notify.app import send_sms_notification

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "+1234567890"
            with patch("lambdas.post_notify.app.sns_client") as mock_sns_client:
                send_sms_notification(
                    "Test Title",
                    "https://example.com/video",
                    "https://example.com/thumbnail.jpg",
                )
                mock_sns_client.publish.assert_called_once_with(
                    PhoneNumber="+1234567890",
                    Message=(
                        "Test Title"
                        "\n\n"
                        "https://example.com/video"
                        "\n\n"
                        "https://example.com/thumbnail.jpg"
                    ),
                )

    def test_send_sms_notification_without_thumbnail(self):
        """サムネイルなしでSMS通知を送信した場合のテスト"""
        from lambdas.post_notify.app import send_sms_notification

        with patch("lambdas.post_notify.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "+1234567890"
            with patch("lambdas.post_notify.app.sns_client") as mock_sns_client:
                send_sms_notification("Test Title", "https://example.com/video", "")
                mock_sns_client.publish.assert_called_once_with(
                    PhoneNumber="+1234567890",
                    Message=("Test Title\n\nhttps://example.com/video"),
                )


@patch.dict(
    os.environ,
    {
        "DYNAMODB_TABLE": "test-dynamodb-table",
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_API_KEY_PARAMETER_NAME": "test-youtube-api-key-param",
    },
)
class TestLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_lambda_handler_success(self):
        """Lambda関数ハンドラーの成功実行テスト"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.record_notified"):
            with patch("lambdas.post_notify.app.send_sms_notification"):
                with patch(
                    "lambdas.post_notify.app.check_if_notified"
                ) as mock_check_notified:
                    mock_check_notified.return_value = False
                    with patch(
                        "lambdas.post_notify.app.check_if_live_streaming"
                    ) as mock_check_live:
                        mock_check_live.return_value = "https://example.com/thumb.jpg"
                        with patch(
                            "lambdas.post_notify.app.parse_websub_xml"
                        ) as mock_parse_xml:
                            mock_parse_xml.return_value = {
                                "video_id": "test_video_id",
                                "title": "Test Title",
                                "url": "https://example.com/video",
                            }
                            with patch(
                                "lambdas.post_notify.app.verify_hmac_signature"
                            ) as mock_verify:
                                mock_verify.return_value = None

                                event = {"body": "test_xml"}
                                result = lambda_handler(event, None)

                                assert result == {"statusCode": 200, "body": "OK"}

    def test_lambda_handler_hmac_verification_failed(self):
        """HMAC検証が失敗した場合のテスト"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.verify_hmac_signature") as mock_verify_hmac:
            mock_verify_hmac.return_value = "Verification failed"

            event = {"body": "test_xml"}
            result = lambda_handler(event, None)

            assert result == {"statusCode": 400, "body": "Verification failed"}

    def test_lambda_handler_not_live_stream(self):
        """ライブ配信でない場合のテスト"""
        from lambdas.post_notify.app import lambda_handler

        with patch(
            "lambdas.post_notify.app.check_if_live_streaming"
        ) as mock_check_live:
            mock_check_live.return_value = None
            with patch("lambdas.post_notify.app.parse_websub_xml") as mock_parse_xml:
                mock_parse_xml.return_value = {
                    "video_id": "test_video_id",
                    "title": "Test Title",
                    "url": "https://example.com/video",
                }
                with patch(
                    "lambdas.post_notify.app.verify_hmac_signature"
                ) as mock_verify:
                    mock_verify.return_value = None

                    event = {"body": "test_xml"}
                    result = lambda_handler(event, None)

                    assert result == {"statusCode": 200, "body": "OK"}

    def test_lambda_handler_already_notified(self):
        """すでに通知済みの場合のテスト"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.check_if_notified") as mock_check_notified:
            mock_check_notified.return_value = True
            with patch(
                "lambdas.post_notify.app.check_if_live_streaming"
            ) as mock_check_live:
                mock_check_live.return_value = "https://example.com/thumb.jpg"
                with patch(
                    "lambdas.post_notify.app.parse_websub_xml"
                ) as mock_parse_xml:
                    mock_parse_xml.return_value = {
                        "video_id": "test_video_id",
                        "title": "Test Title",
                        "url": "https://example.com/video",
                    }
                    with patch(
                        "lambdas.post_notify.app.verify_hmac_signature"
                    ) as mock_verify:
                        mock_verify.return_value = None

                        event = {"body": "test_xml"}
                        result = lambda_handler(event, None)

                        assert result == {"statusCode": 200, "body": "OK"}

    def test_lambda_handler_exception(self):
        """例外が発生した場合のテスト"""
        from lambdas.post_notify.app import lambda_handler

        with patch("lambdas.post_notify.app.verify_hmac_signature") as mock_verify_hmac:
            mock_verify_hmac.side_effect = Exception("Test exception")

            event = {"body": "test_xml"}
            result = lambda_handler(event, None)

            assert result == {"statusCode": 500, "body": "Internal Server Error"}

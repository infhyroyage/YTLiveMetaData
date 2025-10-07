"""WebSubでのYouTubeライブ配信サブスクリプション登録を確認するユニットテスト"""

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
class TestVerifyQueryParams:
    """vetify_query_params関数のテスト"""

    def test_verify_query_params_success(self):
        """クエリパラメータ検証の成功テスト"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?"
                    "channel_id=test_channel_id"
                ),
                "hub.lease_seconds": "828000",
            }

            result = vetify_query_params(query_params)
            assert result is None

    def test_verify_query_params_missing_challenge(self):
        """hub.challengeが不足している場合のテスト"""
        from lambdas.get_notify.app import vetify_query_params

        query_params = {}
        result = vetify_query_params(query_params)
        assert result == "Bad Request: Missing hub.challenge parameter"

    def test_verify_query_params_invalid_mode(self):
        """hub.modeが無効な場合のテスト"""
        from lambdas.get_notify.app import vetify_query_params

        query_params = {
            "hub.challenge": "test_challenge",
            "hub.mode": "unsubscribe",
        }
        result = vetify_query_params(query_params)
        assert result == "Bad Request: Invalid hub.mode: unsubscribe"

    def test_verify_query_params_invalid_secret(self):
        """hub.secretが無効な場合のテスト"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.return_value = "valid_secret"

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "invalid_secret",
            }
            result = vetify_query_params(query_params)
            assert result == "Bad Request: Invalid hub.secret: invalid_secret"

    def test_verify_query_params_invalid_topic(self):
        """hub.topicが無効な場合のテスト"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?"
                    "channel_id=invalid_channel_id"
                ),
            }
            result = vetify_query_params(query_params)
            expected_error = (
                "Bad Request: Unexpected topic URL: "
                "https://www.youtube.com/xml/feeds/videos.xml?"
                "channel_id=invalid_channel_id"
            )
            assert result == expected_error

    def test_verify_query_params_invalid_lease_seconds(self):
        """hub.lease_secondsが無効な場合のテスト"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?"
                    "channel_id=test_channel_id"
                ),
                "hub.lease_seconds": "invalid",
            }
            result = vetify_query_params(query_params)
            assert result == "Bad Request: Invalid hub.lease_seconds: invalid"

    def test_verify_query_params_wrong_lease_seconds(self):
        """hub.lease_secondsが間違った値の場合のテスト"""
        from lambdas.get_notify.app import vetify_query_params

        with patch("lambdas.get_notify.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = ["test_secret", "test_channel_id"]

            query_params = {
                "hub.challenge": "test_challenge",
                "hub.mode": "subscribe",
                "hub.secret": "test_secret",
                "hub.topic": (
                    "https://www.youtube.com/xml/feeds/videos.xml?"
                    "channel_id=test_channel_id"
                ),
                "hub.lease_seconds": "123456",
            }
            result = vetify_query_params(query_params)
            assert result == "Bad Request: Invalid hub.lease_seconds: 123456"


@patch.dict(
    os.environ,
    {
        "WEBSUB_HMAC_SECRET_PARAMETER_NAME": "test-hmac-secret-param",
        "YOUTUBE_CHANNEL_ID_PARAMETER_NAME": "test-channel-id-param",
    },
)
class TestLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_lambda_handler_success(self):
        """Lambda関数ハンドラーの成功テスト"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = None

            event = {
                "queryStringParameters": {
                    "hub.challenge": "test_challenge",
                }
            }
            context = None

            result = lambda_handler(event, context)

            assert result["statusCode"] == 200
            assert result["headers"] == {"Content-Type": "text/plain"}
            assert result["body"] == "test_challenge"

    def test_lambda_handler_verification_failed(self):
        """Lambda関数ハンドラーの検証失敗テスト"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = "Verification failed"

            event = {
                "queryStringParameters": {
                    "hub.challenge": "test_challenge",
                }
            }
            context = None

            result = lambda_handler(event, context)

            assert result["statusCode"] == 400
            assert result["body"] == "Verification failed"

    def test_lambda_handler_no_query_params(self):
        """Lambda関数ハンドラーでクエリパラメータがない場合のテスト"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.return_value = "Missing hub.challenge parameter"

            event = {}
            context = None

            result = lambda_handler(event, context)

            assert result["statusCode"] == 400
            assert result["body"] == "Missing hub.challenge parameter"

    def test_lambda_handler_exception(self):
        """Lambda関数ハンドラーで例外が発生した場合のテスト"""
        from lambdas.get_notify.app import lambda_handler

        with patch("lambdas.get_notify.app.vetify_query_params") as mock_verify:
            mock_verify.side_effect = Exception("Test exception")

            event = {
                "queryStringParameters": {
                    "hub.challenge": "test_challenge",
                }
            }
            context = None

            result = lambda_handler(event, context)

            assert result["statusCode"] == 500
            assert result["body"] == "Internal Server Error"

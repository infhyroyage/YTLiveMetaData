"""Google PubSubHubbubのサブスクリプションを再登録するユニットテスト"""

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
class TestSubscribeToPubsubhubbub:
    """subscribe_to_pubsubhubbub関数のテスト"""

    def test_subscribe_to_pubsubhubbub_success(self):
        """PubSubHubbubへのサブスクリプション成功テスト"""
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
        """PubSubHubbubへのサブスクリプション失敗テスト"""
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
        """サブスクリプションリクエストの正しいデータ形式テスト"""
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

            # データに期待されるhub.topic形式（URLエンコード済み）が含まれるかチェック
            assert "channel_id%3Dtest_channel_id" in data
            assert "hub.verify=async" in data
            assert "hub.mode=subscribe" in data
            assert "hub.secret=test_secret" in data

    def test_subscribe_to_pubsubhubbub_correct_headers(self):
        """サブスクリプションリクエストの正しいヘッダーテスト"""
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
        """429スロットリングエラー後の再試行成功テスト"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # 最初の呼び出しは429、2回目の呼び出しは202を返す
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

                # requests.postが2回呼び出されることを検証
                assert mock_requests_post.call_count == 2
                # sleepが1秒遅延（BASE_DELAY * 2^0）で1回呼び出されることを検証
                mock_sleep.assert_called_once_with(1.0)

    def test_subscribe_to_pubsubhubbub_429_max_retries_exceeded(self):
        """429エラーの最大再試行回数超過後の失敗テスト"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # 常に429を返す
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

                # requests.postが6回（初回 + 5回再試行）呼び出されることを検証
                assert mock_requests_post.call_count == 6
                # sleepが指数バックオフで5回呼び出されることを検証
                assert mock_sleep.call_count == 5
                expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0]
                for i, call in enumerate(mock_sleep.call_args_list):
                    assert call[0][0] == expected_delays[i]

    def test_subscribe_to_pubsubhubbub_network_error_immediate_failure(self):
        """ネットワークエラーの即座の失敗テスト（再試行なし）"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # ネットワークエラーは再試行すべきでない
                mock_requests_post.side_effect = requests.exceptions.ConnectionError(
                    "Network error"
                )

                with pytest.raises(requests.exceptions.ConnectionError):
                    subscribe_to_pubsubhubbub(
                        channel_id="test_channel_id",
                        callback_url="https://example.com/callback",
                        hmac_secret="test_secret",
                    )

                # requests.postが1回のみ（再試行なし）呼び出されることを検証
                assert mock_requests_post.call_count == 1
                # sleepが呼び出されないことを検証
                mock_sleep.assert_not_called()

    def test_subscribe_to_pubsubhubbub_non_retryable_error(self):
        """再試行不可能なエラーの即座の失敗テスト（429、ネットワーク以外）"""
        from lambdas.websub.app import subscribe_to_pubsubhubbub

        with patch("lambdas.websub.app.requests.post") as mock_requests_post:
            with patch("lambdas.websub.app.time.sleep") as mock_sleep:
                # 500エラー（再試行不可能）を返す
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

                # requests.postが1回のみ（再試行なし）呼び出されることを検証
                assert mock_requests_post.call_count == 1
                # sleepが呼び出されないことを検証
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
    """lambda_handler関数のテスト"""

    def test_lambda_handler_success(self):
        """Lambda関数ハンドラーの成功実行テスト"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub") as mock_subscribe:
            with patch("lambdas.websub.app.secrets.token_hex") as mock_token_hex:
                with patch("lambdas.websub.app.ssm_client") as mock_ssm_client:
                    with patch(
                        "lambdas.websub.app.get_parameter_value"
                    ) as mock_get_parameter:
                        # Parameter Store からの値の取得をモック
                        mock_get_parameter.side_effect = [
                            "test_channel_id",
                            "https://example.com/callback",
                        ]
                        # HMACシークレット生成をモック
                        mock_token_hex.return_value = "test_secret_hex"

                        event = {}

                        result = lambda_handler(event, None)

                        assert result["statusCode"] == 200
                        assert result["body"] == "OK"
                        # subscribe_to_pubsubhubbub が正しい引数で呼び出されることを検証
                        mock_subscribe.assert_called_once_with(
                            channel_id="test_channel_id",
                            callback_url="https://example.com/callback",
                            hmac_secret="test_secret_hex",
                        )
                        # HMACシークレットがParameter Storeに保存されることを検証
                        mock_ssm_client.put_parameter.assert_called_once_with(
                            Name="test-hmac-secret-param",
                            Value="test_secret_hex",
                            Type="SecureString",
                            Overwrite=True,
                        )

    def test_lambda_handler_get_parameter_exception(self):
        """get_parameter_valueで例外が発生した場合のLambda関数ハンドラーテスト"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.get_parameter_value") as mock_get_parameter:
            mock_get_parameter.side_effect = Exception("Parameter not found")

            event = {}

            result = lambda_handler(event, None)

            assert result["statusCode"] == 500
            assert result["body"] == "Internal server error"

    def test_lambda_handler_token_hex_exception(self):
        """secrets.token_hexで例外が発生した場合のLambda関数ハンドラーテスト"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub"):
            with patch("lambdas.websub.app.secrets.token_hex") as mock_token_hex:
                with patch(
                    "lambdas.websub.app.get_parameter_value"
                ) as mock_get_parameter:
                    mock_get_parameter.side_effect = [
                        "test_channel_id",
                        "https://example.com/callback",
                    ]
                    mock_token_hex.side_effect = Exception("Secret generation failed")

                    event = {}

                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 500
                    assert result["body"] == "Internal server error"

    def test_lambda_handler_subscribe_exception(self):
        """subscribe_to_pubsubhubbubで例外が発生した場合のLambda関数ハンドラーテスト"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub") as mock_subscribe:
            with patch("lambdas.websub.app.secrets.token_hex") as mock_token_hex:
                with patch(
                    "lambdas.websub.app.get_parameter_value"
                ) as mock_get_parameter:
                    mock_get_parameter.side_effect = [
                        "test_channel_id",
                        "https://example.com/callback",
                    ]
                    mock_token_hex.return_value = "test_secret_hex"
                    mock_subscribe.side_effect = Exception("Subscription failed")

                    event = {}

                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 500
                    assert result["body"] == "Internal server error"

    def test_lambda_handler_ssm_put_parameter_exception(self):
        """ssm_client.put_parameterで例外が発生した場合のLambda関数ハンドラーテスト"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub") as mock_subscribe:
            with patch("lambdas.websub.app.secrets.token_hex") as mock_token_hex:
                with patch("lambdas.websub.app.ssm_client") as mock_ssm_client:
                    with patch(
                        "lambdas.websub.app.get_parameter_value"
                    ) as mock_get_parameter:
                        mock_get_parameter.side_effect = [
                            "test_channel_id",
                            "https://example.com/callback",
                        ]
                        mock_token_hex.return_value = "test_secret_hex"
                        mock_ssm_client.put_parameter.side_effect = Exception(
                            "SSM parameter store error"
                        )

                        event = {}

                        result = lambda_handler(event, None)

                        assert result["statusCode"] == 500
                        assert result["body"] == "Internal server error"
                        # subscribe_to_pubsubhubbub は成功している必要がある
                        mock_subscribe.assert_called_once()

    def test_lambda_handler_parameter_order(self):
        """Lambda関数ハンドラーでのパラメータ取得順序テスト"""
        from lambdas.websub.app import lambda_handler

        with patch("lambdas.websub.app.subscribe_to_pubsubhubbub"):
            with patch("lambdas.websub.app.secrets.token_hex") as mock_token_hex:
                with patch("lambdas.websub.app.ssm_client"):
                    with patch(
                        "lambdas.websub.app.get_parameter_value"
                    ) as mock_get_parameter:
                        mock_get_parameter.side_effect = [
                            "test_channel_id",
                            "https://example.com/callback",
                        ]
                        mock_token_hex.return_value = "test_secret_hex"

                        event = {}

                        lambda_handler(event, None)

                        # パラメータが正しい順序で取得されることを検証
                        expected_calls = [
                            ("test-channel-id-param",),
                            ("test-callback-url-param",),
                        ]
                        actual_calls = [
                            call[0] for call in mock_get_parameter.call_args_list
                        ]
                        assert actual_calls == expected_calls

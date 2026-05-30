"""CodePipelineのステージ失敗をSMS通知するユニットテスト"""

import os
from unittest.mock import patch

import pytest

# pylint: disable=import-outside-toplevel,too-few-public-methods


@patch.dict(
    os.environ,
    {
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
    },
)
class TestBuildMessage:
    """build_message関数のテスト"""

    def test_build_message_success(self):
        """detailに全フィールドが存在する場合のテスト"""
        # Given: pipeline/stage/execution-idが全て存在するdetail
        from lambdas.post_pipeline.app import build_message

        detail = {
            "pipeline": "ytlivemetadata-pipeline",
            "stage": "Build",
            "execution-id": "abc-123",
        }

        # When: メッセージを生成する
        result = build_message(detail)

        # Then: 期待フォーマットのメッセージが生成される
        assert result == (
            "[CI/CD] パイプライン ytlivemetadata-pipeline のステージ 'Build' が失敗しました\n"
            "実行ID: abc-123"
        )

    def test_build_message_empty_detail(self):
        """detailが空dictの場合のテスト"""
        # Given: 空のdetail
        from lambdas.post_pipeline.app import build_message

        detail = {}

        # When: メッセージを生成する
        result = build_message(detail)

        # Then: 欠損キーはunknownでメッセージが生成される
        assert result == (
            "[CI/CD] パイプライン unknown のステージ 'unknown' が失敗しました\n"
            "実行ID: unknown"
        )


@patch.dict(
    os.environ,
    {
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
    },
)
class TestSendFailureSms:
    """send_failure_sms関数のテスト"""

    def test_send_failure_sms_success(self):
        """SMS通知が成功した場合のテスト"""
        # Given: 電話番号が取得できる
        from lambdas.post_pipeline.app import send_failure_sms

        with patch("lambdas.post_pipeline.app.get_parameter_value") as mock_get_param:
            mock_get_param.return_value = "+818098765432"
            with patch("lambdas.post_pipeline.app.sns_client") as mock_sns_client:
                # When: SMS通知を送信する
                send_failure_sms("Test failure message")

                # Then: sns_client.publishが1回呼ばれる
                mock_sns_client.publish.assert_called_once_with(
                    PhoneNumber="+818098765432",
                    Message="Test failure message",
                )

    def test_send_failure_sms_ssm_failure(self):
        """SSM取得が失敗した場合のテスト"""
        # Given: SSM取得が例外を送出する
        from lambdas.post_pipeline.app import send_failure_sms

        with patch("lambdas.post_pipeline.app.get_parameter_value") as mock_get_param:
            mock_get_param.side_effect = Exception("SSM error")

            # When/Then: 例外が伝播する
            with pytest.raises(Exception, match="SSM error"):
                send_failure_sms("Test failure message")


@patch.dict(
    os.environ,
    {
        "SMS_PHONE_NUMBER_PARAMETER_NAME": "test-phone-number-param",
    },
)
class TestLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_lambda_handler_success(self):
        """Lambda関数ハンドラーの成功実行テスト"""
        # Given: 正常なEventBridgeイベント
        from lambdas.post_pipeline.app import lambda_handler

        event = {
            "detail": {
                "pipeline": "ytlivemetadata-pipeline",
                "stage": "Build",
                "execution-id": "abc-123",
            }
        }

        with patch("lambdas.post_pipeline.app.send_failure_sms") as mock_send_sms:
            # When: ハンドラーを実行する
            result = lambda_handler(event, None)

            # Then: 200が返りSMS送信が1回呼ばれる
            assert result == {"statusCode": 200, "body": "OK"}
            mock_send_sms.assert_called_once_with(
                "[CI/CD] パイプライン ytlivemetadata-pipeline のステージ 'Build' が失敗しました\n"
                "実行ID: abc-123"
            )

    def test_lambda_handler_missing_detail(self):
        """eventにdetailキーがない場合のテスト"""
        # Given: detailキーがないevent
        from lambdas.post_pipeline.app import lambda_handler

        event = {}

        with patch("lambdas.post_pipeline.app.send_failure_sms") as mock_send_sms:
            # When: ハンドラーを実行する
            result = lambda_handler(event, None)

            # Then: unknownを含むメッセージで200が返る
            assert result == {"statusCode": 200, "body": "OK"}
            mock_send_sms.assert_called_once_with(
                "[CI/CD] パイプライン unknown のステージ 'unknown' が失敗しました\n"
                "実行ID: unknown"
            )

    def test_lambda_handler_send_failure_sms_exception(self):
        """send_failure_smsが例外を送出した場合のテスト"""
        # Given: send_failure_smsが例外を送出する
        from lambdas.post_pipeline.app import lambda_handler

        event = {
            "detail": {
                "pipeline": "ytlivemetadata-pipeline",
                "stage": "Build",
                "execution-id": "abc-123",
            }
        }

        with patch("lambdas.post_pipeline.app.send_failure_sms") as mock_send_sms:
            mock_send_sms.side_effect = Exception("SNS error")

            # When: ハンドラーを実行する
            result = lambda_handler(event, None)

            # Then: 500が返る
            assert result == {"statusCode": 500, "body": "Internal Server Error"}

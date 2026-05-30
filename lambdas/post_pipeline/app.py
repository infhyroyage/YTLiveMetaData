"""CodePipelineのステージ失敗をSMS通知する"""

import logging
import os
import traceback
from typing import Any, Dict

import boto3
from ssm_utils import get_parameter_value

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SMS_PHONE_NUMBER_PARAMETER_NAME = os.environ["SMS_PHONE_NUMBER_PARAMETER_NAME"]

sns_client = boto3.client("sns")


def build_message(detail: Dict[str, Any]) -> str:
    """
    EventBridgeイベントのdetailからSMS通知メッセージを生成する

    Args:
        detail (dict): CodePipeline Stage Execution State Change イベントのdetail

    Returns:
        str: SMS通知メッセージ
    """
    pipeline: str = detail.get("pipeline", "unknown")
    stage: str = detail.get("stage", "unknown")
    execution_id: str = detail.get("execution-id", "unknown")

    return (
        f"[CI/CD] パイプライン {pipeline} のステージ '{stage}' が失敗しました\n"
        f"実行ID: {execution_id}"
    )


def send_failure_sms(message: str) -> None:
    """
    SNSを使用してパイプライン失敗をSMS通知する

    Args:
        message (str): SMS通知メッセージ
    """
    phone_number: str = get_parameter_value(SMS_PHONE_NUMBER_PARAMETER_NAME)
    sns_client.publish(PhoneNumber=phone_number, Message=message)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    CodePipelineのステージ失敗をSMS通知するLambda関数のハンドラー

    Args:
        event (dict): EventBridgeイベント
        context: Lambda実行コンテキスト

    Returns:
        dict: レスポンス
    """
    try:
        detail: Dict[str, Any] = event.get("detail", {})
        message: str = build_message(detail)
        send_failure_sms(message)
        logger.info("Pipeline failure SMS notification sent: %s", message)

        return {
            "statusCode": 200,
            "body": "OK",
        }
    except Exception:
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": "Internal Server Error",
        }

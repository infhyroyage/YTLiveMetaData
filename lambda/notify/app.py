"""WebSubでのYouTubeライブ配信通知情報をもとに、SMS通知を送信する"""

import json
import logging
import os
import traceback
from typing import Any, Dict

import boto3

WEBSUB_HMAC_SECRET_PARAMETER_NAME = os.environ["WEBSUB_HMAC_SECRET_PARAMETER_NAME"]
YOUTUBE_CHANNEL_ID_PARAMETER_NAME = os.environ["YOUTUBE_CHANNEL_ID_PARAMETER_NAME"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm_client = boto3.client("ssm")


def get_parameter_value(parameter_name: str) -> str:
    """
    AWS Systems Manager Parameter Store からパラメータ値を取得する

    Args:
        parameter_name (str): パラメータ名

    Returns:
        str: パラメータ値
    """
    response: Dict[str, Dict[str, str]] = ssm_client.get_parameter(
        Name=parameter_name, WithDecryption=True
    )
    return response["Parameter"]["Value"]


def handle_websub_verification(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    [GET] /notifyでのWebSub検証リクエストを処理する

    Args:
        event (dict): API Gatewayイベント

    Returns:
        dict: レスポンス
    """
    # クエリパラメータから必要なパラメータを取得
    query_params: Dict[str, str] = event.get("queryStringParameters") or {}
    hub_topic: str | None = query_params.get("hub.topic")
    hub_mode: str | None = query_params.get("hub.mode")
    hub_secret: str | None = query_params.get("hub.secret")
    hub_lease_seconds: str | None = query_params.get("hub.lease_seconds")
    hub_challenge: str | None = query_params.get("hub.challenge")

    # パラメータ検証
    if not hub_challenge:
        return {
            "statusCode": 400,
            "body": "Bad Request: Missing hub.challenge parameter",
        }
    if hub_mode and hub_mode != "subscribe":
        return {"statusCode": 400, "body": f"Bad Request: Invalid hub.mode: {hub_mode}"}
    if hub_secret and hub_secret != get_parameter_value(
        WEBSUB_HMAC_SECRET_PARAMETER_NAME
    ):
        return {
            "statusCode": 400,
            "body": f"Bad Request: Invalid hub.secret: {hub_secret}",
        }
    if hub_topic and hub_topic != (
        f"https://www.youtube.com/xml/feeds/videos.xml?"
        f"channel_id={get_parameter_value(YOUTUBE_CHANNEL_ID_PARAMETER_NAME)}"
    ):
        return {
            "statusCode": 400,
            "body": f"Bad Request: Unexpected topic URL: {hub_topic}",
        }
    if (
        hub_lease_seconds
        and not hub_lease_seconds.isdigit()
        and int(hub_lease_seconds) != 828000
    ):
        return {
            "statusCode": 400,
            "body": f"Bad Request: Invalid hub.lease_seconds: {hub_lease_seconds}",
        }

    # 検証成功：hub.challengeをそのまま返す
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/plain"},
        "body": hub_challenge,
    }


def handle_websub_notification(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    [POST] /notifyでのWebSub通知リクエストを処理する
    TODO: ライブ配信通知処理が未実装

    Args:
        event (dict): API Gatewayイベント

    Returns:
        dict: レスポンス
    """
    logger.info("Received WebSub notification (not yet implemented)")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "WebSub notification received"}),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    WebSubでのYouTubeライブ配信通知情報をもとに、SMS通知を送信するLambda関数のハンドラー

    Args:
        event (dict): API Gatewayイベント
        context: Lambda実行コンテキスト

    Returns:
        dict: レスポンス
    """
    try:
        http_method: str = event.get("httpMethod", "").upper()
        if http_method == "GET":
            # [GET] /notify
            return handle_websub_verification(event)
        if http_method == "POST":
            # [POST] /notify
            return handle_websub_notification(event)

        return {
            "statusCode": 405,
            "body": json.dumps({"error": f"Method Not Allowed: {http_method}"}),
        }
    except Exception:
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal Server Error"}),
        }

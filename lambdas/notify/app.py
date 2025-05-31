"""WebSubでのYouTubeライブ配信通知情報をもとに、SMS通知を送信する"""

import hashlib
import hmac
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


def handle_get_notify(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Google PubSubHubbubのサブスクリプションの登録を確認する

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

    # クエリパラメータの検証
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


def verify_hmac_signature(event: Dict[str, Any]) -> bool:
    """
    Google PubSubHubbub Hubからのプッシュ通知のHMAC署名を検証する

    Args:
        event (dict): API Gatewayイベント

    Returns:
        bool: 検証に成功した場合はTrue、失敗した場合はFalse
    """
    # X-Hub-Signatureヘッダーの存在
    signature: str | None = {
        k.lower(): v for k, v in event.get("headers", {}).items()
    }.get("x-hub-signature")
    if not signature:
        logger.error("Missing X-Hub-Signature header")
        return False

    hmac_secret: str = get_parameter_value(WEBSUB_HMAC_SECRET_PARAMETER_NAME)

    # 署名の形式を解析し、サポートされているアルゴリズムかをチェック
    method, sig = signature.split("=", 1)
    if method not in ["sha1", "sha256", "sha384", "sha512"]:
        logger.error("Unsupported signature method: %s", method)
        return False

    # HMACを計算してセキュアに比較
    expected_signature: str = hmac.new(
        hmac_secret.encode("utf-8"),
        event.get("body", "").encode("utf-8"),
        getattr(hashlib, method),
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_signature):
        logger.error("HMAC signature verification failed")
        return False

    return True


def handle_post_notify(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Google PubSubHubbubから受信したYouTubeライブ配信プッシュ通知より、SMS通知を行う
    TODO: 技術スタック「1.3 データフロー」の5以降が未実装

    Args:
        event (dict): API Gatewayイベント

    Returns:
        dict: レスポンス
    """
    # HMAC署名の検証
    if not verify_hmac_signature(event):
        return {
            "statusCode": 400,
            "body": "Invalid WebSub notification",
        }

    return {"statusCode": 200, "body": "OK"}


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
            return handle_get_notify(event)
        if http_method == "POST":
            # [POST] /notify
            return handle_post_notify(event)

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

"""WebSubでのYouTubeライブ配信サブスクリプション登録を確認する"""

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


def vetify_query_params(query_params: Dict[str, str]) -> str | None:
    """
    Google PubSubHubbubのサブスクリプション登録確認を行う

    Args:
        query_params (dict): クエリパラメータ

    Returns:
        str | None: 検証成功時はNone、失敗時はエラーメッセージ
    """
    if not query_params.get("hub.challenge"):
        return "Bad Request: Missing hub.challenge parameter"

    if query_params.get("hub.mode") != "subscribe":
        return f"Bad Request: Invalid hub.mode: {query_params.get('hub.mode')}"

    if query_params.get("hub.secret") and query_params.get(
        "hub.secret"
    ) != get_parameter_value(WEBSUB_HMAC_SECRET_PARAMETER_NAME):
        return f"Bad Request: Invalid hub.secret: {query_params.get('hub.secret')}"

    if query_params.get("hub.topic") and query_params.get("hub.topic") != (
        f"https://www.youtube.com/xml/feeds/videos.xml?"
        f"channel_id={get_parameter_value(YOUTUBE_CHANNEL_ID_PARAMETER_NAME)}"
    ):
        return f"Bad Request: Unexpected topic URL: {query_params.get('hub.topic')}"

    if (
        query_params.get("hub.lease_seconds")
        and not query_params.get("hub.lease_seconds").isdigit()
        and int(query_params.get("hub.lease_seconds")) != 828000
    ):
        return f"Bad Request: Invalid hub.lease_seconds: {query_params.get('hub.lease_seconds')}"

    return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    WebSubでのYouTubeライブ配信サブスクリプション登録を確認するLambda関数ハンドラー

    Args:
        event (dict): API Gatewayイベント
        context: Lambda実行コンテキスト

    Returns:
        dict: レスポンス
    """
    try:
        query_params = event.get("queryStringParameters") or {}
        result = vetify_query_params(query_params)
        if result:
            # 検証失敗：エラーメッセージを返す
            return {
                "statusCode": 400,
                "body": result,
            }

        # 検証成功：hub.challengeを返す
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/plain"},
            "body": query_params.get("hub.challenge"),
        }
    except Exception:
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": "Internal Server Error",
        }

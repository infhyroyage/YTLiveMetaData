"""WebSubでのYouTubeライブ配信通知情報をもとにSMS通知を送信する"""

import hashlib
import hmac
import logging
import os
import traceback
from typing import Any, Dict

import boto3

WEBSUB_HMAC_SECRET_PARAMETER_NAME = os.environ["WEBSUB_HMAC_SECRET_PARAMETER_NAME"]

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


def verify_hmac_signature(event: Dict[str, Any]) -> str | None:
    """
    Google PubSubHubbub Hubからのプッシュ通知のHMAC署名を検証する

    Args:
        event (dict): API Gatewayイベント

    Returns:
        str | None: 検証成功時はNone、失敗時はエラーメッセージ
    """
    # X-Hub-Signatureヘッダーの存在
    signature: str | None = {
        k.lower(): v for k, v in event.get("headers", {}).items()
    }.get("x-hub-signature")
    if not signature:
        return "Missing X-Hub-Signature header"

    hmac_secret: str = get_parameter_value(WEBSUB_HMAC_SECRET_PARAMETER_NAME)

    # 署名の形式を解析し、サポートされているアルゴリズムかをチェック
    method, sig = signature.split("=", 1)
    if method not in ["sha1", "sha256", "sha384", "sha512"]:
        return f"Unsupported signature method: {method}"

    # HMACを計算してセキュアに比較
    expected_signature: str = hmac.new(
        hmac_secret.encode("utf-8"),
        event.get("body", "").encode("utf-8"),
        getattr(hashlib, method),
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_signature):
        return "HMAC signature verification failed"

    return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    WebSubでのYouTubeライブ配信通知情報をもとにSMS通知を送信するLambda関数のハンドラー
    TODO: 技術スタック「1.3 データフロー」の5以降が未実装

    Args:
        event (dict): API Gatewayイベント
        context: Lambda実行コンテキスト

    Returns:
        dict: レスポンス
    """
    try:
        # Google PubSubHubbub Hubからのプッシュ通知のHMAC署名を検証
        verify_result: str | None = verify_hmac_signature(event)
        if verify_result:
            logger.error({"verify_result": verify_result})
            return {
                "statusCode": 400,
                "body": verify_result,
            }

        logger.info("Not implemented")

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

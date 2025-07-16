"""Google PubSubHubbubのサブスクリプションを再登録する"""

import logging
import os
import secrets
import time
import traceback
import urllib.parse
from typing import Any, Dict

import boto3
import requests

PUBSUBHUBBUB_HUB_URL = os.environ["PUBSUBHUBBUB_HUB_URL"]
LEASE_SECONDS = int(os.environ["LEASE_SECONDS"])
HMAC_SECRET_LENGTH = int(os.environ["HMAC_SECRET_LENGTH"])
WEBSUB_HMAC_SECRET_PARAMETER_NAME = os.environ["WEBSUB_HMAC_SECRET_PARAMETER_NAME"]
YOUTUBE_CHANNEL_ID_PARAMETER_NAME = os.environ["YOUTUBE_CHANNEL_ID_PARAMETER_NAME"]
WEBSUB_CALLBACK_URL_PARAMETER_NAME = os.environ["WEBSUB_CALLBACK_URL_PARAMETER_NAME"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm_client = boto3.client("ssm")

# 再試行設定
MAX_RETRIES = 5
BASE_DELAY = 1.0  # 初回待機時間（秒）


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


def subscribe_to_pubsubhubbub(
    channel_id: str,
    callback_url: str,
    hmac_secret: str,
) -> None:
    """
    Google PubSubHubbub Hub にサブスクリプションを登録する

    Args:
        channel_id (str): チャンネルID
        callback_url (str): コールバックURL
        hmac_secret (str): HMACシークレット

    Raises:
        Exception: 指数バックオフでの最大再試行回数を超えた場合、またはスロットルエラー以外のエラーが発生した場合
    """
    # Google PubSubHubbub Hub にPOSTリクエストを送信
    data: str = urllib.parse.urlencode(
        {
            "hub.callback": callback_url,
            "hub.topic": f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}",
            "hub.verify": "async",
            "hub.mode": "subscribe",
            "hub.secret": hmac_secret,
            "hub.lease_seconds": str(LEASE_SECONDS),
        }
    )
    headers: Dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "YTLiveMetaData-WebSub/1.0",
    }

    # 指数バックオフで再試行
    for attempt in range(MAX_RETRIES + 1):
        response = requests.post(
            url=PUBSUBHUBBUB_HUB_URL,
            data=data,
            headers=headers,
            timeout=30,
        )

        logger.info("Response status code: %d", response.status_code)
        logger.info("Response text: %s", response.text)

        # 成功
        if response.status_code == 202:
            logger.info("Subscription successful on attempt %d", attempt + 1)
            return

        # スロットルエラー
        if response.status_code == 429:
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2**attempt)
                logger.warning(
                    "Throttled (429) on attempt %d/%d. Retrying in %.1f seconds...",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    delay,
                )
                time.sleep(delay)
                continue

            logger.error(
                "Subscription failed after %d attempts due to throttling",
                MAX_RETRIES + 1,
            )
            raise Exception(
                f"Subscription failed after {MAX_RETRIES + 1} attempts: "
                f"status code: {response.status_code}, "
                f"response: {response.text}"
            )

        logger.error(
            "Subscription failed with non-retryable error: "
            "status code: %d, response: %s",
            response.status_code,
            response.text,
        )
        raise Exception(
            f"Subscription failed: "
            f"status code: {response.status_code}, "
            f"response: {response.text}"
        )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Google PubSubHubbubのサブスクリプションを再登録するLambda関数のハンドラー

    Args:
        event (dict): イベント
        context: Lambda実行コンテキスト

    Returns:
        dict: レスポンス
    """
    try:
        # Parameter StoreからチャンネルID・コールバックURLを取得
        channel_id: str = get_parameter_value(YOUTUBE_CHANNEL_ID_PARAMETER_NAME)
        callback_url: str = get_parameter_value(WEBSUB_CALLBACK_URL_PARAMETER_NAME)

        # 新しいHMACシークレットを生成
        hmac_secret: str = secrets.token_hex(HMAC_SECRET_LENGTH)

        # Google PubSubHubbub Hubにサブスクリプションを登録
        subscribe_to_pubsubhubbub(
            channel_id=channel_id,
            callback_url=callback_url,
            hmac_secret=hmac_secret,
        )

        # 生成したHMACシークレットをParameter Storeに保存
        ssm_client.put_parameter(
            Name=WEBSUB_HMAC_SECRET_PARAMETER_NAME,
            Value=hmac_secret,
            Type="SecureString",
            Overwrite=True,
        )

        return {
            "statusCode": 200,
            "body": "OK",
        }

    except Exception:
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": "Internal server error",
        }

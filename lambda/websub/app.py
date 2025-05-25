"""Google PubSubHubbubのサブスクリプションを再登録する"""

import json
import logging
import secrets
import traceback
import urllib.parse
from typing import Any, Dict

import boto3
import requests

# Google PubSubHubbub Hub のURL
PUBSUBHUBBUB_HUB_URL = "https://pubsubhubbub.appspot.com/"

# Google PubSubHubbub のリース期間(=10日間=828000秒)
LEASE_SECONDS = 828000

# HMACシークレットの長さ(=32バイト)
HMAC_SECRET_LENGTH = 32

# HMACシークレットのParameter Storeのパス
HMAC_SECRET_PARAMETER_NAME = "/ytlivemetadata/hmac-secret"

# チャンネルIDのParameter Storeのパス
CHANNEL_ID_PARAMETER_NAME = "/ytlivemetadata/channel-id"

# コールバックURLのParameter Storeのパス
CALLBACK_URL_PARAMETER_NAME = "/ytlivemetadata/callback-url"

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
    response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
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
    response = requests.post(
        url=PUBSUBHUBBUB_HUB_URL,
        data=data,
        headers=headers,
        timeout=30,
    )

    logger.info("Response status code: %d", response.status_code)
    logger.info("Response text: %s", response.text)

    if response.status_code != 202:
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
        # Parameter Store からチャンネルID・コールバックURLを取得
        channel_id = get_parameter_value(CHANNEL_ID_PARAMETER_NAME)
        callback_url = get_parameter_value(CALLBACK_URL_PARAMETER_NAME)

        # 新しいHMACシークレットを生成してParameter Storeに保存
        hmac_secret = secrets.token_hex(HMAC_SECRET_LENGTH)
        ssm_client.put_parameter(
            Name=HMAC_SECRET_PARAMETER_NAME,
            Value=hmac_secret,
            Type="SecureString",
            Overwrite=True,
        )

        # Google PubSubHubbub Hub にサブスクリプションを登録
        subscribe_to_pubsubhubbub(
            channel_id=channel_id,
            callback_url=callback_url,
            hmac_secret=hmac_secret,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "WebSub subscription renewed successfully"}),
        }

    except Exception:
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }

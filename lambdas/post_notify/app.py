"""WebSubでのYouTubeライブ配信通知情報をもとにSMS通知を送信する"""

import hashlib
import hmac
import logging
import os
import traceback
from typing import Any, Dict, List
from xml.etree.ElementTree import Element, fromstring

import boto3
import requests

WEBSUB_HMAC_SECRET_PARAMETER_NAME = os.environ["WEBSUB_HMAC_SECRET_PARAMETER_NAME"]
YOUTUBE_API_KEY_PARAMETER_NAME = os.environ["YOUTUBE_API_KEY_PARAMETER_NAME"]

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


def parse_websub_xml(xml_content: str) -> Dict[str, str]:
    """
    WebSubプッシュ通知のXMLコンテンツを解析する

    Args:
        xml_content (str): XMLコンテンツ

    Returns:
        Dict[str, str]: 解析結果(ビデオID、動画タイトル、動画URL)
    """
    root: Element = fromstring(xml_content)
    namespaces: Dict[str, str] = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015'
    }

    # entryを検索
    entry: Element | None = root.find('atom:entry', namespaces)
    if entry is None:
        raise ValueError("No entry found in XML")

    # ビデオIDを取得
    video_id_element: Element | None = entry.find('yt:videoId', namespaces)
    if video_id_element is None:
        raise ValueError("No videoId found in XML")
    video_id: str = video_id_element.text

    # タイトルを取得
    title_element: Element | None = entry.find('atom:title', namespaces)
    if title_element is None:
        raise ValueError("No title found in XML")
    title: str = title_element.text

    return {
        "video_id": video_id,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }


def check_if_live_streaming(video_id: str) -> str | None:
    """
    YouTube Data API v3を使用して現在ライブ配信中かどうかを判定し、
    ライブ配信中の場合はサムネイル画像URLを取得する

    Args:
        video_id (str): ビデオID

    Returns:
        str | None: 現在ライブ配信中の場合はサムネイル画像URL(取得できない場合は空文字列)、
                    ライブ配信中でない場合はNone
    """
    # YouTube Data API v3を実行したレスポンスから動画情報を取得
    response: requests.Response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "part": "snippet",
            "id": video_id,
            "key": get_parameter_value(YOUTUBE_API_KEY_PARAMETER_NAME),
        },
        timeout=10,
    )
    response.raise_for_status()
    items: List[Dict[str, Any]] | None = response.json().get("items")
    if items is None:
        raise ValueError("Video not found")
    snippet: Dict[str, Any] | None = items[0].get("snippet")
    if snippet is None:
        raise ValueError("snippet not found")

    # ライブ配信以外(none)、またはライブ配信予定(upcoming)の場合はNoneを返す
    live_broadcast_content: str | None = snippet.get("liveBroadcastContent")
    if live_broadcast_content is None:
        raise ValueError("liveBroadcastContent not found")

    # 現在ライブ配信中の場合はサムネイル画像URLを取得して返す
    # まれにサムネイル画像URLを取得できないこともあるため、その場合は空文字列を返す
    if live_broadcast_content == "live":
        thumbnails: Dict[str, Any] | None = snippet.get("thumbnails")
        if thumbnails:
            for quality in ["high", "medium", "default"]: # 高解像度のサムネイル画像URLを優先的に取得
                if quality in thumbnails and "url" in thumbnails[quality]:
                    return thumbnails[quality]["url"]
        return ""

    return None


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
    TODO: 技術スタック「1.3 データフロー」の6以降が未実装

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
            logger.error("HMAC verification failed: %s", verify_result)
            return {
                "statusCode": 400,
                "body": verify_result,
            }

        # プッシュ通知内容のXMLデータを解析
        video_data: Dict[str, str] = parse_websub_xml(event.get("body", ""))
        logger.info("video_data: %s", video_data)

        # YouTube Data API v3でライブ配信かを判定し、サムネイル画像URLを取得
        thumbnail_url: str | None = check_if_live_streaming(video_data["video_id"])
        if thumbnail_url is None:
            logger.info("Video is not a live stream: %s", video_data)
            return {
                "statusCode": 200,
                "body": "OK",
            }
        video_data["thumbnail_url"] = thumbnail_url
        logger.info("video_data: %s", video_data)

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

"""
AWS Systems Manager Parameter Store 関連のユーティリティ関数
"""
from typing import Dict
import boto3

# SSM クライアントのグローバル初期化
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
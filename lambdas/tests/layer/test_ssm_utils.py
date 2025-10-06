"""AWS Systems Manager Parameter Store用のユーティリティ関数のユニットテスト"""

from unittest.mock import patch

# pylint: disable=import-outside-toplevel,import-error


class TestGetParameterValue:
    """get_parameter_value関数のテスト"""

    def test_get_parameter_value_success(self):
        """パラメータ取得の成功テスト"""
        from ssm_utils import get_parameter_value

        with patch("ssm_utils.ssm_client") as mock_ssm_client:
            mock_ssm_client.get_parameter.return_value = {
                "Parameter": {"Value": "test_value"}
            }

            result = get_parameter_value("test_param")

            assert result == "test_value"
            mock_ssm_client.get_parameter.assert_called_once_with(
                Name="test_param", WithDecryption=True
            )

    def test_get_parameter_value_with_encryption(self):
        """暗号化パラメータ取得の成功テスト"""
        from ssm_utils import get_parameter_value

        with patch("ssm_utils.ssm_client") as mock_ssm_client:
            mock_ssm_client.get_parameter.return_value = {
                "Parameter": {"Value": "encrypted_test_value"}
            }

            result = get_parameter_value("encrypted_param")

            assert result == "encrypted_test_value"
            mock_ssm_client.get_parameter.assert_called_once_with(
                Name="encrypted_param", WithDecryption=True
            )

    def test_get_parameter_value_different_parameters(self):
        """異なるパラメータ名での取得テスト"""
        from ssm_utils import get_parameter_value

        with patch("ssm_utils.ssm_client") as mock_ssm_client:
            # 複数回の呼び出しで異なる値を返す
            mock_ssm_client.get_parameter.side_effect = [
                {"Parameter": {"Value": "value1"}},
                {"Parameter": {"Value": "value2"}},
            ]

            result1 = get_parameter_value("param1")
            result2 = get_parameter_value("param2")

            assert result1 == "value1"
            assert result2 == "value2"
            assert mock_ssm_client.get_parameter.call_count == 2

# Contribution Guide

## 開発ツール

本システムの開発には、以下のツールとテクノロジーを使用する:

- Python 3.12 (プログラミング言語)
- AWS SAM CLI (ローカルテストとデプロイ)
- pytest (ユニットテスト)
- pylint (コード静的解析)

## ローカル開発環境のセットアップ

1. 以下のツールを事前にインストールしておく:

   - [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
   - Git
   - Python 3.12

2. GitHub アカウントを用意して、このリポジトリをフォークし、ローカル環境にクローンする
3. Python 3.12 の仮想環境を作成する:

   ```bash
   python3.12 -m venv venv
   ```

4. Python 3.12 の仮想環境を有効化する:

   ```bash
   # Linux/macOSの場合
   source venv/bin/activate
   # Windowsの場合
   venv\Scripts\activate
   ```

5. Python の依存関係をインストールする:

   ```bash
   pip install -r requirements.txt
   ```

## 開発時の実装規則

コード品質と一貫性を確保するため、以下の実装規則に従う:

- ほとんどのインフラストラクチャは Infrastructure as Code (IaC) で管理し、手動構成は行わない。本システムでは、目的に応じて複数のテンプレートファイルを使用する:
  - **`cfn.yml` (CloudFormation テンプレート)**: CI/CD パイプラインの AWS リソースを定義
    - Amazon CloudWatch
      - CodeBuild 用ロググループ
    - Amazon S3
    - AWS CloudFormation
    - AWS CodeBuild
    - AWS CodePipeline
    - AWS Systems Manager Parameter Store
      - ライブ配信を購読するチャンネル ID
    - 上記 AWS リソースに必要な IAM ロール・IAM ポリシー
  - **`sam.yml` (SAM テンプレート)**: サーバーレスアプリケーションの実行環境の AWS リソースを定義
    - Amazon API Gateway
    - Amazon CloudWatch
      - Amazon API Gateway 用ロググループ
      - AWS Lambda 用ロググループ
    - Amazon DynamoDB
    - Amazon EventBridge
    - Amazon SNS
    - AWS Lambda
    - AWS Systems Manager Parameter Store
      - API Gateway の`ytlivemetadata-lambda-post-notify`/`ytlivemetadata-lambda-get-notify`エンドポイント
    - 上記 AWS リソースに必要な IAM ロール・IAM ポリシー
- CloudFormation テンプレート・SAM テンプレートでは、SecureString タイプ(安全な文字列)の SSM パラメーターがサポートされていないため、以下の機密情報は IaC で管理せず、AWS CLI で事前作成する。
  - YouTube Data API v3 の API キー
  - SMS 通知の送信先電話番号
- 初期セットアップのみ AWS CloudFormation を使用して手動でデプロイし、以下の AWS サービスを連携した CI/CD パイプラインを手動で構築する。この CI/CD パイプラインは、GitHub リポジトリの main ブランチへの commit をトリガーとして実行される。

  - **AWS CodeBuild**: `buildspec.yml`で定義したテスト・ビルド処理(依存関係解決、テスト実行、SAM パッケージング、S3 アップロード)
  - **AWS CloudFormation**: ビルドアーティファクト(`packaged.yaml`)を用いたサーバーレスアプリケーションのデプロイ

- AWS Lambda 関数の Python のユニットテストは lambdas/tests に実装し、stmt のカバレッジ率 80%以上をみたすようにして、コード品質を担保する。ユニットテストは、以下のコマンドで実行する。
  ```bash
  pytest --cov=lambdas --cov-report=term-missing --cov-fail-under=80 tests
  ```
- AWS Lambda 関数間で共通する処理は Lambda レイヤーとして lambdas/layer に実装し、コードの重複を避ける。
- AWS Lambda 関数は Python を用いてコーディングし、.pylintrc に記載した例外を除き、必ず Pylint の警告・エラーをすべて解消するように、コード品質を担保する。Pylint の静的解析は、以下のコマンドで実行する。
  ```bash
  pylint lambdas/**/*.py tests/**/*.py --disable=import-error
  ```

## コミット・プルリクエストのワークフロー

### セキュリティ上の制約事項

以下のパラメーターは AWS Systems Manager Parameter Store で安全に管理するため、リポジトリにコミットしないこと。

- API Gateway の`ytlivemetadata-lambda-post-notify`/`ytlivemetadata-lambda-get-notify`のエンドポイント
- Google PubSubHubbub Hub サブスクリプションの HMAC シークレット
- YouTube Data API v3 の API キー
- ライブ配信を購読するチャンネル ID
- SMS 通知の送信先電話番号

### プルリクエストの要件

プルリクエスト作成時は以下を満たすこと:

- [ ] 以下のコマンドを実行して、すべてのユニットテストが成功し、カバレッジを 80% 以上にする:
  ```bash
  pytest --cov=lambdas --cov-report=term-missing --cov-fail-under=80 tests
  ```
- [ ] 以下のコマンドを実行して、Pylint の警告・エラーをすべて解消する:
  ```bash
  pylint lambdas/**/*.py tests/**/*.py --disable=import-error
  ```
- [ ] ターゲットを main ブランチに設定している。

## Python の依存関係管理

本システムでは、セキュリティの脆弱性や新機能に対応するように定期的にパッケージのバージョンアップを自動的に提案する GitHub の機能である GitHub Dependabot を使用して、Python パッケージの依存関係を `requirements.txt` として管理する。
GitHub Dependabot は以下の実行方式に従い、`.github/dependabot.yaml`で管理する:

- **実行スケジュール**: 毎週火曜日 10:00 (Asia/Tokyo)
- **対象ファイル**: `requirements.txt`
- **更新方式**: プルリクエストによる自動提案
- **レビュー担当**: 指定されたリポジトリ管理者

# 技術スタック

## 1. 要件と概要

### 1.1 要件

YouTube でライブ配信を開始した直後に、そのライブ配信の開始を共有するための素材を SMS で通知する。

### 1.2 ソリューション概要

Google PubSubHubbub Hub を経由した WebSub の仕組みを利用して YouTube ライブ配信開始イベントを検知し、ライブ配信の情報(配信タイトル、動画 URL、サムネイル画像 URL)を SMS で通知するように AWS Lambda を実行するサーバーレスアプリケーションを構築する。このアプローチにより、手動操作なしでリアルタイムな通知を実現する。

### 1.3 データフロー

システム全体の処理フローは以下の通りである:

1. ユーザーが YouTube でライブ配信を開始する。
2. YouTube が事前に登録された Google PubSubHubbub Hub に RSS をプッシュ通知する。
3. Google PubSubHubbub Hub が Amazon API Gateway にプッシュ通知し、AWS Lambda 関数を起動する。
4. AWS Lambda 関数が Google PubSubHubbub Hub からのプッシュ通知から HMAC 署名を検証する。
5. AWS Lambda 関数がプッシュ通知内容のデータを解析して動画タイトル、動画 URL を取得する。
6. AWS Lambda 関数が YouTube Data API v3 を実行し、現在ライブ配信中の場合はサムネイル画像 URL を取得して処理を継続し、それ以外の場合は以降の動作を行わずに正常終了する。
7. AWS Lambda 関数が Amazon DynamoDB で処理済かを判定し、処理済の場合は以降の動作を行わずに正常終了する。
8. AWS Lambda 関数が Amazon SNS を使用して、ライブ配信の情報を SMS で通知する。
9. AWS Lambda 関数が処理結果を Amazon DynamoDB に記録する。

## 2. アーキテクチャ

### 2.1 使用サービス

#### AWS サービス

本システムでは、以下の AWS サービスを利用して、スケーラブルかつ耐障害性の高いアーキテクチャを構築する:

- Amazon API Gateway (Google PubSubHubbub Hub からの通知受信)
- Amazon CloudWatch (ログ・モニタリング)
- Amazon DynamoDB (配信状態管理)
- Amazon EventBridge (スケジュールタスク・自動更新)
- Amazon S3 (ビルドアーティファクトのストレージ)
- Amazon SNS (SMS 通知の送信)
- AWS CloudFormation (サーバーレスアプリケーションのデプロイ)
- AWS CodeBuild (コードビルド・テスト実行)
- AWS CodePipeline (CI/CD パイプライン管理)
- AWS IAM (権限管理)
- AWS Lambda (サーバーレスアプリケーションのロジック実装)
- AWS Systems Manager Parameter Store (パラメーター・シークレット管理)

#### 外部サービス

AWS 以外の外部サービスとも連携することにより、コア機能を実現する:

- GitHub (コードリポジトリ)
- YouTube Data API v3 (動画情報取得)

### 2.2 AWS リソース構成

以下の表は、本システムで使用する主要な AWS リソースとその役割を示している:

| AWS リソース名 (論理 ID)            | AWS サービス       | 概要                                                                                 |
| ----------------------------------- | ------------------ | ------------------------------------------------------------------------------------ |
| `ytlivemetadata-apig`               | Amazon API Gateway | WebSub での YouTube ライブ配信通知を受け取る API エンドポイント                      |
| `ytlivemetadata-build`              | AWS CodeBuild      | ビルドプロセスを管理するアプリケーション                                             |
| `ytlivemetadata-dynamodb`           | Amazon DynamoDB    | 処理済みの YouTube ライブ配信を記録するテーブル                                      |
| `ytlivemetadata-ebrule-websub`      | Amazon EventBridge | `ytlivemetadata-lambda-websub`を定期実行するルール                                   |
| `ytlivemetadata-lambda-get-notify`  | AWS Lambda         | WebSub サブスクリプション確認処理を行う Lambda 関数                                  |
| `ytlivemetadata-lambda-post-notify` | AWS Lambda         | WebSub での YouTube ライブ配信通知情報をもとに SMS で通知する Lambda 関数            |
| `ytlivemetadata-lambda-websub`      | AWS Lambda         | Google PubSubHubbub Hub のサブスクリプションを再登録する Lambda 関数                 |
| `ytlivemetadata-pipeline`           | AWS CodePipeline   | `ytlivemetadata-build`・`ytlivemetadata-stack-pipeline`を管理する CI/CD パイプライン |
| `ytlivemetadata-sns`                | Amazon SNS         | SMS 通知を送信するための SNS トピック                                                |
| (ユーザー指定)                      | Amazon S3          | CI/CD パイプラインのビルドアーティファクトを保存するバケット                         |
| `ytlivemetadata-stack-pipeline`     | AWS CloudFormation | CI/CD パイプラインの AWS リソースを管理するスタック                                  |
| `ytlivemetadata-stack-sam`          | AWS CloudFormation | サーバーレスアプリケーションの AWS リソースを管理するスタック                        |

### 2.3 AWS アーキテクチャー図

以下の図は、システム全体のアーキテクチャを示している:

![architecture.drawio](architecture.drawio.svg)

## 3. コア機能の実装詳細

### 3.1 YouTube ライブ配信検知

YouTube の新規ライブ配信を`ytlivemetadata-lambda-post-notify`が検知するために、[Google PubSubHubbub Hub](https://pubsubhubbub.appspot.com/) を経由した WebSub の仕組みを利用する。この仕組みにより、[YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) のポーリング遅延やポーリングによるクオーター超過を避け、リアルタイムにプッシュ通知を検知することができる。

本システムでは、以下を設定して Google PubSubHubbub Hub のサブスクリプションを登録する:

| 設定項目      | 値                                                                                                   |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| Callback URL  | API Gateway の`ytlivemetadata-lambda-post-notify`/`ytlivemetadata-lambda-get-notify`のエンドポイント |
| Topic URL     | `https://www.youtube.com/xml/feeds/videos.xml?channel_id={購読するチャンネル ID}`                    |
| Verify Type   | `Asynchronous`                                                                                       |
| Mode          | `Subscribe`                                                                                          |
| HMAC secret   | `ytlivemetadata-lambda-websub`で発行した HMAC シークレットの値                                       |
| Lease seconds | `828000`(10 日間)                                                                                    |

Google PubSubHubbub Hub がプッシュ通知したデータは、[XML 形式](https://developers.google.com/youtube/v3/guides/push_notifications?hl=ja)である。

### 3.2 SMS 通知の送信

Google PubSubHubbub Hub がプッシュ通知したデータ、および YouTube Data API v3 を実行して取得したデータをもとに、Amazon SNS を利用して以下のライブ配信の情報を別々に SMS 通知する:

- 配信タイトル
- 動画 URL (`https://www.youtube.com/watch?v={ビデオ ID}`)
- サムネイル画像 URL

SMS 通知の送信先電話番号は、AWS Systems Manager Parameter Store に安全に保管する。

### 3.3 重複 SMS 通知防止とデータ管理

SMS 通知の送信後、以下の属性をもつ Amazon DynamoDB の項目を`ytlivemetadata-dynamodb` に記録する:

| 属性名               | データ型 | 説明                                                |
| -------------------- | -------- | --------------------------------------------------- |
| `video_id`           | String   | ビデオ ID(パーティションキー)                       |
| `notified_timestamp` | Number   | 通知時刻(Unix timestamp 形式)                       |
| `is_notified`        | Boolean  | 通知済フラグ                                        |
| `title`              | String   | 配信タイトル                                        |
| `url`                | String   | 動画 URL                                            |
| `thumbnail_url`      | String   | サムネイル画像 URL                                  |
| `ttl`                | Number   | TTL(ストレージコスト最適化のため 30 日後に自動削除) |

この項目の記録により、同一の`video_id`に対する Strong Consistency を使用した YouTube ライブ配信の重複 SMS 通知を確実に防止する。

### 3.4 Google PubSubHubbub Hub サブスクリプション自動再登録

Google PubSubHubbub Hub に登録したサブスクリプションの最大有効期間は 10 日間である。サービスの継続的な運用を保証するため、有効期間が設けられている Google PubSubHubbub Hub サブスクリプションに対し、自動的に再登録する仕組みとして、以下のステップを採用する:

1. `ytlivemetadata-lambda-websub`を 7 日ごとに実行するように、`ytlivemetadata-ebrule-websub`を定義する。

   - 最大有効期限の 10 日間から余裕を持って更新する。

2. `ytlivemetadata-lambda-websub`実行時に HMAC シークレットを発行し、Google PubSubHubbub Hub のサブスクリプション登録時に設定する。
3. 発行した HMAC シークレットを AWS Systems Manager Parameter Store に保管する。

## 4. 開発・運用ガイドライン

### 4.1 開発ツール

本システムの開発には、以下のツールとテクノロジーを使用する:

- Python 3.12 (プログラミング言語)
- AWS SAM CLI (ローカルテストとデプロイ)
- pytest (ユニットテスト)
- pylint (コード静的解析)

### 4.2 依存関係管理

本システムでは、セキュリティの脆弱性や新機能に対応するように定期的にパッケージのバージョンアップを自動的に提案する GitHub の機能である GitHub Dependabot を使用して、Python パッケージの依存関係を `requirements.txt` として管理する。
GitHub Dependabot は以下の実行方式に従い、`.github/dependabot.yaml`で管理する:

- **実行スケジュール**: 毎週火曜日 10:00 (Asia/Tokyo)
- **対象ファイル**: `requirements.txt`
- **更新方式**: プルリクエストによる自動提案
- **レビュー担当**: 指定されたリポジトリ管理者

### 4.3 重要な制約事項

セキュリティとシステム信頼性を確保するため、以下のパラメーターは AWS Systems Manager Parameter Store で安全に管理し、リポジトリには保存しない。

- API Gateway の`ytlivemetadata-lambda-post-notify`/`ytlivemetadata-lambda-get-notify`のエンドポイント
- Google PubSubHubbub Hub サブスクリプションの HMAC シークレット
- YouTube Data API v3 の API キー
- ライブ配信を購読するチャンネル ID
- SMS 通知の送信先電話番号

### 4.4 開発時の実装規則

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

- AWS Lambda 関数の Python のコードは、必ず Python のユニットテストの stmt のカバレッジ率 80%以上をみたすようにして、コード品質を担保する。ユニットテストは、以下のコマンドで実行する。
  ```bash
  pytest --cov=lambdas --cov-report=term-missing --cov-fail-under=80 tests
  ```
- AWS Lambda 関数は Python を用いてコーディングし、`.pylintrc`に記載した例外を除き、必ず Pylint の警告・エラーをすべて解消するように、コード品質を担保する。Pylint の静的解析は、以下のコマンドで実行する。
  ```bash
  pylint lambdas/**/*.py tests/**/*.py
  ```

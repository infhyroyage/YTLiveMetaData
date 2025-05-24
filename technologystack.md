# 技術スタック

## 1. 要件と概要

### 1.1 要件

YouTube でライブ配信を開始した直後に、そのライブ配信の開始を共有するための素材を SMS で通知する。

### 1.2 ソリューション概要

Google PubSubHubbub Hub を経由した WebSub の仕組みを利用して YouTube ライブ配信開始イベントを検知し、ライブ配信の情報(サムネイル画像 URL、配信タイトル、動画 URL)を SMS で通知するように AWS Lambda を実行するサーバーレスアプリケーションを構築する。このアプローチにより、手動操作なしでリアルタイムな通知を実現する。

### 1.3 データフロー

システム全体の処理フローは以下の通りである:

1. ユーザーが YouTube でライブ配信を開始する。
2. YouTube が事前に登録された Google PubSubHubbub Hub に RSS を通知する。
3. Google PubSubHubbub Hub が Amazon API Gateway に通知し、AWS Lambda 関数を起動する。
4. AWS Lambda 関数が本当に Google PubSubHubbub Hub から通知したかを、HMAC シークレットを用いて検証する。
5. AWS Lambda 関数が通知内容の XML を解析してライブ配信かどうかを判定し、ライブ配信の場合はそのビデオ ID を取得する。
6. AWS Lambda 関数が Amazon DynamoDB で処理済みかチェック(重複通知防止)する。
7. AWS Lambda 関数が YouTube Data API v3 を実行し、ライブ配信の動画情報を取得する。
8. AWS Lambda 関数が Amazon SNS を使用して、ライブ配信情報(サムネイル画像 URL、配信タイトル、動画 URL)を SMS で通知する。
9. AWS Lambda 関数が処理結果を Amazon DynamoDB に記録する。

## 2. アーキテクチャと技術スタック

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

| AWS リソース名 (論理 ID)        | AWS サービス       | 概要                                                                                 |
| ------------------------------- | ------------------ | ------------------------------------------------------------------------------------ |
| `ytlivemetadata-apig`           | Amazon API Gateway | WebSub での YouTube ライブ配信通知を受け取る API エンドポイント                      |
| `ytlivemetadata-build`          | AWS CodeBuild      | ビルドプロセスを管理するアプリケーション                                             |
| `ytlivemetadata-dynamodb`       | Amazon DynamoDB    | 処理済みの YouTube ライブ配信を記録するテーブル                                      |
| `ytlivemetadata-ebrule-websub`  | Amazon EventBridge | `ytlivemetadata-lambda-websub`を定期実行するルール                                   |
| `ytlivemetadata-lambda-notify`  | AWS Lambda         | WebSub での YouTube ライブ配信通知情報をもとに SMS で通知する Lambda 関数            |
| `ytlivemetadata-lambda-websub`  | AWS Lambda         | Google PubSubHubbub Hub のサブスクリプションを再登録する Lambda 関数                 |
| `ytlivemetadata-pipeline`       | AWS CodePipeline   | `ytlivemetadata-build`・`ytlivemetadata-stack-pipeline`を管理する CI/CD パイプライン |
| `ytlivemetadata-sns`            | Amazon SNS         | SMS 通知を送信するための SNS トピック                                                |
| (ユーザー指定)                  | Amazon S3          | CI/CD パイプラインのビルドアーティファクトを保存するバケット                         |
| `ytlivemetadata-stack-pipeline` | AWS CloudFormation | CI/CD パイプラインの AWS リソースを管理するスタック                                  |
| `ytlivemetadata-stack-sam`      | AWS CloudFormation | サーバーレスアプリケーションの AWS リソースを管理するスタック                        |

### 2.3 AWS アーキテクチャー図

以下の図は、システム全体のアーキテクチャを示している:

![architecture.drawio](architecture.drawio.svg)

## 3. コア機能の実装詳細

### 3.1 YouTube ライブ配信検知

YouTube の新規ライブ配信を検知するために、Google PubSubHubbub Hub を経由した WebSub の仕組みを利用する。この仕組みにより、YouTube Data API v3 のポーリング遅延やクオーター超過を避け、リアルタイムな通知を受け取ることができる。

Google PubSubHubbub Hub では、以下のトピックを RSS でライブ配信を購読するようにサブスクリプションを登録する必要がある:

```
https://www.youtube.com/xml/feeds/videos.xml?channel_id={購読するチャンネル ID}
```

Google PubSubHubbub Hub のサブスクリプション登録時に、以下を設定する必要がある:

| 設定項目      | 値                                                                                |
| ------------- | --------------------------------------------------------------------------------- |
| Callback URL  | `ytlivemetadata-lambda-notify`の API Gateway のエンドポイント                     |
| Topic URL     | `https://www.youtube.com/xml/feeds/videos.xml?channel_id={購読するチャンネル ID}` |
| Verify Type   | `Asynchronous`                                                                    |
| Mode          | `Subscribe`                                                                       |
| HMAC secret   | `ytlivemetadata-lambda-websub`で発行した HMAC シークレットの値                    |
| Lease seconds | `828000`(10 日間)                                                                 |

### 3.2 SMS 通知の送信

YouTube Data API v3 を実行して取得した情報をもとに、Amazon SNS を利用して以下の内容を SMS で通知する:

- YouTube ライブ配信の配信タイトル
- YouTube ライブ配信の URL (`https://www.youtube.com/watch?v={ライブ配信のビデオ ID}`)
- YouTube ライブ配信のサムネイル画像 URL

SMS 通知の送信先電話番号は、AWS Systems Manager Parameter Store に安全に保管する。

### 3.3 Google PubSubHubbub Hub サブスクリプション自動再登録

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

### 4.2 重要な制約事項

セキュリティとシステム信頼性を確保するため、以下のパラメーターは AWS Systems Manager Parameter Store で安全に管理し、リポジトリには保存しない。

- API Gateway の`ytlivemetadata-lambda-notify`のエンドポイント
- Google PubSubHubbub Hub サブスクリプションの HMAC シークレット
- YouTube Data API v3 の API キー
- ライブ配信を購読するチャンネル ID
- SMS 通知の送信先電話番号

### 4.3 開発時の実装規則

コード品質と一貫性を確保するため、以下の実装規則に従う:

- インフラストラクチャは全て Infrastructure as Code (IaC) で管理し、手動構成は行わない。本システムでは、目的に応じて複数のテンプレートファイルを使用する:

  - **`cfn.yml` (CloudFormation テンプレート)**: CI/CD パイプラインの AWS リソースを定義

    - Amazon S3
    - AWS CloudFormation
    - AWS CodeBuild
    - AWS CodePipeline
    - AWS Systems Manager Parameter Store
      - YouTube Data API v3 の API キー
      - ライブ配信を購読するチャンネル ID
      - SMS 通知の送信先電話番号
    - 上記 AWS リソースに必要な IAM ロール・IAM ポリシー

  - **`sam.yml` (SAM テンプレート)**: サーバーレスアプリケーションの実行環境の AWS リソースを定義

    - Amazon API Gateway
    - Amazon CloudWatch
    - Amazon DynamoDB
    - Amazon EventBridge
    - Amazon SNS
    - AWS Lambda
    - AWS Systems Manager Parameter Store
      - API Gateway の`ytlivemetadata-lambda-notify`のエンドポイント
    - 上記 AWS リソースに必要な IAM ロール・IAM ポリシー

- 初期セットアップのみ AWS CloudFormation を使用して手動でデプロイし、以下の AWS サービスを連携した CI/CD パイプラインを手動で構築する。この CI/CD パイプラインは、GitHub リポジトリの main ブランチへの commit をトリガーとして実行される。

  - **AWS CodeBuild**: `buildspec.yml`で定義したテスト・ビルド処理(依存関係解決、テスト実行、SAM パッケージング、S3 アップロード)
  - **AWS CloudFormation**: ビルドアーティファクト(`packaged.yaml`)を用いたサーバーレスアプリケーションのデプロイ

- AWS Lambda 関数の Python のコードは、必ず Python のユニットテストの stmt のカバレッジ率 80%以上をみたすようにして、コード品質を担保する。ユニットテストは、以下のコマンドで実行する。
  ```bash
  pytest --cov=lambda --cov-report=term-missing --cov-fail-under=80 lambda/tests
  ```
- AWS Lambda 関数は Python を用いてコーディングし、`.pylintrc`に記載した例外を除き、必ず Pylint の警告・エラーをすべて解消するように、コード品質を担保する。Pylint の静的解析は、以下のコマンドで実行する。
  ```bash
  pylint lambda/**/*.py
  ```

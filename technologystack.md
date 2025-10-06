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
- AWS CloudFormation (スタック管理)
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
| `ytlivemetadata-dynamodb`           | Amazon DynamoDB    | 処理済みの YouTube ライブ配信を記録するデータベース                                  |
| `ytlivemetadata-ebrule-websub`      | Amazon EventBridge | `ytlivemetadata-lambda-websub`を定期実行するルール                                   |
| `ytlivemetadata-lambda-get-notify`  | AWS Lambda         | WebSub サブスクリプション確認処理を行う Lambda 関数                                  |
| `ytlivemetadata-lambda-post-notify` | AWS Lambda         | WebSub での YouTube ライブ配信通知情報をもとに SMS で通知する Lambda 関数            |
| `ytlivemetadata-lambda-websub`      | AWS Lambda         | Google PubSubHubbub Hub のサブスクリプションを再登録する Lambda 関数                 |
| `ytlivemetadata-pipeline`           | AWS CodePipeline   | `ytlivemetadata-build`・`ytlivemetadata-stack-pipeline`を管理する CI/CD パイプライン |
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

Google PubSubHubbub Hub がプッシュ通知したデータ、および YouTube Data API v3 を実行して取得したデータをもとに、Amazon SNS を利用して、以下のライブ配信の情報を SMS に通知する:

- 配信タイトル
- 動画 URL (`https://www.youtube.com/watch?v={ビデオ ID}`)
- サムネイル画像 URL(取得できない場合は本文に含めない)

SMS でのメッセージ本文は、 以下の通り 1 通のメッセージで構成される:

```
{配信タイトル}

https://www.youtube.com/watch?v={ビデオ ID}

{サムネイル画像 URL}
```

Amazon SNS では、通知成功・失敗の状態や通知先電話番号などを含む配信ログを、以下の Amazon CloudWatch ロググループに記録する。

- 成功配信ログ: `/sns/{リージョン}/{AWSアカウントID}/DirectPublishToPhoneNumber`
- 失敗配信ログ: `/sns/{リージョン}/{AWSアカウントID}/DirectPublishToPhoneNumber/Failure`

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

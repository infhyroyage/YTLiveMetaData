# 初期セットアップ構築手順・削除手順

## 構築手順

### 1. 必要な前提条件の準備

1. AWS アカウントを用意する
2. 当リポジトリで使用する S3 バケット名を 1 つ決定する
3. AWS CLI を[インストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)し、ap-northeast-1 リージョンでプロファイルを設定する
4. [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)をインストールする
5. GitHub アカウントを用意して、このリポジトリをフォークし、ローカル環境にクローンする
6. 以下を設定した GitHub [Personal Access Token](https://github.com/settings/personal-access-tokens)を作成する
   - Repository access: Only select repositories(フォークしたリポジトリのみを選択)
   - Repository permissions:
     - Contents: Read-only
     - Metadata: Read-only

### 2. YouTube Data API v3 の認証情報の取得

1. [Google Cloud Console](https://console.cloud.google.com/)にログインする
2. 新しいプロジェクトを作成する
3. 作成したプロジェクトに対し、YouTube Data API v3 を有効化する
4. 作成したプロジェクトに対し、[OAuth 同意画面](https://console.cloud.google.com/apis/credentials/consent)で以下の項目を入力して、OAuth の構成を作成する。
   - アプリ名: 任意の名前
   - ユーザーサポートメール: 有効なメールアドレス
   - デベロッパーの連絡先情報: 有効なメールアドレス
5. 作成したプロジェクトに対し、認証情報ページで YouTube Data API v3 のみ許可を与えた API キーを新しく作成し、手元に控える

### 3. 機密情報の SSM パラメータ作成

機密情報(YouTube Data API v3 の API キー・SMS 通知先の電話番号)を、 AWS Systems Manager Parameter Store に保存する:

```bash
aws ssm put-parameter \
  --name "/ytlivemetadata/youtube_api_key" \
  --value "{YouTube Data API v3のAPIキー}" \
  --type "SecureString" \
  --description "API Key for YouTube Data API v3"
aws ssm put-parameter \
  --name "/ytlivemetadata/phone_number" \
  --value "{SMS通知先の電話番号(国際形式)}" \
  --type "SecureString" \
  --description "Phone Number for SMS Notifications"
```

> [!IMPORTANT]  
> SMS 通知先の電話番号は、国際形式(E.164 形式)で入力する。例えば、日本の場合は、以下のように国コード `+81` + 最初の `0` を除いた電話番号(ハイフンなし)を入力する。
>
> - 携帯電話 080-9876-5432 → `+818098765432`
> - 固定電話 03-1234-5678 → `+81312345678`

### 4. SNS SMS サンドボックスでの電話番号検証

> [!IMPORTANT]  
> この手順は、SMS 通知を受信する電話番号ごとに実行する必要がある。検証を行わないと、Lambda 関数`ytlivemetadata-lambda-post-notify`が成功しても、SMS 通知が送信されない。

1. [Amazon SNS コンソール](https://console.aws.amazon.com/sns/home)にログインする
2. リージョンが ap-northeast-1 (東京) に設定されていることを確認する
3. 左側のナビゲーションペインで **テキストメッセージング (SMS)** を選択する
4. **サンドボックスの送信先電話番号** セクションで **電話番号を追加** ボタンを押下する
5. 以下の情報を入力して **電話番号を追加** ボタンを押下する：
   - **電話番号**: **3. 機密情報の SSM パラメータ作成** で入力した、SMS 通知先の電話番号(国際形式)
   - **検証メッセージの言語**: **日本語 (日本)**
6. 入力した電話番号に OTP(ワンタイムパスコード)が SMS で送信される
7. 受信した OTP を **検証コード** ボックスに入力し、**電話番号を検証** ボタンを押下する
8. 検証ステータスが **検証済み** になることを確認する

### 5. CI/CD 用 CloudFormation テンプレートのデプロイ

リポジトリのルートディレクトリに移動して、以下のコマンドを実行し、CI/CD パイプライン用 CloudFormation スタックをデプロイする:

```bash
aws cloudformation deploy \
  --template-file templates/cfn.yml \
  --stack-name ytlivemetadata-stack-pipeline \
  --parameter-overrides \
    ArtifactS3BucketName="{決定したS3バケット名}" \
    GitHubOwnerName="{GitHubユーザー名}" \
    GitHubPAT="{作成したGitHubパーソナルアクセストークン}" \
    GitHubRepositoryName="{フォークしたリポジトリ名}" \
    YouTubeChannelId="{監視対象のYouTubeチャンネルID}" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```

> [!NOTE]  
> このデプロイ完了直後に、CI/CD パイプラインである CodePipeline(`ytlivemetadata-stack-pipeline`) が自動実行し、SAM テンプレートによるサーバーレスアプリケーションの実行環境用 CloudFormation スタックのデプロイも自動実行する。この実行状況は、AWS マネジメントコンソールの CloudFormation のスタックから確認できる。

### 6. SNS の SMS 配信ログの有効化

以下のコマンドを実行して、CloudWatch ロググループへの SNS の SMS 配信ログ設定を有効化する:

```bash
aws sns set-sms-attributes \
  --attributes \
    DeliveryStatusIAMRole=arn:aws:iam::{AWSアカウントID}:role/ytlivemetadata-role-sns-cloudwatch-logs,DeliveryStatusSuccessSamplingRate=100
```

### 7. Google PubSubHubbub Hub の初期設定

以下のコマンドを実行し、Lambda 関数`ytlivemetadata-lambda-websub`を手動実行して、Google PubSubHubbub Hub に登録する:

```bash
aws lambda invoke --function-name ytlivemetadata-lambda-websub response.json
```

## 削除手順

1. SNS の SMS 配信ログの設定を無効化する:

   ```bash
   aws sns set-sms-attributes \
     --attributes \
       'DeliveryStatusLogging=false'
   ```

2. SAM テンプレートでデプロイしたスタックを削除する:

   ```bash
   aws cloudformation delete-stack --stack-name ytlivemetadata-stack-sam
   ```

3. SNS SMS サンドボックスから検証済み電話番号を削除する:

   1. [Amazon SNS コンソール](https://console.aws.amazon.com/sns/home)にログインする
   2. リージョンが ap-northeast-1 (東京) に設定されていることを確認する
   3. 左側のナビゲーションペインで **Text messaging (SMS)** を選択する
   4. **Sandbox destination phone numbers** セクションで削除したい電話番号を選択する
   5. **Delete phone number** を選択して削除する

   > [!NOTE]  
   > 検証済み電話番号は、検証から 24 時間経過後に削除可能になる。

4. Amazon S3 バケット内のすべてのオブジェクトを削除する:

   ```bash
   aws s3 rm s3://{決定したS3バケット名} --recursive
   ```

5. CloudFormation テンプレートでデプロイしたスタックを削除する:

   ```bash
   aws cloudformation delete-stack --stack-name ytlivemetadata-stack-pipeline
   ```

6. 機密情報(YouTube Data API v3 の API キー・SMS 通知先の電話番号)の SSM パラメータを削除する:

   ```bash
   aws ssm delete-parameter --name "/ytlivemetadata/youtube_api_key"
   aws ssm delete-parameter --name "/ytlivemetadata/phone_number"
   ```

7. [Google Cloud Console](https://console.cloud.google.com/)にアクセスし、作成したプロジェクトを削除する

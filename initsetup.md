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

### 3. CI/CD 用 CloudFormation テンプレートのデプロイ

リポジトリのルートディレクトリに移動して、以下のコマンドを実行し、CI/CD パイプライン用 CloudFormation スタックをデプロイする:

```bash
aws cloudformation deploy \
  --template-file templates/cfn.yml \
  --stack-name ytlivemetadata-stack-pipeline \
  --parameter-overrides \
    ArtifactS3BucketName={決定したS3バケット名} \
    GitHubOwnerName={GitHubユーザー名} \
    GitHubPAT={作成したGitHubパーソナルアクセストークン} \
    GitHubRepositoryName={フォークしたリポジトリ名} \
    YouTubeApiKey={YouTube Data API v3のAPIキー} \
    YouTubeChannelId={監視対象のYouTubeチャンネルID} \
    SmsPhoneNumber={SMS通知先の電話番号(国際形式)} \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```

### 4. SAM テンプレートのデプロイ

リポジトリのルートディレクトリに移動して、以下のコマンドを実行し、SAM テンプレートを手動デプロイする:

```bash
sam build --template templates/sam.yml
sam deploy --stack-name ytlivemetadata-stack-sam --capabilities CAPABILITY_IAM
```

### 5. Google PubSubHubbub Hub の初期設定

Google PubSubHubbub Hub 登録のための Lambda 関数を実行する:

```bash
aws lambda invoke \
  --function-name ytlivemetadata-lambda-websub \
  --region ap-northeast-1
```

## 削除手順

1. Amazon S3 バケット内のすべてのオブジェクトを削除する:

   ```bash
   aws s3 rm s3://{決定したS3バケット名} --recursive
   ```

2. SAM テンプレートでデプロイしたスタックを削除する:

   ```bash
   aws cloudformation delete-stack --stack-name ytlivemetadata-stack-sam
   ```

3. CloudFormation テンプレートでデプロイしたスタックを削除する:

   ```bash
   aws cloudformation delete-stack --stack-name ytlivemetadata-stack-pipeline
   ```

4. [Google Cloud Console](https://console.cloud.google.com/)にアクセスし、作成したプロジェクトを削除する

# AGENTS.md

## Cursor Cloud specific instructions

### プロダクト概要

**YTLiveMetaData** は AWS サーバーレス（Lambda / API Gateway / DynamoDB / SNS）で、YouTube ライブ開始を WebSub 経由で検知し SMS 通知するシステムです。ローカルに常駐する Web アプリはなく、開発は **pytest / pylint / `sam build`** が中心です。

### 前提（初回 VM のみ）

Ubuntu では `python3.12 -m venv` に **`python3.12-venv`** が必要です（未導入時は `sudo apt-get install -y python3.12-venv`）。

### 仮想環境と依存関係

```bash
cd /workspace
python3.12 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

以降のセッションでは `source venv/bin/activate` を先に実行してください。

### 必須環境変数（テスト・import 時）

`lambdas/layer/python/ssm_utils.py` が import 時に `boto3.client("ssm")` を作るため、**リージョン未設定だと全テストが `NoRegionError` で失敗**します。

```bash
export AWS_DEFAULT_REGION=ap-northeast-1
```

CI（`templates/buildspec.yml`）と同様に、テスト前に次も設定します（`pytest.ini` の `pythonpath` で layer は解決されます）。

```bash
export PYTHONPATH="lambdas/layer/python:$PYTHONPATH"
```

### Lint

```bash
source venv/bin/activate
pylint lambdas/**/*.py
```

### テスト（カバレッジ 80% 以上必須）

```bash
source venv/bin/activate
export AWS_DEFAULT_REGION=ap-northeast-1
export PYTHONPATH="lambdas/layer/python:$PYTHONPATH"
pytest --cov=lambdas --cov-report=term-missing --cov-fail-under=80 lambdas/tests
```

詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照。

### ビルド（SAM）

`buildspec.yml` と同様、各 Lambda ディレクトリへ `requirements.txt` をコピーしてからビルドします（コピー先は **git 管理外**の作業用ファイル）。

```bash
source venv/bin/activate
cp requirements.txt lambdas/get_notify/requirements.txt
cp requirements.txt lambdas/post_notify/requirements.txt
cp requirements.txt lambdas/websub/requirements.txt
cp requirements.txt lambdas/post_pipeline/requirements.txt
cp requirements.txt lambdas/layer/requirements.txt
sam build --template templates/sam.yml
```

成果物は `.aws-sam/build`（`.gitignore` 対象）。

### `sam local invoke` について

`sam local invoke` は **Docker（または Finch）** が必要です。Cloud Agent VM にコンテナランタイムがない場合は、**モック付きで `lambda_handler` を Python から直接呼ぶ**か、上記 pytest でコアロジックを検証してください。本番 E2E は AWS デプロイ後（[awssetup.md](awssetup.md)）が必要です。

### ローカルでコア動作を確認する例（WebSub 検証 GET）

Docker なしで `get_notify` のハンドラを動かす最小例（SSM はモック）:

```bash
source venv/bin/activate
export AWS_DEFAULT_REGION=ap-northeast-1
export WEBSUB_HMAC_SECRET_PARAMETER_NAME=/ytlivemetadata/websub_hmac_secret
export YOUTUBE_CHANNEL_ID_PARAMETER_NAME=/ytlivemetadata/youtube_channel_id
# Python から unittest.mock.patch で get_parameter_value を差し替えて lambda_handler を呼ぶ
```

### 注意

- **AWS 認証情報・SSM の実値**がないと、デプロイ済みスタックへの実 E2E（YouTube ライブ → SMS）はできません。
- `sam package` / デプロイには S3 アーティファクトバケットと AWS クレデンシャルが必要です（[awssetup.md](awssetup.md)）。

# Duty Allocation

グループ内で当番やタスクを公平に割り当てるための Web システムです。現在は最小構成で、FastAPI、PostgreSQL、素の HTML/CSS/JS のフロントエンドを Docker Compose で起動します。

## 必要なもの

対応環境は Ubuntu / Debian、または WSL 上の Ubuntu です。

```bash
sudo apt update
sudo apt install -y git make curl unzip wget
curl -LsSf https://astral.sh/uv/install.sh | sh

# E2E テストの Chrome に必要なシステムライブラリをまとめてインストールします
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

Docker:

- **Ubuntu / Debian:** [Docker Engine](https://docs.docker.com/engine/install/) を Compose プラグインと一緒にインストールします。
- **WSL:** Windows に [Docker Desktop](https://docs.docker.com/desktop/features/wsl/) をインストールし、使用する Ubuntu ディストリビューションの WSL 統合を有効にします。

Linux のシェルで `docker compose version` が動くことを確認してください。

### WSL での注意点

- リポジトリは `/mnt/c/...` ではなく、`~/projects/duty-allocation` のように Linux 側にクローンしてください。
- Git for Windows ではなく、WSL 内の Git を使ってください。

## はじめかた

```bash
make setup
make up
```

<http://localhost:8000> を開き、サンプルユーザーの Alice と Bob が表示されれば成功です。ログはこのターミナルに流れ続け、Ctrl+C でアプリが停止します。

## コマンド

| コマンド | 内容 |
|---|---|
| `make setup` | ローカルの Python 環境を準備し、Chrome をダウンロードします |
| `make chrome` | Chrome と ChromeDriver の最新版を `downloads/` にダウンロードします（バージョン指定: `make chrome VERSION=142.0.7444.59`） |
| `make up` | アプリをビルドして起動し、ログを表示します |
| `make down` | コンテナを停止して削除します（データベースのデータは残ります） |
| `make test` | Docker 内でユニットテストを実行します |
| `make e2e` | ローカルで Selenium テストを実行します（別のターミナルで `make up` が必要です） |
| `make reset` | **データベースのデータをすべて削除し**、`db/init.sql` から作り直してアプリを起動します |

`make test` は、データベースが起動していなければ起動します。アプリを起動していない場合は、終わったあとに `make down` で停止してください。

## 変更するとき

- **スキーマ:** `db/init.sql` を編集して `make reset` を実行します。このスクリプトはデータベースが空のときだけ実行されます。これは一時的な方法で、チームでスキーマ変更を共有し始める前に Alembic のマイグレーションへ移行します。
- **依存パッケージ:** `uv add <パッケージ名>` を実行し、`pyproject.toml` と `uv.lock` をコミットしてから、`make up` で再ビルドします。
- **パスワード:** `docker-compose.yml` にあるデータベースのパスワードは開発用です。LINE のトークンなどの本物の秘密情報は絶対にコミットしないでください。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `backend/app/` | FastAPI アプリとビジネスロジック |
| `backend/tests/` | ユニットテスト（Docker 内で実行） |
| `frontend/` | FastAPI が配信する静的ページ |
| `db/init.sql` | スキーマの草案とサンプルデータ |
| `e2e/` | Selenium テスト（Docker の外で実行） |

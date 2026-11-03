# Duty Allocation

グループ内で当番やタスクを公平に割り当てるための Web システムです。現在は最小構成で、FastAPI、PostgreSQL、素の HTML/CSS/JS のフロントエンドを Docker Compose で起動します。

## 必要なもの

対応環境は Ubuntu / Debian、または WSL 上の Ubuntu です。

```bash
sudo apt update
sudo apt install -y git make curl unzip wget
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Docker:

- **Ubuntu / Debian:** [Docker Engine](https://docs.docker.com/engine/install/) を Compose プラグインと一緒にインストールします。
- **WSL:** Windows に [Docker Desktop](https://docs.docker.com/desktop/features/wsl/) をインストールし、使用する Ubuntu ディストリビューションの WSL 統合を有効にします。
  - Docker Desktop の **Settings > Resources > WSL integration** を開き、「Configure which WSL 2 distros you want to access Docker from.」の下にある **Enable integration with my default WSL distro** をオンにします。既定以外のディストリビューションを使う場合は、その下の一覧で該当するディストリビューションもオンにして、**Apply** を押してください。
  - `make up`、`make test`、`make reset` を実行する前に、Windows 側で Docker Desktop を起動しておいてください。起動していないと、WSL から `docker` コマンドが見つからない、または Docker に接続できないというエラーになります。

Linux のシェルで `docker compose version` が動くことを確認してください。

### WSL での注意点

- Windows の VS Code と Git for Windows で、そのまま作業できます。改行コードはリポジトリ側の設定（`.gitattributes`、`.vscode/settings.json`）で LF に揃えているので、各自の Git の設定を変える必要はありません。
- `make` などのコマンドは WSL のターミナルで実行します。Windows 側（例: `C:\projects\duty-allocation`）にクローンした場合は、WSL から `/mnt/c/projects/duty-allocation` に移動して実行してください。
- Windows 側のフォルダーは WSL から読み書きすると遅いため、`make setup` や `make up` に時間がかかることがあります。速さが気になる場合は、`~/projects/duty-allocation` のように Linux 側にクローンし、VS Code の [WSL 拡張機能](https://code.visualstudio.com/docs/remote/wsl)で開いてください。

## はじめかた

```bash
make setup
make up
```

<http://localhost:8000> を開き、サンプルユーザーの Alice と Bob が表示されれば成功です。ログはこのターミナルに流れ続け、Ctrl+C でアプリが停止します。

### E2E テスト用のシステムライブラリ

`make setup`（`make chrome`）は Chrome と ChromeDriver を `downloads/` にダウンロードしますが、それらが使う共有ライブラリ（`libnss3`、`libnspr4`、`libasound2`、GTK など）は OS 側に必要です。WSL や最小構成の Ubuntu には入っていないことが多いので、`make setup` のあとに一度だけ、Chrome が同梱しているパッケージ一覧から apt でインストールしてください。

```bash
sudo apt-get satisfy -y --no-install-recommends "$(paste -sd, downloads/chrome-linux64/deb.deps)"
```

Chrome のバージョンを上げて必要なライブラリが増えた場合も、同じコマンドを実行してください。

ライブラリが足りないと、`make e2e` が次のエラーで失敗します。

```
WebDriverException: Message: Service .../chromedriver unexpectedly exited. Status code was: 127
```

足りないライブラリは次のコマンドで確認できます。

```bash
ldd downloads/chromedriver-linux64/chromedriver downloads/chrome-linux64/chrome | grep "not found"
```

## コマンド

| コマンド | 内容 |
|---|---|
| `make setup` | ローカルの Python 環境を準備し、Chrome をダウンロードします |
| `make chrome` | Chrome と ChromeDriver の最新版を `downloads/` にダウンロードします（バージョン指定: `make chrome VERSION=142.0.7444.59`） |
| `make up` | アプリをビルドして起動し、ログを表示します |
| `make down` | コンテナを停止して削除します（データベースのデータは残ります） |
| `make test` | Docker 内でユニットテストを実行します |
| `make e2e` | ローカルで Selenium テストを実行します（別のターミナルで `make up` が必要です）。`make e2e V=1` で Chrome のウィンドウを表示し、テスト名を一覧表示します |
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

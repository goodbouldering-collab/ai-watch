# CLAUDE.md — AIハブ

**AIハブ** は「自分のAIをひとつに集める場所」をテーマにした個人ポートフォリオ兼マイページ。
作品（アプリ集）・講師紹介・講習資料を見せる**フロント面**と、AI/SNS関連情報をRSSから自動収集・要約してNotebookLMに流し込む**バックエンドのパイプライン**を1つのサイトに同居させている。

## リポジトリ名の正規化

- プロジェクト名: **AIハブ / AI Hub**（旧称: AI-watch、AI情報収集、cclimb-intel、ai-info）
- GitHub: `goodbouldering-collab/ai-hub`
- Render service: `ai-hub`（静的サイト、Singapore、`main` push で自動デプロイ）
- GitHub Pages: `https://goodbouldering-collab.github.io/ai-hub/`
- Supabase: 既存の共有プロジェクト `zrawhzwtppmlxyhngnju` の `public.ai_watch_*` 相乗り（テーブル名は履歴互換のため `ai_watch_` プレフィックスを維持）

新規で文言を書くときは「AIハブ」に揃える。過去ログ（`outputs/notebooklm/*`）と Supabase テーブル名は改名しない（NotebookLM 側のソース参照と既存データ互換のため）。

## ディレクトリ

| パス | 役割 |
|---|---|
| `run.py` | エントリーポイント。収集→要約→出力→サイト生成まで一気通貫 |
| `core/` | 収集・差分・要約・ランキング・サムネ・書き出し |
| `config/sources.yaml` | 収集対象 RSS。追加するだけで増やせる |
| `config/genres.yaml` | ジャンル（AI業務活用 / SNSアルゴリズム 等）の定義 |
| `config/support_sns.yaml` | サポートSNSアカウントリスト |
| `config/portfolio.yaml` | トップに並べる作品カードの定義 |
| `config/top_buttons.yaml` | トップ上部のクイックリンクボタン |
| `site/build_site.py` | `outputs/top10.json` から静的 HTML を生成 |
| `site/dist/` | 生成物（GitHub Pages / Render が公開） |
| `outputs/notebooklm/` | NotebookLM 用 Markdown/TXT（日次） |
| `outputs/full/` | 週次フル版 TXT |
| `data/history.db` | SQLite の既取得ログ（差分検出の土台） |
| `admin/server.py` | FastAPI 管理画面（ローカル 3010）。Shopify Admin API 操作タブも内蔵 |
| `core/shopify_admin.py` | Shopify Admin REST クライアント。`.env` の `SHOPIFY_ACCESS_TOKEN` / `SHOPIFY_STORE_DOMAIN` を読む |
| `scripts/migrate_sqlite_to_supabase.py` | SQLite → Supabase へのマイグレーション |
| `content/speaker.md` | 講師紹介（由井辰美）の編集ソース。ビルドで `speaker.html` になる |
| `content/lectures/*.md` | 講習資料の編集ソース。ビルドで `lectures/<slug>.html` になる |
| `content/assets/` | 画像・PDF。`./assets/xxx` で参照 |

## デプロイ構成

- **GitHub Actions `daily.yml`**: JST 07:00 に `run.py` を実行し、`outputs/` と `data/history.db` を main に commit back
- **GitHub Actions `pages.yml`**: `main` への push で `site/build_site.py` を叩いて GitHub Pages に配布
- **Render (`render.yaml`)**: `main` push で `pip install` → `build_site.py` → `site/dist/` を静的配信
- **Supabase**: `ai_watch_articles` テーブルに差分保存（`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` が env にあれば書き込む）

### Render プラン運用（Static Site = keepalive 不要）

このサービスは **Render Static Site** として配信している。Static Site は Web Service と異なり**スリープしないため keepalive は不要**。Free プランのまま帯域・ビルド枚数の制約内で運用可能。

将来 Web Service（FastAPI 管理画面の本番公開など）に切り替える場合は、親 CLAUDE.md「Render プラン運用ルール」に従い Free + keepalive で開始する。

## コマンド

```bash
python run.py                 # 日次ダイジェスト (直近24h の diff モード)
python run.py --full          # 週次フル版も生成
python run.py --no-summary    # Claude API をスキップ
python site/build_site.py     # サイトだけ再ビルド
uvicorn admin.server:app --port 3010 --reload   # 管理画面
```

VSCode で `clients.code-workspace` を開けば「AIハブ起動」タスクで `http://localhost:3010/admin` が立ち上がる。

## 守るべきルール

- ソース追加は `config/sources.yaml` に 1 ブロック足すだけ。コードは触らない
- 作品カードを増やすときは `config/portfolio.yaml` に1ブロック追加。コードは触らない
- RSS 以外（X API・スクレイピング等）を増やすときは `core/collector.py` の `DISPATCH` に関数を追加する
- 日付入りの出力ファイルは上書きしない（NotebookLM 側がソースとして保持しているため）
- `data/history.db` は commit back される前提。`.gitignore` で除外しない
- 文字化け防止: グッぼる本店など EUC-JP ソースを HTML で取り込む場合は親 `CLAUDE.md` のルールに従って `iconv` 変換層を挟む
- Supabase テーブル名 `ai_watch_*` は**改名しない**（旧名のまま運用継続）

## 管理画面について

`admin/server.py` は FastAPI ベースの**ローカル専用**管理 UI。
GitHub Pages / Render (static) は静的ホスティングなので、公開ナビから `/admin` リンクは外してある。
ローカルで触るときは `uvicorn admin.server:app --port 3010 --reload` を起動して `http://localhost:3010/admin` にアクセスする。
運用（記事収集の実行）は基本 GitHub Actions 任せで、管理画面は手元確認用。

### 講習資料タブ

`/admin` の「📝 講習資料」タブで `content/lectures/*.md` を一覧・新規作成・編集・削除できる。

**操作**:
- 左カラム: 既存資料一覧（日付の新しい順）
- 右カラム: frontmatter (title/date/role/gen_by/summary) と Markdown 本文のエディタ
- **slug** はファイル名（例: `2026-04-ai-kihon`）。小文字英数とハイフンのみ
- 「💾 保存して再ビルド」で `/lectures/<slug>.html` に即反映

**追加機能**:
- **Markdownライブプレビュー**（右半分に即時描画、入力から400ms後に更新）
- **画像/PDFアップロード** → `content/assets/` に保存して本文の現在カーソル位置に Markdown を自動挿入。許容拡張子: png/jpg/jpeg/gif/webp/svg/pdf、最大10MB、同名は連番で自動回避
- **複製して新規** ボタン: 現在の編集内容をテンプレに新規モード化（slugだけ空に）

**API**:
- `GET /api/lectures` 一覧
- `GET /api/lectures/{slug}` 取得
- `POST /api/lectures` 新規（同名があれば 409）
- `PUT /api/lectures/{slug}` 更新
- `DELETE /api/lectures/{slug}` 削除
- `POST /api/lectures/preview` Markdown→HTML プレビュー
- `GET /api/assets` アセット一覧
- `POST /api/assets` アセットアップロード (multipart)
- `DELETE /api/assets/{name}` アセット削除

### Shopify Admin タブ

`/admin` の「🛒 Shopify」タブで、`.env` に登録した Shopify ストアを直接操作できる。

**前提**: `.env` に以下を設定（`.env.example` 参照）。
```
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_STORE_DOMAIN=84c617.myshopify.com
```

**機能**:
- 接続確認（ストア名・通貨・プラン表示）
- 商品一覧（タイトル絞り込み・在庫数つき）
- 注文一覧（status フィルタ）
- 顧客検索（メール・名前・電話）
- 在庫拠点（Location）一覧

**重要**: 本番ストアに直接書き込めるトークンを使うので、`.env` は絶対にコミットしない（`.gitignore` で除外済）。書き込み系（在庫更新等）はAPI実装済だがUI上はまだ読み取りに徹している。書き込み操作を増やす場合は確認モーダルを必ず挟む方針。

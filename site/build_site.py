"""
outputs/top10.json を読み取り、静的 HTML サイトを生成する。
- ジャンルでグループ化
- 各グループ内に小タブ (全部 / 記事 / 動画) でメディア絞り込み
- 全カードにサムネイル
- クリックを localStorage + Gist へ送信（好み学習用）
"""
from __future__ import annotations
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

SITE_URL = os.environ.get("AIHUB_SITE_URL", os.environ.get("AIWATCH_SITE_URL", "https://goodbouldering-collab.github.io/ai-hub")).rstrip("/")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
TOP10_JSON = ROOT / "outputs" / "top10.json"
ARCHIVE_DIR = ROOT / "outputs" / "archive"
GENRES_YAML = ROOT / "config" / "genres.yaml"
SUPPORT_SNS_YAML = ROOT / "config" / "support_sns.yaml"
TOP_BUTTONS_YAML = ROOT / "config" / "top_buttons.yaml"
DIST = ROOT / "site" / "dist"
STATIC = ROOT / "site" / "static"

SNS_META = [
    ("youtube",         "🎥", "YouTube"),
    ("x",               "🐦", "X (Twitter)"),
    ("instagram_feed",  "📷", "Instagram Feed"),
    ("instagram_reel",  "🎬", "Instagram Reel"),
    ("instagram_story", "⭕", "Instagram Story"),
    ("threads",         "🧵", "Threads"),
    ("facebook",        "📘", "Facebook"),
]

URL_RE = re.compile(r"https?://\S+")


def clean_summary(s: str) -> str:
    s = URL_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" 　、。,")
    return s


def load_genres() -> list[dict]:
    if not GENRES_YAML.exists():
        return []
    data = yaml.safe_load(GENRES_YAML.read_text(encoding="utf-8"))
    return data.get("genres", [])


DEFAULT_TOP_BUTTONS = [
    {"id": "speaker",         "label": "講師紹介",           "icon": "🎤", "href": "./speaker.html",            "kind": "link",   "enabled": True},
    {"id": "portfolio",       "label": "実績",               "icon": "🏆", "href": "./portfolio.html",          "kind": "link",   "enabled": True},
    {"id": "lectures",        "label": "講習資料",           "icon": "📝", "href": "./lectures/index.html",     "kind": "link",   "enabled": True},
    {"id": "archive",         "label": "過去ログ",           "icon": "📚", "href": "./archive.html",            "kind": "link",   "enabled": True},
    {"id": "programming_map", "label": "プログラミングマップ", "icon": "📘", "href": "./programming-map.html",    "kind": "link",   "enabled": True},
    {"id": "run",             "label": "巡回実行",           "icon": "🔄", "href": "",                          "kind": "action", "action_id": "run", "enabled": True},
]


def load_top_buttons() -> list[dict]:
    if not TOP_BUTTONS_YAML.exists():
        return DEFAULT_TOP_BUTTONS
    try:
        data = yaml.safe_load(TOP_BUTTONS_YAML.read_text(encoding="utf-8")) or {}
        items = data.get("top_buttons") or []
        if not items:
            return DEFAULT_TOP_BUTTONS
        return items
    except Exception:
        return DEFAULT_TOP_BUTTONS


def render_top_nav(include_run: bool = True) -> str:
    """トップページのナビを config/top_buttons.yaml から生成。"""
    buttons = load_top_buttons()
    parts: list[str] = ["<nav>"]
    has_run = False
    for b in buttons:
        if not b.get("enabled", True):
            continue
        label = html.escape(str(b.get("label", "")))
        icon = html.escape(str(b.get("icon", "")))
        kind = b.get("kind", "link")
        text = f"{icon} {label}".strip()
        if kind == "action":
            action_id = b.get("action_id") or b.get("id") or "run"
            if action_id == "run":
                if not include_run:
                    continue
                has_run = True
                parts.append(f"<button type='button' id='run-btn' class='run-btn'>{text}</button>")
        else:
            href = html.escape(str(b.get("href", "")), quote=True)
            if not href:
                continue
            extra = " data-localhost-only='1' style='display:none'" if b.get("localhost_only") else ""
            parts.append(f"<a href='{href}'{extra}>{text}</a> ")
    if has_run:
        parts.append("<span id='run-status' class='run-status'></span>")
    parts.append("</nav>")
    return "".join(parts)


def load_support_sns() -> dict:
    if not SUPPORT_SNS_YAML.exists():
        return {k: [] for k, _, _ in SNS_META}
    data = yaml.safe_load(SUPPORT_SNS_YAML.read_text(encoding="utf-8")) or {}
    sns = data.get("support_sns") or {}
    return {k: sns.get(k, []) or [] for k, _, _ in SNS_META}


SUPPORT_SNS_LATEST_JSON = ROOT / "outputs" / "support_sns" / "latest.json"


def _hash_str(s: str) -> str:
    import hashlib
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


def load_support_sns_items() -> list[dict]:
    """outputs/support_sns/latest.json を読み、各アカウントの最新1件を Top10 と同じ形に整える。"""
    if not SUPPORT_SNS_LATEST_JSON.exists():
        return []
    try:
        data = json.loads(SUPPORT_SNS_LATEST_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []

    from urllib.parse import unquote
    result: list[dict] = []
    platforms = data.get("platforms", {})
    for plat_key, icon, label in SNS_META:
        entries = platforms.get(plat_key, [])
        for entry in entries:
            items = entry.get("items") or []
            if not items:
                continue
            latest = items[0]
            acc = entry.get("account", {})
            url = latest.get("url", "")
            title = latest.get("title", "") or f"{acc.get('name','')} - 最新"
            display_handle = unquote(acc.get("handle") or acc.get("name", ""))
            source_name = f"{icon} {display_handle}"
            result.append({
                "hash": _hash_str(f"sns:{plat_key}:{url}"),
                "title": title,
                "orig_title": title,
                "summary": f"{label}の最新投稿",
                "url": url,
                "source": source_name,
                "category": "サポートSNS",
                "genre": "support_sns",
                "score": 0,
                "thumbnail": latest.get("thumbnail", ""),
                "published": latest.get("published", ""),
            })
    return result


def render_support_sns_section(sns: dict) -> str:
    total = sum(len(sns.get(k, [])) for k, _, _ in SNS_META)
    if total == 0:
        return (
            "<section class='support-sns'>"
            "<h2>📡 サポートSNS</h2>"
            "<p class='empty'>まだ登録がありません。管理画面 (http://localhost:4001/) から追加できます。</p>"
            "</section>"
        )
    parts = ["<section class='support-sns'><h2>📡 サポートSNS</h2><div class='sns-grid'>"]
    for key, icon, label in SNS_META:
        items = sns.get(key, [])
        if not items:
            continue
        parts.append(
            f"<div class='sns-card'><div class='sns-head'>{icon} {label} "
            f"<span class='sns-count'>{len(items)}</span></div><ul class='sns-list'>"
        )
        for it in items:
            name = html.escape(it.get("name", ""))
            handle = html.escape(it.get("handle", ""))
            url = it.get("url", "")
            note = html.escape(it.get("note", ""))
            handle_html = f" <span class='sns-handle'>{handle}</span>" if handle else ""
            note_html = f"<div class='sns-note'>{note}</div>" if note else ""
            if url:
                safe_url = html.escape(url, quote=True)
                parts.append(
                    f"<li><a href='{safe_url}' target='_blank' rel='noopener'>{name}</a>"
                    f"{handle_html}{note_html}</li>"
                )
            else:
                parts.append(f"<li><span>{name}</span>{handle_html}{note_html}</li>")
        parts.append("</ul></div>")
    parts.append("</div></section>")
    return "".join(parts)


def is_video(item: dict) -> bool:
    url = item.get("url", "")
    return "youtube.com/watch" in url or "youtu.be/" in url


# top_buttons の中で `localhost_only: true` のリンクは
# サーバ生成HTMLでは display:none で出力 → 本スクリプトが localhost 系ホストのときだけ
# display を inline に戻す。本番 (GitHub Pages) では訪問者に一切見えない。
ADMIN_BUTTON_HTML = """
<script>
(function(){
  function reveal(){
    var h = location.hostname;
    if (h !== "localhost" && h !== "127.0.0.1" && h !== "0.0.0.0" && !h.endsWith(".localhost")) return;
    document.querySelectorAll("[data-localhost-only]").forEach(function(el){
      el.style.display = "";
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reveal);
  } else {
    reveal();
  }
})();
</script>
"""


CSS = """
:root {
  --text:#f2f4fb;
  --muted:#aab1c5;
  --glass-bg:rgba(255,255,255,0.06);
  --glass-border:rgba(255,255,255,0.14);
  --glass-hover:rgba(255,255,255,0.10);
  --accent1:#7aa2ff;
  --accent2:#c77dff;
  --accent3:#ff7ab6;
}
* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body {
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans","Noto Sans JP",sans-serif;
  color:var(--text);
  line-height:1.7;
  min-height:100vh;
  background:
    radial-gradient(1200px 800px at 15% -10%, rgba(122,162,255,.35), transparent 60%),
    radial-gradient(900px 700px at 85% 10%, rgba(199,125,255,.28), transparent 60%),
    radial-gradient(1000px 800px at 50% 110%, rgba(255,122,182,.22), transparent 60%),
    linear-gradient(180deg, #0a0d1a 0%, #0d1126 50%, #0a0d1a 100%);
  background-attachment: fixed;
  -webkit-font-smoothing: antialiased;
}
.container { position:relative; z-index:1; max-width: 920px; margin: 0 auto; padding: 48px 20px 80px; }

header { margin-bottom:32px; }
header h1 {
  margin:0 0 8px;
  font-size:clamp(28px, 5vw, 42px);
  font-weight:800;
  background: linear-gradient(100deg, var(--accent1) 0%, var(--accent2) 45%, var(--accent3) 100%);
  -webkit-background-clip:text;
  background-clip:text;
  color:transparent;
  filter: drop-shadow(0 2px 20px rgba(122,162,255,.25));
  background-size: 200% 100%;
  animation: shimmer 6s ease-in-out infinite;
}
@keyframes shimmer {
  0%,100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
header .sub { margin:0; color:var(--muted); font-size:13px; letter-spacing:.04em; }

nav { margin-top:16px; display:flex; gap:10px; flex-wrap:wrap; }
nav a {
  padding:8px 16px; border-radius:999px;
  background:var(--glass-bg); border:1px solid var(--glass-border);
  backdrop-filter: blur(14px) saturate(160%);
  color:var(--text); text-decoration:none; font-size:13px;
  transition: all .25s ease;
}
nav a:hover { background:var(--glass-hover); transform: translateY(-1px); }
.run-btn {
  font: inherit;
  padding:8px 16px; border-radius:999px;
  background: linear-gradient(135deg, rgba(122,162,255,.35), rgba(199,125,255,.35));
  border:1px solid rgba(255,255,255,.22);
  color:var(--text); cursor:pointer; font-size:13px; font-weight:700;
  backdrop-filter: blur(14px) saturate(160%);
  transition: all .25s ease;
}
.run-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(122,162,255,.55), rgba(199,125,255,.55));
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(122,162,255,.25);
}
.run-btn:disabled { opacity:.6; cursor:not-allowed; }
.run-status { margin-left:10px; font-size:12px; color:var(--muted); }
.run-status.ok { color:#7eeba3; }
.run-status.err { color:#ff7a90; }
.run-status.running { color:#ffd36b; }

.genre-tabs {
  display:flex; flex-wrap:wrap; gap:8px;
  margin:24px 0 28px; padding:10px;
  background:var(--glass-bg); border:1px solid var(--glass-border);
  border-radius:16px;
  backdrop-filter: blur(16px) saturate(160%);
}
.genre-tab {
  font: inherit;
  padding:8px 14px; border-radius:999px;
  background:transparent; border:1px solid transparent;
  color:var(--muted); cursor:pointer; font-size:13px; font-weight:600;
  transition: all .25s ease;
  display:inline-flex; align-items:center; gap:6px;
}
.genre-tab:hover { color:var(--text); background:rgba(255,255,255,.05); }
.genre-tab.active {
  background: linear-gradient(135deg, rgba(122,162,255,.3), rgba(199,125,255,.3));
  color:var(--text); border-color: rgba(255,255,255,.2);
  box-shadow: 0 4px 16px rgba(122,162,255,.25);
}

.group { margin-top:36px; }
.group-head {
  display:flex; align-items:center; justify-content:space-between;
  margin-bottom:14px; padding:14px 20px;
  background: linear-gradient(135deg, rgba(122,162,255,.12), rgba(199,125,255,.08));
  border:1px solid var(--glass-border); border-radius:16px;
  backdrop-filter: blur(16px);
}
.group-label {
  font-size:17px; font-weight:800;
  background: linear-gradient(100deg, var(--accent1), var(--accent2));
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.group-count {
  font-size:11px; color:var(--muted);
  padding:4px 10px; border-radius:999px;
  background:rgba(255,255,255,.06); border:1px solid var(--glass-border);
}

.sub-tabs {
  display:flex; gap:6px; margin:0 0 12px 4px;
}
.sub-tab {
  font: inherit;
  padding:4px 12px; border-radius:999px;
  background:transparent; border:1px solid rgba(255,255,255,.12);
  color:var(--muted); cursor:pointer; font-size:11px; font-weight:600;
  transition: all .2s ease;
}
.sub-tab:hover { color:var(--text); }
.sub-tab.active {
  background: rgba(122,162,255,.2); color:var(--text);
  border-color: rgba(122,162,255,.4);
}

article {
  position:relative;
  display:flex; gap:16px;
  background:var(--glass-bg); border:1px solid var(--glass-border);
  border-radius:18px; padding:16px;
  margin-bottom:12px;
  backdrop-filter: blur(18px) saturate(160%);
  box-shadow: 0 8px 32px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.08);
  transition: transform .3s ease, background .3s ease, box-shadow .3s ease;
  cursor:pointer;
  text-decoration:none; color:inherit;
  overflow:hidden;
}
article:hover {
  transform: translateY(-3px);
  background:var(--glass-hover);
  box-shadow: 0 16px 48px rgba(122,162,255,.18);
}
.thumb {
  flex-shrink:0;
  width:140px; height:88px;
  border-radius:12px;
  background:rgba(255,255,255,.04) center/cover;
  border:1px solid var(--glass-border);
  position:relative;
  overflow:hidden;
}
.thumb.placeholder {
  display:flex; align-items:center; justify-content:center;
  font-size:28px; opacity:.4;
  background: linear-gradient(135deg, rgba(122,162,255,.15), rgba(199,125,255,.15));
}
.thumb .play {
  position:absolute; inset:0;
  display:flex; align-items:center; justify-content:center;
  font-size:32px; color:#fff;
  text-shadow: 0 2px 12px rgba(0,0,0,.6);
}
.body {
  flex:1; min-width:0;
  display:flex; flex-direction:column; gap:6px;
}
.meta {
  display:flex; align-items:center; gap:8px;
  font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em;
}
.meta .rank {
  padding:2px 8px; border-radius:6px;
  background: linear-gradient(135deg, var(--accent1), var(--accent2));
  color:#fff; font-weight:800;
}
.meta .score { opacity:.7; }
article h3 {
  margin:0; font-size:15px; font-weight:700;
  line-height:1.5; color:var(--text);
}
article p {
  margin:0; font-size:12.5px; color:#c5cbdd;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
  overflow:hidden;
}
.src {
  font-size:10px; color:var(--muted);
  display:flex; align-items:center; gap:6px;
}

.empty {
  color:var(--muted); font-size:14px;
  padding:40px 20px; text-align:center;
  background:var(--glass-bg); border:1px solid var(--glass-border);
  border-radius:16px;
}

footer {
  margin-top:64px; padding-top:20px;
  color:var(--muted); font-size:11px; text-align:center;
  letter-spacing:.1em; text-transform:uppercase; opacity:.6;
}

.support-sns { margin-top: 48px; }
.support-sns > h2 {
  font-size: 18px; font-weight: 800; margin-bottom: 14px;
  background: linear-gradient(100deg, var(--accent1), var(--accent3));
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.support-sns .empty {
  color:var(--muted); font-size:13px;
  padding:20px; text-align:center;
  background:var(--glass-bg); border:1px solid var(--glass-border);
  border-radius:14px;
}
.sns-grid {
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap:14px;
}
.sns-card {
  background:var(--glass-bg); border:1px solid var(--glass-border);
  border-radius:14px; padding:14px 16px;
  backdrop-filter: blur(14px);
}
.sns-head {
  font-size:13px; font-weight:700; color:var(--text);
  margin-bottom:8px; display:flex; align-items:center; gap:8px;
}
.sns-count {
  font-size:10px; color:var(--muted);
  padding:2px 8px; border-radius:999px;
  background:rgba(255,255,255,.06); border:1px solid var(--glass-border);
}
.sns-list { list-style:none; margin:0; padding:0; }
.sns-list li {
  padding:6px 0; border-top:1px solid rgba(255,255,255,.06);
  font-size:12px; color:var(--text);
}
.sns-list li:first-child { border-top:none; }
.sns-list a { color:var(--accent1); text-decoration:none; }
.sns-list a:hover { text-decoration:underline; }
.sns-handle { color:var(--muted); font-size:11px; margin-left:4px; }
.sns-note { color:var(--muted); font-size:10px; margin-top:2px; }

@media (max-width: 640px) {
  .container { padding: 32px 14px 60px; }
  article { flex-direction:column; }
  .thumb { width:100%; height:180px; }
}
"""


def render_index(payload: dict, genres: list[dict]) -> str:
    date = payload.get("date", "")
    items = list(payload.get("items", []))

    sns_items = load_support_sns_items()
    items.extend(sns_items)
    total = len(items)

    for it in items:
        it["_is_video"] = is_video(it)
        it["_summary_clean"] = clean_summary(it.get("summary", "")) or ""

    genre_order = [g["key"] for g in genres] + ["support_sns"]
    genre_label = {g["key"]: f"{g.get('icon','')} {g['label']}" for g in genres}
    genre_label["support_sns"] = "📡 サポートSNS"

    genre_counts: dict[str, int] = {}
    for it in items:
        genre_counts[it["genre"]] = genre_counts.get(it["genre"], 0) + 1

    parts: list[str] = []
    parts.append("<!doctype html><html lang='ja'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    parts.append(f"<title>AIハブ Top{total} / {date}</title>")
    desc = f"AI情報とSNSアルゴリズム動向を毎朝要約・ランキング。{date} のTop{total}を掲載。"
    parts.append(f"<meta name='description' content='{html.escape(desc, quote=True)}'>")
    parts.append(f"<link rel='canonical' href='{html.escape(SITE_URL + '/index.html', quote=True)}'>")
    parts.append(_build_ogp("AIハブ", desc, SITE_URL + "/index.html", kind="website"))
    ld = _build_jsonld("website", {}, "AIハブ", SITE_URL + "/index.html")
    if ld:
        parts.append(f"<script type='application/ld+json'>{ld}</script>")
    parts.append(f"<style>{CSS}</style></head><body><div class='container'>")
    parts.append(ADMIN_BUTTON_HTML)
    parts.append("<header>")
    parts.append("<h1>AIハブ</h1>")
    parts.append(f"<p class='sub'>{date} ・ 今日の注目Top{total} ・ クリックで好みを学習</p>")
    parts.append(render_top_nav(include_run=True))
    parts.append("</header>")

    if not items:
        parts.append("<p class='empty'>今日の記事はありません。</p>")
        parts.append(render_support_sns_section(load_support_sns()))
        parts.append("<footer>AIハブ</footer></div></body></html>")
        return "".join(parts)

    parts.append("<div class='genre-tabs'>")
    parts.append(f"<button class='genre-tab active' data-genre='all'>🌐 すべて ({total})</button>")
    for key in genre_order:
        c = genre_counts.get(key, 0)
        if c == 0:
            continue
        parts.append(f"<button class='genre-tab' data-genre='{html.escape(key)}'>{html.escape(genre_label.get(key, key))} ({c})</button>")
    parts.append("</div>")

    rank_map = {it["hash"]: i + 1 for i, it in enumerate(items)}

    for key in genre_order:
        g_items = [it for it in items if it["genre"] == key]
        if not g_items:
            continue
        label = genre_label.get(key, key)
        has_article = any(not it["_is_video"] for it in g_items)
        has_video = any(it["_is_video"] for it in g_items)

        parts.append(f"<section class='group' data-genre='{html.escape(key)}'>")
        parts.append("<div class='group-head'>")
        parts.append(f"<span class='group-label'>{html.escape(label)}</span>")
        parts.append(f"<span class='group-count'>{len(g_items)}件</span>")
        parts.append("</div>")

        if has_article and has_video:
            parts.append("<div class='sub-tabs'>")
            parts.append("<button class='sub-tab active' data-sub='all'>すべて</button>")
            parts.append("<button class='sub-tab' data-sub='article'>📄 記事</button>")
            parts.append("<button class='sub-tab' data-sub='video'>📺 動画</button>")
            parts.append("</div>")

        for it in g_items:
            rank = rank_map[it["hash"]]
            sub_kind = "video" if it["_is_video"] else "article"
            title = html.escape(it["title"])
            summary = html.escape(it["_summary_clean"]) or "<span style='color:#777'>（要約なし）</span>"
            url = html.escape(it["url"])
            source = html.escape(it["source"])
            score = it.get("score", 0)
            thumb = html.escape(it.get("thumbnail", ""))
            hash_ = html.escape(it["hash"])
            genre_key = html.escape(it["genre"])

            if thumb:
                thumb_html = f"<div class='thumb' style='background-image:url(\"{thumb}\")'>" + ("<div class='play'>▶</div>" if it["_is_video"] else "") + "</div>"
            else:
                thumb_html = "<div class='thumb placeholder'>📄</div>" if not it["_is_video"] else "<div class='thumb placeholder'>📺</div>"

            parts.append(
                f"<article data-sub='{sub_kind}' data-hash='{hash_}' "
                f"data-genre='{genre_key}' data-source='{source}' "
                f"onclick=\"trackClick(this, '{url}')\">"
            )
            parts.append(thumb_html)
            parts.append("<div class='body'>")
            parts.append("<div class='meta'>")
            parts.append(f"<span class='rank'>#{rank}</span>")
            parts.append(f"<span class='score'>score {score:.0f}</span>")
            parts.append(f"<span>{source}</span>")
            parts.append("</div>")
            parts.append(f"<h3>{title}</h3>")
            parts.append(f"<p>{summary}</p>")
            parts.append("</div>")
            parts.append("</article>")

        parts.append("</section>")

    parts.append(render_support_sns_section(load_support_sns()))
    parts.append("<footer>AIハブ / Generated by Claude</footer>")
    parts.append("</div>")

    parts.append("""<script>
const LS_KEY = 'ai_intel_clicks_v1';
const GIST_ENDPOINT = window.AI_INTEL_GIST_ENDPOINT || '';

function loadClicks() {
  try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; }
  catch(e) { return []; }
}
function saveClicks(arr) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(arr.slice(-500))); }
  catch(e) {}
}

function trackClick(el, url) {
  const rec = {
    hash: el.dataset.hash,
    genre: el.dataset.genre,
    source: el.dataset.source,
    ts: new Date().toISOString(),
  };
  const all = loadClicks();
  all.push(rec);
  saveClicks(all);

  if (GIST_ENDPOINT) {
    try {
      navigator.sendBeacon(GIST_ENDPOINT, JSON.stringify(rec));
    } catch(e) {}
  }
  window.open(url, '_blank', 'noopener');
}

(function(){
  const gtabs = document.querySelectorAll('.genre-tab');
  const groups = document.querySelectorAll('.group');
  gtabs.forEach(t => t.addEventListener('click', () => {
    gtabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    const g = t.dataset.genre;
    groups.forEach(sec => {
      sec.style.display = (g === 'all' || sec.dataset.genre === g) ? '' : 'none';
    });
  }));

  document.querySelectorAll('.group').forEach(sec => {
    const subs = sec.querySelectorAll('.sub-tab');
    const cards = sec.querySelectorAll('article');
    subs.forEach(t => t.addEventListener('click', (e) => {
      e.stopPropagation();
      subs.forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      const s = t.dataset.sub;
      cards.forEach(c => {
        c.style.display = (s === 'all' || c.dataset.sub === s) ? '' : 'none';
      });
    }));
  });
})();

(function(){
  const btn = document.getElementById('run-btn');
  const status = document.getElementById('run-status');
  if (!btn) return;

  function setStatus(text, cls) {
    status.textContent = text;
    status.className = 'run-status' + (cls ? ' ' + cls : '');
  }

  async function poll() {
    try {
      const r = await fetch('/api/run/status');
      const s = await r.json();
      if (s.running) {
        setStatus('巡回中...', 'running');
        btn.disabled = true;
        setTimeout(poll, 3000);
      } else {
        btn.disabled = false;
        if (s.last_status === 'ok') {
          setStatus('完了 — 3秒後にリロード', 'ok');
          setTimeout(() => location.reload(), 3000);
        } else if (s.last_status === 'error') {
          setStatus('エラー（コンソール確認）', 'err');
          console.error(s.last_log);
        }
      }
    } catch(e) {
      setStatus('通信エラー（サーバー起動中？）', 'err');
      btn.disabled = false;
    }
  }

  btn.addEventListener('click', async () => {
    if (!confirm('巡回を開始しますか？（数分かかることがあります）')) return;
    btn.disabled = true;
    setStatus('開始中...', 'running');
    try {
      const r = await fetch('/api/run', { method: 'POST' });
      const j = await r.json();
      if (!j.ok) { setStatus(j.message || '開始失敗', 'err'); btn.disabled = false; return; }
      poll();
    } catch(e) {
      setStatus('通信エラー（FastAPI経由で開いていますか？）', 'err');
      btn.disabled = false;
    }
  });

  // 起動時に一度だけ状態確認（実行中ならポーリング再開）
  fetch('/api/run/status').then(r => r.json()).then(s => {
    if (s.running) { btn.disabled = true; setStatus('巡回中...', 'running'); poll(); }
  }).catch(() => {});
})();
</script>""")
    parts.append("</body></html>")
    return "".join(parts)


def render_archive(dates: list[str]) -> str:
    parts: list[str] = []
    parts.append("<!doctype html><html lang='ja'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    parts.append("<title>AIハブ — 過去ログ</title>")
    parts.append(f"<style>{CSS}</style></head><body><div class='container'>")
    parts.append(ADMIN_BUTTON_HTML)
    parts.append("<header>")
    parts.append("<h1>過去ログ</h1>")
    parts.append(f"<p class='sub'>アーカイブ {len(dates)}件</p>")
    parts.append("<nav><a href='./index.html'>📰 最新に戻る</a> <a href='./speaker.html'>🎤 講師紹介</a> <a href='./portfolio.html'>🏆 実績</a> <a href='./lectures/index.html'>📝 講習資料</a> <a href='./programming-map.html'>📘 プログラミングマップ</a> <a href='/admin' data-localhost-only='1' style='display:none'>⚙️ 管理</a></nav>")
    parts.append("</header>")
    if dates:
        parts.append("<ul style='list-style:none;padding:0;margin:0'>")
        for d in dates:
            parts.append(
                f"<li style='margin-bottom:10px;background:var(--glass-bg);"
                f"border:1px solid var(--glass-border);border-radius:14px;"
                f"backdrop-filter:blur(14px)'>"
                f"<a href='./{d}.html' style='display:block;padding:16px 20px;"
                f"color:var(--text);text-decoration:none'>{d}</a></li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p class='empty'>アーカイブはまだありません。</p>")
    parts.append("<footer>AIハブ</footer></div></body></html>")
    return "".join(parts)


CONTENT_DIR = ROOT / "content"
SPEAKER_MD = CONTENT_DIR / "speaker.md"
LECTURES_DIR = CONTENT_DIR / "lectures"
PORTFOLIO_YAML = ROOT / "config" / "portfolio.yaml"

CONTENT_CSS = """
.content-wrap {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
  padding: 28px clamp(18px, 4vw, 40px);
  backdrop-filter: blur(18px) saturate(160%);
  box-shadow: 0 8px 32px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.08);
  color: var(--text);
  line-height: 1.85;
}
.content-wrap h1,
.content-wrap h2,
.content-wrap h3 {
  color: var(--text);
  font-weight: 800;
  line-height: 1.35;
  margin: 1.6em 0 .5em;
}
.content-wrap h1 {
  font-size: clamp(24px, 4vw, 34px);
  background: linear-gradient(100deg, var(--accent1), var(--accent2), var(--accent3));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 2px 18px rgba(122,162,255,.22));
}
.content-wrap h2 {
  font-size: 20px;
  padding: 10px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(122,162,255,.12), rgba(199,125,255,.08));
  border: 1px solid var(--glass-border);
  background-clip: padding-box;
}
.content-wrap h3 { font-size: 15px; color: var(--accent1); letter-spacing: .02em; }
.content-wrap p { margin: .6em 0; color: #d3d8ea; font-size: 14.5px; }
.content-wrap ul,
.content-wrap ol { margin: .4em 0 1em 1.3em; padding: 0; color: #d3d8ea; font-size: 14.5px; }
.content-wrap li { margin: .2em 0; }
.content-wrap a { color: var(--accent1); text-decoration: none; border-bottom: 1px dashed rgba(122,162,255,.35); transition: color .2s; }
.content-wrap a:hover { color: var(--accent3); border-bottom-color: rgba(255,122,182,.55); }
.content-wrap blockquote {
  margin: 1em 0;
  padding: 10px 16px;
  border-left: 3px solid var(--accent2);
  background: rgba(255,255,255,.04);
  border-radius: 0 12px 12px 0;
  color: var(--muted);
  font-size: 13.5px;
}
.content-wrap code {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  background: rgba(255,255,255,.08);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: .9em;
  color: #ffd4ea;
}
.content-wrap strong { color: var(--text); }
.speaker-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--muted);
}
.speaker-meta .role {
  padding: 3px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(122,162,255,.3), rgba(199,125,255,.3));
  color: var(--text);
  font-weight: 700;
}
.content-toc {
  background: rgba(255,255,255,.03);
  border: 1px solid var(--glass-border);
  border-radius: 14px;
  padding: 14px 20px;
  margin: 0 0 22px;
}
.content-toc .toc-label {
  font-size: 12px;
  color: var(--accent1);
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.content-toc ol {
  margin: 0;
  padding-left: 1.3em;
  columns: 2;
  column-gap: 28px;
  font-size: 13.5px;
}
.content-toc ol li { margin: 2px 0; break-inside: avoid; }
.content-toc a {
  color: #d3d8ea;
  text-decoration: none;
  border-bottom: 1px dashed transparent;
}
.content-toc a:hover { color: var(--accent3); border-bottom-color: rgba(255,122,182,.55); }
@media (max-width: 640px) {
  .content-toc ol { columns: 1; }
}
.content-wrap h2[id],
.content-wrap h3[id] { scroll-margin-top: 20px; }
.back-to-top {
  position: fixed;
  right: 18px;
  bottom: 22px;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent1), var(--accent2));
  color: #0b1020;
  font-weight: 800;
  font-size: 20px;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(0,0,0,.35);
  cursor: pointer;
  border: none;
  z-index: 50;
}
.back-to-top.show { display: flex; }

/* ---- Portfolio ---- */
.pf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
  margin: 16px 0 8px;
}
.pf-card {
  display: flex;
  flex-direction: column;
  background: rgba(255,255,255,.04);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 14px 16px 12px;
  transition: transform .15s, border-color .15s, box-shadow .15s;
  text-decoration: none;
  color: inherit;
  min-height: 150px;
}
.pf-card:hover {
  transform: translateY(-2px);
  border-color: rgba(122,162,255,.45);
  box-shadow: 0 10px 26px rgba(8,12,30,.45);
}
.pf-card .pf-title {
  font-weight: 800;
  font-size: 15px;
  color: var(--text);
  background: linear-gradient(100deg, var(--accent1), var(--accent3));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.pf-card .pf-host {
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 2px;
  word-break: break-all;
}
.pf-card .pf-sum {
  font-size: 13px;
  color: #d3d8ea;
  line-height: 1.55;
  margin: 8px 0 10px;
  flex: 1;
}
.pf-card .pf-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11px;
}
.pf-card .pf-chip {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(122,162,255,.14);
  color: #c7d2ff;
  border: 1px solid rgba(122,162,255,.25);
}
.pf-card .pf-chip.cat {
  background: rgba(255,122,182,.14);
  color: #ffd4ea;
  border-color: rgba(255,122,182,.3);
}
.pf-card .pf-chip.retired { background: rgba(120,120,120,.2); color: #aaa; }
.pf-card .pf-chip.dev { background: rgba(250,204,21,.15); color: #fde68a; border-color: rgba(250,204,21,.35); }
.pf-section-title {
  font-size: 13px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--accent1);
  margin: 22px 0 4px;
  font-weight: 700;
}
.pf-note {
  font-size: 12px;
  color: var(--muted);
  margin-top: 18px;
  padding: 10px 14px;
  border-left: 3px solid var(--accent2);
  background: rgba(255,255,255,.03);
  border-radius: 0 10px 10px 0;
}
"""


def _load_markdown():
    import importlib
    return importlib.import_module("markdown")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    try:
        end = text.index("\n---", 3)
    except ValueError:
        return {}, text
    fm_raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        meta = yaml.safe_load(fm_raw) or {}
    except Exception:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), body


_HEADING_ID_RE = re.compile(r"<h2>([^<]+)</h2>")
_SLUG_NON_ALNUM = re.compile(r"[^0-9A-Za-z぀-ヿ一-鿿\-]+")


def _build_jsonld(kind: str, meta: dict, title: str, page_url: str) -> str:
    """BlogPosting / Person / WebSite の JSON-LD を生成。"""
    if kind == "lecture":
        doc = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "datePublished": str(meta.get("date") or datetime.now().strftime("%Y-%m-%d")),
            "mainEntityOfPage": { "@type": "WebPage", "@id": page_url },
            "author": { "@type": "Person", "name": "由井 辰美" },
            "publisher": {
                "@type": "Organization",
                "name": "AIハブ",
                "url": SITE_URL,
            },
            "description": str(meta.get("summary") or title),
            "speakable": {
                "@type": "SpeakableSpecification",
                "cssSelector": ["h1", ".content-wrap p:first-of-type"],
            },
        }
        return json.dumps(doc, ensure_ascii=False)
    if kind == "speaker":
        doc = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": title,
            "jobTitle": str(meta.get("role") or "AI講師"),
            "url": page_url,
            "sameAs": [str(meta.get("profile_url"))] if meta.get("profile_url") else [],
        }
        return json.dumps(doc, ensure_ascii=False)
    if kind == "website":
        doc = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "AIハブ",
            "url": SITE_URL,
            "description": "AI情報とSNSアルゴリズム動向を毎朝要約して届ける静的サイト",
        }
        return json.dumps(doc, ensure_ascii=False)
    return ""


def _build_ogp(title: str, description: str, page_url: str, kind: str = "article") -> str:
    desc = description or title
    return "".join([
        f"<meta property='og:title' content='{html.escape(title, quote=True)}'>",
        f"<meta property='og:description' content='{html.escape(desc, quote=True)}'>",
        f"<meta property='og:url' content='{html.escape(page_url, quote=True)}'>",
        f"<meta property='og:type' content='{html.escape(kind, quote=True)}'>",
        "<meta property='og:site_name' content='AIハブ'>",
        "<meta name='twitter:card' content='summary'>",
    ])


def _inject_heading_ids(body_html: str) -> tuple[str, list[tuple[str, str]]]:
    """h2 に id を付与し、(id, text) のリストを返す。"""
    toc: list[tuple[str, str]] = []
    used: set[str] = set()

    def repl(m: re.Match) -> str:
        text = m.group(1).strip()
        # slug 作成(日本語も通す)
        slug = _SLUG_NON_ALNUM.sub("-", text).strip("-").lower()
        if not slug:
            slug = f"h-{len(toc) + 1}"
        base = slug
        i = 2
        while slug in used:
            slug = f"{base}-{i}"
            i += 1
        used.add(slug)
        toc.append((slug, text))
        return f"<h2 id='{slug}'>{text}</h2>"

    new_html = _HEADING_ID_RE.sub(repl, body_html)
    return new_html, toc


def render_content_page(title: str, meta: dict, body_html: str, nav_html: str, page_path: str = "", kind: str = "") -> str:
    body_html, toc = _inject_heading_ids(body_html)
    page_url = f"{SITE_URL}/{page_path.lstrip('/')}" if page_path else SITE_URL
    parts: list[str] = []
    parts.append("<!doctype html><html lang='ja'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    parts.append(f"<title>{html.escape(title)} | AIハブ</title>")
    desc = str(meta.get("summary") or "")
    if desc:
        parts.append(f"<meta name='description' content='{html.escape(desc, quote=True)}'>")
    parts.append(f"<link rel='canonical' href='{html.escape(page_url, quote=True)}'>")
    parts.append(_build_ogp(title, desc, page_url, "article" if kind in ("lecture", "speaker") else "website"))
    if kind:
        jsonld_kind = "website" if kind == "portfolio" else kind
        ld = _build_jsonld(jsonld_kind, meta, title, page_url)
        if ld:
            parts.append(f"<script type='application/ld+json'>{ld}</script>")
    parts.append(f"<style>{CSS}{CONTENT_CSS}</style></head><body><div class='container'>")
    parts.append(ADMIN_BUTTON_HTML)
    parts.append("<header>")
    parts.append(f"<h1>{html.escape(title)}</h1>")
    sub_bits: list[str] = []
    if meta.get("role"):
        sub_bits.append(f"<span class='role'>{html.escape(str(meta['role']))}</span>")
    if meta.get("date"):
        sub_bits.append(f"<span>📅 {html.escape(str(meta['date']))}</span>")
    if meta.get("gen_by"):
        sub_bits.append(f"<span>{html.escape(str(meta['gen_by']))}</span>")
    if meta.get("profile_url"):
        url = html.escape(str(meta["profile_url"]), quote=True)
        sub_bits.append(f"<a href='{url}' target='_blank' rel='noopener'>プロフィール</a>")
    if sub_bits:
        parts.append("<div class='speaker-meta'>" + "".join(sub_bits) + "</div>")
    parts.append(nav_html)
    parts.append("</header>")
    parts.append("<div class='content-wrap'>")
    # TOC: h2 が 3 個以上あれば出す
    if len(toc) >= 3:
        parts.append("<div class='content-toc'><div class='toc-label'>🗂 目次</div><ol>")
        for slug, text in toc:
            parts.append(f"<li><a href='#{slug}'>{html.escape(text)}</a></li>")
        parts.append("</ol></div>")
    parts.append(body_html)
    parts.append("</div>")
    parts.append("<footer>AIハブ / Generated by Claude</footer>")
    parts.append("<button class='back-to-top' id='backTop' aria-label='トップへ戻る'>↑</button>")
    parts.append("<script>(function(){var b=document.getElementById('backTop');if(!b)return;window.addEventListener('scroll',function(){b.classList.toggle('show',window.scrollY>400);});b.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});})();</script>")
    parts.append("</div></body></html>")
    return "".join(parts)


def build_speaker_page() -> bool:
    if not SPEAKER_MD.exists():
        return False
    md = _load_markdown()
    raw = SPEAKER_MD.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    body_html = md.markdown(body, extensions=["extra", "sane_lists"])
    title = meta.get("name") or "講師紹介"
    nav = (
        "<nav>"
        "<a href='./index.html'>🏠 トップ</a> "
        "<a href='./portfolio.html'>🏆 実績</a> "
        "<a href='./lectures/index.html'>📝 講習資料</a> "
        "<a href='./programming-map.html'>📘 プログラミングマップ</a> "
        "<a href='./archive.html'>📚 過去ログ</a> "
        "<a href='/admin' data-localhost-only='1' style='display:none'>⚙️ 管理</a>"
        "</nav>"
    )
    html_text = render_content_page(title, meta, body_html, nav, page_path="speaker.html", kind="speaker")
    (DIST / "speaker.html").write_text(html_text, encoding="utf-8")
    return True


def build_lectures() -> int:
    if not LECTURES_DIR.exists():
        return 0
    md = _load_markdown()
    out_dir = DIST / "lectures"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    index_items: list[tuple[str, str, dict]] = []
    for f in sorted(LECTURES_DIR.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        body_html = md.markdown(body, extensions=["extra", "sane_lists"])
        title = meta.get("title") or f.stem
        nav = (
            "<nav>"
            "<a href='../index.html'>🏠 トップ</a> "
            "<a href='../speaker.html'>🎤 講師紹介</a> "
            "<a href='../portfolio.html'>🏆 実績</a> "
            "<a href='./index.html'>📝 資料一覧</a> "
            "<a href='/admin' data-localhost-only='1' style='display:none'>⚙️ 管理</a>"
            "</nav>"
        )
        (out_dir / f"{f.stem}.html").write_text(
            render_content_page(title, meta, body_html, nav, page_path=f"lectures/{f.stem}.html", kind="lecture"),
            encoding="utf-8",
        )
        index_items.append((f.stem, title, meta))
        count += 1
    if index_items:
        lines = ["## 講習資料一覧", ""]
        for slug, title, meta in index_items:
            date = meta.get("date", "")
            lines.append(f"- [{title}](./{slug}.html){f' — {date}' if date else ''}")
        body_html = md.markdown("\n".join(lines), extensions=["extra", "sane_lists"])
        nav = (
            "<nav>"
            "<a href='../index.html'>🏠 トップ</a> "
            "<a href='../speaker.html'>🎤 講師紹介</a> "
            "<a href='../portfolio.html'>🏆 実績</a> "
            "<a href='/admin' data-localhost-only='1' style='display:none'>⚙️ 管理</a>"
            "</nav>"
        )
        (out_dir / "index.html").write_text(
            render_content_page("講習資料", {}, body_html, nav, page_path="lectures/index.html"),
            encoding="utf-8",
        )
    return count


_OGP_TITLE_RE = re.compile(r"<meta[^>]+property=['\"]og:title['\"][^>]+content=['\"]([^'\"]+)['\"]", re.I)
_OGP_DESC_RE = re.compile(r"<meta[^>]+property=['\"]og:description['\"][^>]+content=['\"]([^'\"]+)['\"]", re.I)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.I)
_DESC_RE = re.compile(r"<meta[^>]+name=['\"]description['\"][^>]+content=['\"]([^'\"]+)['\"]", re.I)


def _fetch_meta(url: str, timeout: float = 3.0) -> dict:
    """URL から og:title/og:description/<title>/meta[description] を拾う。失敗時は空 dict。"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 ai-hub-portfolio-bot/1.0",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000)  # 先頭 200KB で十分
            charset = resp.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        meta = {}
        m = _OGP_TITLE_RE.search(text)
        if m: meta["title"] = m.group(1).strip()
        m = _OGP_DESC_RE.search(text)
        if m: meta["desc"] = m.group(1).strip()
        if "title" not in meta:
            m = _TITLE_RE.search(text)
            if m: meta["title"] = m.group(1).strip()
        if "desc" not in meta:
            m = _DESC_RE.search(text)
            if m: meta["desc"] = m.group(1).strip()
        return meta
    except Exception:
        return {}


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url
    except Exception:
        return url


def build_portfolio_page() -> bool:
    if not PORTFOLIO_YAML.exists():
        return False
    try:
        raw = yaml.safe_load(PORTFOLIO_YAML.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    items = raw.get("portfolio") or []
    if not items:
        return False

    online = os.environ.get("AIWATCH_PORTFOLIO_NO_FETCH") != "1"

    # カテゴリでグループ化(定義順を維持)
    grouped: dict[str, list[dict]] = {}
    cat_order: list[str] = []
    for it in items:
        if it.get("status") == "retired":
            continue
        cat = it.get("category") or "その他"
        if cat not in grouped:
            grouped[cat] = []
            cat_order.append(cat)
        grouped[cat].append(it)

    # オンラインなら OGP を軽く取りに行く
    for cat in cat_order:
        for it in grouped[cat]:
            if not online:
                break
            meta = _fetch_meta(str(it.get("url")))
            if meta.get("title") and not it.get("_title"):
                it["_title"] = meta["title"]
            if meta.get("desc") and not it.get("_desc"):
                it["_desc"] = meta["desc"]

    parts: list[str] = ["<h1>🏆 実績・運営サイト</h1>"]
    parts.append(
        "<p>このワークスペース(Claude/配下)で制作・運営しているサイトを、カテゴリ別に掲載。"
        "各サイトは現在の公開ドメインを設定ファイル (<code>config/portfolio.yaml</code>) から引き、"
        "ドメインが変わったら 1 箇所書き換えるだけで全リンクが追従する。</p>"
    )

    for cat in cat_order:
        parts.append(f"<h2>{html.escape(cat)}</h2>")
        parts.append("<div class='pf-grid'>")
        for it in grouped[cat]:
            url = str(it.get("url") or "")
            name = str(it.get("name") or url)
            host = _host_of(url)
            summary = str(it.get("_desc") or it.get("summary") or "")
            if len(summary) > 140:
                summary = summary[:137] + "…"
            status = str(it.get("status") or "live")
            tech = it.get("tech") or []
            since = str(it.get("since") or "")

            parts.append(f"<a class='pf-card' href='{html.escape(url, quote=True)}' target='_blank' rel='noopener'>")
            parts.append(f"<div class='pf-title'>{html.escape(name)}</div>")
            parts.append(f"<div class='pf-host'>{html.escape(host)}</div>")
            if summary:
                parts.append(f"<div class='pf-sum'>{html.escape(summary)}</div>")
            parts.append("<div class='pf-meta'>")
            parts.append(f"<span class='pf-chip cat'>{html.escape(cat)}</span>")
            if status != "live":
                parts.append(f"<span class='pf-chip {html.escape(status)}'>{html.escape(status)}</span>")
            for t in tech:
                parts.append(f"<span class='pf-chip'>{html.escape(str(t))}</span>")
            if since:
                parts.append(f"<span class='pf-chip'>since {html.escape(since)}</span>")
            parts.append("</div>")
            parts.append("</a>")
        parts.append("</div>")

    parts.append(
        "<p class='pf-note'>💡 新しいサイトを追加する場合は <code>config/portfolio.yaml</code> に 1 ブロック追記。"
        "ドメイン変更時も同ファイルで URL を差し替えるだけ。"
        "オフラインビルドや CI で外部取得を止めたい場合は <code>AIWATCH_PORTFOLIO_NO_FETCH=1</code> を設定。</p>"
    )
    body_html = "".join(parts)
    meta = {
        "summary": "AIハブ 講師の由井辰美が制作・運営している実績サイト一覧。カテゴリ・技術スタック・公開年で絞って俯瞰できる。",
    }
    nav = (
        "<nav>"
        "<a href='./index.html'>🏠 トップ</a> "
        "<a href='./speaker.html'>🎤 講師紹介</a> "
        "<a href='./lectures/index.html'>📝 講習資料</a> "
        "<a href='./programming-map.html'>📘 プログラミングマップ</a> "
        "<a href='/admin' data-localhost-only='1' style='display:none'>⚙️ 管理</a>"
        "</nav>"
    )
    html_text = render_content_page("実績サイト", meta, body_html, nav, page_path="portfolio.html", kind="portfolio")
    (DIST / "portfolio.html").write_text(html_text, encoding="utf-8")
    return True


def copy_static() -> None:
    if not STATIC.exists():
        return
    for src in STATIC.rglob("*"):
        if src.is_dir():
            continue
        dst = DIST / src.relative_to(STATIC)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_sitemap_and_robots() -> None:
    """DIST 内の index.html / speaker.html / programming-map.html / lectures/*.html / archive/*.html を
    集めて sitemap.xml と robots.txt を生成。"""
    urls: list[tuple[str, str, float]] = []  # (loc, lastmod, priority)
    today = datetime.now().strftime("%Y-%m-%d")

    def add(path_rel: str, priority: float) -> None:
        f = DIST / path_rel
        if not f.exists():
            return
        ts = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        urls.append((f"{SITE_URL}/{path_rel.replace(chr(92), '/')}", ts, priority))

    add("index.html", 1.0)
    add("speaker.html", 0.9)
    add("portfolio.html", 0.9)
    add("programming-map.html", 0.9)
    add("archive.html", 0.6)
    # lectures
    lec_idx = DIST / "lectures" / "index.html"
    if lec_idx.exists():
        add("lectures/index.html", 0.7)
    lec_dir = DIST / "lectures"
    if lec_dir.exists():
        for lp in sorted(lec_dir.glob("*.html")):
            if lp.name == "index.html":
                continue
            add(f"lectures/{lp.name}", 0.8)
    # archive: date pages(YYYY-MM-DD.html)
    for arc in sorted(DIST.glob("*.html")):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\.html$", arc.name)
        if m:
            add(arc.name, 0.4)

    if not urls:
        return

    xml_lines = ["<?xml version='1.0' encoding='UTF-8'?>",
                 "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    for loc, lastmod, prio in urls:
        xml_lines.append(
            "  <url>"
            f"<loc>{html.escape(loc)}</loc>"
            f"<lastmod>{lastmod}</lastmod>"
            f"<priority>{prio:.1f}</priority>"
            "</url>"
        )
    xml_lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(xml_lines), encoding="utf-8")

    (DIST / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def main() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    copy_static()

    genres = load_genres()

    if not TOP10_JSON.exists():
        print(f"[!] {TOP10_JSON} が見つかりません。run.py を先に実行してください。")
        (DIST / "index.html").write_text(
            render_index({"date": datetime.now().strftime("%Y-%m-%d"), "items": []}, genres),
            encoding="utf-8",
        )
        (DIST / "archive.html").write_text(render_archive([]), encoding="utf-8")
        (DIST / ".nojekyll").write_text("", encoding="utf-8")
        build_speaker_page()
        build_lectures()
        build_portfolio_page()
        build_sitemap_and_robots()
        return 0

    payload = json.loads(TOP10_JSON.read_text(encoding="utf-8"))
    (DIST / "index.html").write_text(render_index(payload, genres), encoding="utf-8")

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    date = payload.get("date", datetime.now().strftime("%Y-%m-%d"))
    archive_file = ARCHIVE_DIR / f"{date}.json"
    archive_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    dates: list[str] = []
    for f in sorted(ARCHIVE_DIR.glob("*.json"), reverse=True):
        d = f.stem
        dates.append(d)
        arc_payload = json.loads(f.read_text(encoding="utf-8"))
        (DIST / f"{d}.html").write_text(render_index(arc_payload, genres), encoding="utf-8")

    (DIST / "archive.html").write_text(render_archive(dates), encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    speaker_built = build_speaker_page()
    lectures_built = build_lectures()
    portfolio_built = build_portfolio_page()
    build_sitemap_and_robots()

    print(
        f"[+] site built: {DIST} ({len(dates)} archive pages"
        + (", speaker.html" if speaker_built else "")
        + (f", {lectures_built} lectures" if lectures_built else "")
        + (", portfolio.html" if portfolio_built else "")
        + ", sitemap.xml, robots.txt)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

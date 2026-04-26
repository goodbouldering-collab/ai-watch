"""
サポートSNS 管理画面 (FastAPI)

起動:
    .venv/Scripts/python.exe -m uvicorn admin.server:app --port 4001 --reload

ブラウザ:
    http://localhost:4001/
"""
from __future__ import annotations
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "support_sns.yaml"
TOP_BUTTONS_FILE = ROOT / "config" / "top_buttons.yaml"
SPEAKER_FILE = ROOT / "content" / "speaker.md"
LECTURES_DIR = ROOT / "content" / "lectures"
ASSETS_DIR = ROOT / "content" / "assets"
STATIC_DIR = Path(__file__).resolve().parent / "static"
SITE_DIST = ROOT / "site" / "dist"

ASSET_EXT_OK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}
ASSET_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB

Platform = Literal[
    "youtube",
    "x",
    "instagram_feed",
    "instagram_reel",
    "instagram_story",
    "threads",
    "facebook",
]

PLATFORMS: list[Platform] = [
    "youtube",
    "x",
    "instagram_feed",
    "instagram_reel",
    "instagram_story",
    "threads",
    "facebook",
]


class Account(BaseModel):
    name: str
    handle: str = ""
    url: str = ""
    note: str = ""


class AccountInput(BaseModel):
    input: str


URL_PREFIX = {
    "youtube":          "https://www.youtube.com/",
    "x":                "https://x.com/",
    "instagram_feed":   "https://www.instagram.com/",
    "instagram_reel":   "https://www.instagram.com/",
    "instagram_story":  "https://www.instagram.com/",
    "threads":          "https://www.threads.net/",
    "facebook":         "https://www.facebook.com/",
}


def normalize_account(platform: Platform, raw: str) -> Account:
    s = raw.strip()
    if not s:
        raise HTTPException(400, "input is empty")

    if s.startswith("http://") or s.startswith("https://"):
        url = s.rstrip("/")
        tail = url.rsplit("/", 1)[-1]
        if platform in ("instagram_feed", "instagram_reel", "instagram_story", "facebook"):
            handle = "@" + tail.lstrip("@") if tail else ""
        elif platform == "threads":
            handle = tail if tail.startswith("@") else "@" + tail
        elif platform == "youtube":
            handle = tail if tail.startswith("@") else tail
        else:
            handle = "@" + tail.lstrip("@")
        name = handle.lstrip("@") or tail
        return Account(name=name, handle=handle, url=url)

    handle_raw = s.lstrip("@")
    if not handle_raw:
        raise HTTPException(400, "invalid input")

    prefix = URL_PREFIX[platform]
    if platform == "youtube":
        url = f"{prefix}@{handle_raw}"
        handle = "@" + handle_raw
    elif platform == "threads":
        url = f"{prefix}@{handle_raw}"
        handle = "@" + handle_raw
    elif platform in ("instagram_feed", "instagram_reel", "instagram_story", "facebook"):
        url = f"{prefix}{handle_raw}"
        handle = "@" + handle_raw
    else:
        url = f"{prefix}{handle_raw}"
        handle = "@" + handle_raw

    return Account(name=handle_raw, handle=handle, url=url)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"support_sns": {p: [] for p in PLATFORMS}}
    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    sns = data.get("support_sns") or {}
    for p in PLATFORMS:
        sns.setdefault(p, [])
    return {"support_sns": sns}


def save_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


app = FastAPI(title="ai-hub")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/site/")


@app.get("/admin")
@app.get("/admin/")
def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/support-sns")
def get_all() -> dict:
    return load_config()["support_sns"]


# ---------- 講師紹介 (content/speaker.md) ----------

class SpeakerPayload(BaseModel):
    content: str


@app.get("/api/speaker")
def get_speaker() -> dict:
    if not SPEAKER_FILE.exists():
        return {"content": "", "path": str(SPEAKER_FILE.relative_to(ROOT))}
    return {
        "content": SPEAKER_FILE.read_text(encoding="utf-8"),
        "path": str(SPEAKER_FILE.relative_to(ROOT)),
    }


@app.put("/api/speaker")
def put_speaker(payload: SpeakerPayload) -> dict:
    SPEAKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPEAKER_FILE.write_text(payload.content, encoding="utf-8")
    return {"ok": True, "bytes": len(payload.content.encode("utf-8"))}


# ---------- トップボタン (config/top_buttons.yaml) ----------

DEFAULT_TOP_BUTTONS = [
    {"id": "speaker",         "label": "講師紹介",           "icon": "🎤", "href": "./speaker.html",            "kind": "link",   "enabled": True},
    {"id": "portfolio",       "label": "実績",               "icon": "🏆", "href": "./portfolio.html",          "kind": "link",   "enabled": True},
    {"id": "lectures",        "label": "講習資料",           "icon": "📝", "href": "./lectures/index.html",     "kind": "link",   "enabled": True},
    {"id": "archive",         "label": "過去ログ",           "icon": "📚", "href": "./archive.html",            "kind": "link",   "enabled": True},
    {"id": "programming_map", "label": "プログラミングマップ", "icon": "📘", "href": "./programming-map.html",    "kind": "link",   "enabled": True},
    {"id": "run",             "label": "巡回実行",           "icon": "🔄", "href": "",                          "kind": "action", "action_id": "run", "enabled": True},
]


class TopButton(BaseModel):
    id: str = ""
    label: str = ""
    icon: str = ""
    href: str = ""
    kind: str = "link"       # "link" or "action"
    action_id: str = ""
    enabled: bool = True


class TopButtonsPayload(BaseModel):
    top_buttons: list[TopButton]


def load_top_buttons() -> list[dict]:
    if not TOP_BUTTONS_FILE.exists():
        return [dict(b) for b in DEFAULT_TOP_BUTTONS]
    try:
        data = yaml.safe_load(TOP_BUTTONS_FILE.read_text(encoding="utf-8")) or {}
        items = data.get("top_buttons") or []
        if not items:
            return [dict(b) for b in DEFAULT_TOP_BUTTONS]
        return items
    except Exception:
        return [dict(b) for b in DEFAULT_TOP_BUTTONS]


def save_top_buttons(items: list[dict]) -> None:
    TOP_BUTTONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOP_BUTTONS_FILE.write_text(
        yaml.safe_dump({"top_buttons": items}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


@app.get("/api/top-buttons")
def get_top_buttons() -> dict:
    return {"top_buttons": load_top_buttons()}


@app.put("/api/top-buttons")
def put_top_buttons(payload: TopButtonsPayload) -> dict:
    items = [b.model_dump() for b in payload.top_buttons]
    for b in items:
        if b.get("kind") not in ("link", "action"):
            raise HTTPException(400, f"invalid kind: {b.get('kind')!r}")
        if not b.get("id"):
            raise HTTPException(400, "id is required")
    save_top_buttons(items)
    return {"ok": True, "count": len(items)}


# ---------- サイト再ビルド ----------

@app.post("/api/rebuild")
def rebuild_site() -> dict:
    try:
        r = subprocess.run(
            [sys.executable, "site/build_site.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        return {
            "ok": r.returncode == 0,
            "stdout": (r.stdout or "")[-3000:],
            "stderr": (r.stderr or "")[-1500:],
        }
    except Exception as e:
        return {"ok": False, "stderr": str(e)}


@app.post("/api/support-sns/{platform}")
def add_account(platform: Platform, payload: AccountInput) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(400, f"unknown platform: {platform}")
    account = normalize_account(platform, payload.input)
    data = load_config()
    data["support_sns"][platform].append(account.model_dump())
    save_config(data)
    return {"ok": True, "platform": platform, "account": account.model_dump()}


@app.delete("/api/support-sns/{platform}/{index}")
def delete_account(platform: Platform, index: int) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(400, f"unknown platform: {platform}")
    data = load_config()
    items = data["support_sns"][platform]
    if index < 0 or index >= len(items):
        raise HTTPException(404, "index out of range")
    removed = items.pop(index)
    save_config(data)
    return {"ok": True, "removed": removed}


_run_state = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_status": None,
    "last_log": "",
}
_run_lock = threading.Lock()


def _execute_pipeline() -> None:
    log_lines: list[str] = []
    try:
        log_lines.append("[1/2] run.py")
        r1 = subprocess.run(
            [sys.executable, "run.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        log_lines.append(r1.stdout[-4000:] if r1.stdout else "")
        if r1.stderr:
            log_lines.append("[stderr] " + r1.stderr[-1000:])

        log_lines.append("\n[2/2] support_sns_collector")
        r2 = subprocess.run(
            [sys.executable, "-m", "core.support_sns_collector"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        log_lines.append(r2.stdout[-2000:] if r2.stdout else "")
        if r2.stderr:
            log_lines.append("[stderr] " + r2.stderr[-500:])

        _run_state["last_status"] = "ok" if r1.returncode == 0 else "error"
    except Exception as e:
        log_lines.append(f"[exception] {e}")
        _run_state["last_status"] = "error"
    finally:
        _run_state["last_log"] = "\n".join(log_lines)
        _run_state["last_finished"] = datetime.now(timezone.utc).isoformat()
        with _run_lock:
            _run_state["running"] = False


@app.post("/api/run")
def trigger_run() -> dict:
    with _run_lock:
        if _run_state["running"]:
            return {"ok": False, "message": "すでに実行中です", "state": _run_state}
        _run_state["running"] = True
        _run_state["last_started"] = datetime.now(timezone.utc).isoformat()
        _run_state["last_status"] = "running"
    threading.Thread(target=_execute_pipeline, daemon=True).start()
    return {"ok": True, "message": "巡回を開始しました", "state": _run_state}


@app.get("/api/run/status")
def run_status() -> dict:
    return _run_state


# ---------- 講習資料 (content/lectures/*.md) ----------

import re

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


class LecturePayload(BaseModel):
    slug: str           # ファイル名 (拡張子なし)。例: "2026-04-ai-kihon"
    title: str = ""
    date: str = ""      # "2026-04-22" 形式
    role: str = "講習ノート"
    gen_by: str = "由井 辰美 / AIハブ"
    summary: str = ""
    body: str = ""      # Markdown 本文（frontmatterは含めない）


def _validate_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not s:
        raise HTTPException(400, "slug is required")
    if not SLUG_RE.match(s):
        raise HTTPException(400, "slug は小文字英数とハイフンのみ (例: 2026-04-ai-kihon)")
    return s


def _parse_lecture(raw: str) -> tuple[dict, str]:
    """ frontmatter + body に分割。frontmatter が無ければ {} と raw を返す。"""
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    body = parts[2].lstrip("\n")
    return meta, body


def _serialize_lecture(payload: LecturePayload) -> str:
    meta = {
        "title": payload.title,
        "date": payload.date,
        "role": payload.role,
        "gen_by": payload.gen_by,
        "summary": payload.summary,
    }
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{payload.body.lstrip()}\n"


@app.get("/api/lectures")
def list_lectures() -> dict:
    LECTURES_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(LECTURES_DIR.glob("*.md")):
        meta, _ = _parse_lecture(f.read_text(encoding="utf-8"))
        items.append({
            "slug": f.stem,
            "title": meta.get("title", f.stem),
            "date": meta.get("date", ""),
            "summary": meta.get("summary", ""),
            "bytes": f.stat().st_size,
        })
    items.sort(key=lambda x: x.get("date") or x["slug"], reverse=True)
    return {"lectures": items, "count": len(items)}


@app.get("/api/lectures/{slug}")
def get_lecture(slug: str) -> dict:
    s = _validate_slug(slug)
    f = LECTURES_DIR / f"{s}.md"
    if not f.exists():
        raise HTTPException(404, f"lecture not found: {s}")
    meta, body = _parse_lecture(f.read_text(encoding="utf-8"))
    return {
        "slug": s,
        "title": meta.get("title", ""),
        "date": meta.get("date", ""),
        "role": meta.get("role", "講習ノート"),
        "gen_by": meta.get("gen_by", "由井 辰美 / AIハブ"),
        "summary": meta.get("summary", ""),
        "body": body,
        "path": str(f.relative_to(ROOT)),
    }


@app.post("/api/lectures")
def create_lecture(payload: LecturePayload) -> dict:
    s = _validate_slug(payload.slug)
    LECTURES_DIR.mkdir(parents=True, exist_ok=True)
    f = LECTURES_DIR / f"{s}.md"
    if f.exists():
        raise HTTPException(409, f"既に存在します: {s}")
    payload.slug = s
    f.write_text(_serialize_lecture(payload), encoding="utf-8")
    return {"ok": True, "slug": s, "path": str(f.relative_to(ROOT))}


@app.put("/api/lectures/{slug}")
def update_lecture(slug: str, payload: LecturePayload) -> dict:
    s = _validate_slug(slug)
    f = LECTURES_DIR / f"{s}.md"
    if not f.exists():
        raise HTTPException(404, f"lecture not found: {s}")
    payload.slug = s
    f.write_text(_serialize_lecture(payload), encoding="utf-8")
    return {"ok": True, "slug": s, "bytes": f.stat().st_size}


@app.delete("/api/lectures/{slug}")
def delete_lecture(slug: str) -> dict:
    s = _validate_slug(slug)
    f = LECTURES_DIR / f"{s}.md"
    if not f.exists():
        raise HTTPException(404, f"lecture not found: {s}")
    f.unlink()
    return {"ok": True, "slug": s}


# ---------- Markdown プレビュー ----------

class PreviewPayload(BaseModel):
    body: str


@app.post("/api/lectures/preview")
def preview_markdown(payload: PreviewPayload) -> dict:
    import markdown as md_mod
    md = md_mod.Markdown(extensions=["extra", "sane_lists"])
    html = md.convert(payload.body or "")
    return {"html": html}


# ---------- アセットアップロード (content/assets/) ----------

@app.get("/api/assets")
def list_assets() -> dict:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(ASSETS_DIR.glob("*")):
        if not f.is_file():
            continue
        items.append({
            "name": f.name,
            "size": f.stat().st_size,
            "url": f"./assets/{f.name}",   # 公開サイトからの相対パス
        })
    return {"assets": items, "count": len(items)}


@app.post("/api/assets")
async def upload_asset(file: UploadFile = File(...)) -> dict:
    name = (file.filename or "").strip()
    if not name:
        raise HTTPException(400, "ファイル名が空です")
    # サニタイズ: パス分離・隠しファイル禁止
    name = Path(name).name
    if name.startswith("."):
        raise HTTPException(400, "隠しファイルは不可です")
    ext = Path(name).suffix.lower()
    if ext not in ASSET_EXT_OK:
        raise HTTPException(400, f"許可されない拡張子: {ext or '(なし)'}")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ASSETS_DIR / name
    # 重複時は連番つけて回避
    if dest.exists():
        stem, suf = dest.stem, dest.suffix
        for i in range(2, 1000):
            cand = ASSETS_DIR / f"{stem}-{i}{suf}"
            if not cand.exists():
                dest = cand
                break

    data = await file.read()
    if len(data) > ASSET_MAX_BYTES:
        raise HTTPException(413, f"ファイルが大きすぎます ({len(data)} > {ASSET_MAX_BYTES})")
    dest.write_bytes(data)
    return {"ok": True, "name": dest.name, "size": len(data), "url": f"./assets/{dest.name}"}


@app.delete("/api/assets/{name}")
def delete_asset(name: str) -> dict:
    safe = Path(name).name
    if safe.startswith(".") or "/" in name or "\\" in name:
        raise HTTPException(400, "不正なファイル名")
    f = ASSETS_DIR / safe
    if not f.exists() or not f.is_file():
        raise HTTPException(404, f"asset not found: {safe}")
    f.unlink()
    return {"ok": True, "name": safe}


# ---------- Shopify Admin ----------

from core import shopify_admin


def _shopify_call(fn, *args, **kwargs) -> dict:
    try:
        return {"ok": True, "data": fn(*args, **kwargs)}
    except shopify_admin.ShopifyConfigError as e:
        raise HTTPException(400, f"設定エラー: {e}")
    except shopify_admin.ShopifyAPIError as e:
        raise HTTPException(e.status if 400 <= e.status < 600 else 502, str(e))
    except Exception as e:
        raise HTTPException(500, f"内部エラー: {e}")


class InventorySetPayload(BaseModel):
    inventory_item_id: int
    location_id: int
    available: int


@app.get("/api/shopify/status")
def shopify_status() -> dict:
    return shopify_admin.is_configured()


@app.get("/api/shopify/shop")
def shopify_shop() -> dict:
    return _shopify_call(shopify_admin.shop_info)


@app.get("/api/shopify/products")
def shopify_products(limit: int = 20, q: str = "") -> dict:
    return _shopify_call(shopify_admin.list_products, limit=limit, query=q)


@app.get("/api/shopify/orders")
def shopify_orders(limit: int = 20, status: str = "any") -> dict:
    return _shopify_call(shopify_admin.list_orders, limit=limit, status=status)


@app.get("/api/shopify/customers")
def shopify_customers(q: str, limit: int = 20) -> dict:
    return _shopify_call(shopify_admin.search_customers, query=q, limit=limit)


@app.get("/api/shopify/locations")
def shopify_locations() -> dict:
    return _shopify_call(shopify_admin.list_locations)


@app.post("/api/shopify/inventory/set")
def shopify_set_inventory(payload: InventorySetPayload) -> dict:
    return _shopify_call(
        shopify_admin.set_inventory,
        inventory_item_id=payload.inventory_item_id,
        location_id=payload.location_id,
        available=payload.available,
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if SITE_DIST.exists():
    app.mount("/site", StaticFiles(directory=SITE_DIST, html=True), name="site")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找可商用照片、下载、并留下授权记录。

在当期项目的 _工作文件/ 里跑（脚本按 __file__ 的上一级当项目根）：

    python _工作文件/stock_photos.py search "ai data center" --top 8
    python _工作文件/stock_photos.py pick 2 --used-in 封面
    python _工作文件/stock_photos.py list
    python _工作文件/stock_photos.py record --file 素材/图库/我的截图.png \
        --source "自测截图" --license "自有" --author "本人"

来源与授权：
    Openverse  默认来源，无需密钥；只取 CC0 / 公共领域 / CC-BY / CC-BY-SA
    Pexels     设了 PEXELS_API_KEY 才可选（授权宽松，不强制署名）
    Unsplash   设了 UNSPLASH_ACCESS_KEY 才可选（授权宽松，不强制署名）

输出：
    素材/图库/<来源>-<序号>-<slug>.jpg     下载好的照片
    素材/图库/图片来源.md                 授权记录（qa.py 会检查它存在）
    素材/图库/_搜索_<slug>.json           上一次搜索结果，供 pick 按序号取

禁止用非商用授权（CC BY-NC / BY-ND）——公众号是商业场景，见 references/compliance.md。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "素材" / "图库"
CREDITS = LIB / "图片来源.md"
UA = "Mozilla/5.0 (compatible; skill-radar/1.0; personal curation bot)"

ALLOWED_LICENSES = {"cc0", "pdm", "by", "by-sa", "pexels", "unsplash"}
LICENSE_LABEL = {
    "cc0": "CC0", "pdm": "公共领域", "by": "CC BY", "by-sa": "CC BY-SA",
    "pexels": "Pexels 许可", "unsplash": "Unsplash 许可",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def slug(text: str, limit: int = 40) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", text).strip("-").lower()[:limit] or "img"


def get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, target: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
    target.write_bytes(data)
    return len(data)


def shrink(path: Path, max_width: int = 1600) -> None:
    """能装到 Pillow 就顺手压一下，省体积；装不到就保持原图。"""
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return
    try:
        im = Image.open(path)
        if im.width <= max_width:
            return
        ratio = max_width / im.width
        im = im.convert("RGB").resize((max_width, int(im.height * ratio)))
        im.save(path, quality=86, optimize=True)
    except Exception:  # noqa: BLE001
        pass


def search_openverse(query: str, top: int) -> list[dict]:
    url = ("https://api.openverse.org/v1/images/?"
           + urllib.parse.urlencode({
               "q": query,
               "page_size": max(top * 3, 12),
               "license_type": "commercial,modification",
               "mature": "false",
           }))
    data = get_json(url)
    out = []
    for item in data.get("results", []):
        lic = (item.get("license") or "").lower()
        if lic not in ALLOWED_LICENSES:
            continue
        out.append({
            "source": "openverse",
            "title": item.get("title") or query,
            "author": item.get("creator") or "未知",
            "author_url": item.get("creator_url") or "",
            "license": lic,
            "license_version": item.get("license_version") or "",
            "landing_url": item.get("foreign_landing_url") or "",
            "image_url": item.get("url") or "",
            "width": item.get("width") or 0,
            "height": item.get("height") or 0,
            "origin": item.get("source") or "",
        })
    return out


def search_pexels(query: str, top: int) -> list[dict]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise SystemExit("没有 PEXELS_API_KEY 环境变量，改用默认的 openverse。")
    url = ("https://api.pexels.com/v1/search?"
           + urllib.parse.urlencode({"query": query, "per_page": top, "orientation": "landscape"}))
    data = get_json(url, {"Authorization": key})
    return [{
        "source": "pexels",
        "title": photo.get("alt") or query,
        "author": photo.get("photographer") or "未知",
        "author_url": photo.get("photographer_url") or "",
        "license": "pexels",
        "license_version": "",
        "landing_url": photo.get("url") or "",
        "image_url": (photo.get("src") or {}).get("large2x") or (photo.get("src") or {}).get("large"),
        "width": photo.get("width") or 0,
        "height": photo.get("height") or 0,
        "origin": "pexels",
    } for photo in data.get("photos", [])]


def search_unsplash(query: str, top: int) -> list[dict]:
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        raise SystemExit("没有 UNSPLASH_ACCESS_KEY 环境变量，改用默认的 openverse。")
    url = ("https://api.unsplash.com/search/photos?"
           + urllib.parse.urlencode({"query": query, "per_page": top}))
    data = get_json(url, {"Authorization": f"Client-ID {key}"})
    return [{
        "source": "unsplash",
        "title": photo.get("alt_description") or query,
        "author": (photo.get("user") or {}).get("name") or "未知",
        "author_url": (photo.get("user") or {}).get("links", {}).get("html", ""),
        "license": "unsplash",
        "license_version": "",
        "landing_url": (photo.get("links") or {}).get("html", ""),
        "image_url": (photo.get("urls") or {}).get("regular"),
        "width": photo.get("width") or 0,
        "height": photo.get("height") or 0,
        "origin": "unsplash",
    } for photo in data.get("results", [])]


SEARCHERS = {"openverse": search_openverse, "pexels": search_pexels, "unsplash": search_unsplash}


def credit_line(rec: dict) -> str:
    lic = LICENSE_LABEL.get(rec["license"], rec["license"].upper())
    if rec.get("license_version"):
        lic += " " + rec["license_version"]
    parts = [f"{rec.get('author') or '未知'}／{rec.get('origin') or rec.get('source')}",
             lic]
    if rec.get("landing_url"):
        parts.append(rec["landing_url"])
    return " · ".join(parts)


def write_credit(rec: dict, path: Path, used_in: str) -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    if not CREDITS.exists():
        CREDITS.write_text(
            "# 图片来源与授权\n\n"
            "每一张用在文章里的外部图片都要在这里留一行。图注或文末按最后一列署名"
            "（CC0 与公共领域不强制署名，但照样记录）。口径见 references/compliance.md。\n\n"
            "| 文件 | 用在哪 | 作者／来源 | 许可 | 原始链接 |\n"
            "| --- | --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
    title = (rec.get("title") or "").replace("|", "/")[:60]
    with CREDITS.open("a", encoding="utf-8") as fh:
        fh.write(f"| {path.name} | {used_in} | {rec.get('author') or '未知'}／"
                 f"{rec.get('origin') or rec.get('source')} | "
                 f"{LICENSE_LABEL.get(rec['license'], rec['license'])}"
                 f"{' ' + rec['license_version'] if rec.get('license_version') else ''} | "
                 f"{rec.get('landing_url') or rec.get('image_url')} |\n")
        fh.write(f"\n<!-- 图注可用：图片：{credit_line(rec)}　（标题：{title}） -->\n")


def cmd_search(query: str, source: str, top: int) -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    recs = SEARCHERS[source](query, top)[:top]
    if not recs:
        raise SystemExit(f"没搜到可商用结果：{query}（换关键词或换来源）")
    cache = LIB / f"_搜索_{slug(query)}.json"
    cache.write_text(json.dumps({"query": query, "source": source, "results": recs},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"「{query}」可商用结果（来源 {source}），用 pick <序号> 下载：\n")
    for i, rec in enumerate(recs, 1):
        log(f"  [{i:>2}] {rec['width']}×{rec['height']}  "
            f"{LICENSE_LABEL.get(rec['license'], rec['license'])}  "
            f"{(rec.get('title') or '')[:44]}  — {rec.get('author')}")
    log(f"\n搜索结果已存 {cache}")
    log("挑好之后：python _工作文件/stock_photos.py pick 2 --used-in 封面")


def cmd_pick(index: int, used_in: str, keyword: str | None, max_width: int) -> None:
    if keyword:
        cache = LIB / f"_搜索_{slug(keyword)}.json"
    else:
        found = sorted(LIB.glob("_搜索_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not found:
            raise SystemExit("还没搜过图，先跑 search。")
        cache = found[0]
    data = json.loads(cache.read_text(encoding="utf-8"))
    recs = data.get("results", [])
    if not 1 <= index <= len(recs):
        raise SystemExit(f"序号超出范围：1–{len(recs)}")
    rec = recs[index - 1]
    ext = Path(urllib.parse.urlparse(rec["image_url"]).path).suffix or ".jpg"
    target = LIB / f"{rec['source']}-{index:02d}-{slug(data.get('query') or 'img')}{ext}"
    size = download(rec["image_url"], target)
    shrink(target, max_width)
    write_credit(rec, target, used_in)
    log(f"已下载 {target}（{target.stat().st_size // 1024} KB）")
    log(f"署名：{credit_line(rec)}")
    log(f"记录已写入 {CREDITS.name}")


def cmd_record(file_arg: str, source: str, lic: str, author: str, url: str,
               title: str, used_in: str) -> None:
    path = Path(file_arg)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"找不到文件：{path}")
    rec = {"source": source or "手工", "origin": source or "手工", "title": title or path.name,
           "author": author or "本人", "license": (lic or "自有").lower(),
           "license_version": "", "landing_url": url or "", "image_url": url or ""}
    write_credit(rec, path, used_in or "待定")
    log(f"已登记 {path.name} → {CREDITS}")


def cmd_list() -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    files = [p for p in sorted(LIB.iterdir()) if p.is_file() and not p.name.startswith(("_", "."))]
    if not files:
        log("素材/图库/ 里还没有图片。")
        return
    for p in files:
        log(f"  {p.stat().st_size // 1024:>5} KB  {p.name}")
    log(f"\n授权记录：{CREDITS if CREDITS.exists() else '（还没有，qa.py 会拦）'}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="可商用图片素材：搜索 / 下载 / 留授权记录")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="按关键词搜索可商用照片")
    s.add_argument("query")
    s.add_argument("--source", default="openverse", choices=list(SEARCHERS))
    s.add_argument("--top", type=int, default=8)

    p = sub.add_parser("pick", help="下载上一次搜索结果里的第 N 张")
    p.add_argument("index", type=int)
    p.add_argument("--used-in", default="待定", help="用在哪：封面 / 配图1 / …")
    p.add_argument("--keyword", help="指定某次搜索的关键词（默认用最近一次）")
    p.add_argument("--max-width", type=int, default=1600)

    r = sub.add_parser("record", help="登记自己截的图或手工下载的图")
    r.add_argument("--file", required=True)
    r.add_argument("--source", default="")
    r.add_argument("--license", default="", help="自有 / CC0 / CC BY 2.0 …")
    r.add_argument("--author", default="")
    r.add_argument("--url", default="")
    r.add_argument("--title", default="")
    r.add_argument("--used-in", default="")

    sub.add_parser("list", help="列出图库里的图片与授权记录")
    args = ap.parse_args()

    if args.cmd == "search":
        cmd_search(args.query, args.source, args.top)
    elif args.cmd == "pick":
        cmd_pick(args.index, args.used_in, args.keyword, args.max_width)
    elif args.cmd == "record":
        cmd_record(args.file, args.source, args.license, args.author, args.url,
                   args.title, args.used_in)
    else:
        cmd_list()


if __name__ == "__main__":
    main()

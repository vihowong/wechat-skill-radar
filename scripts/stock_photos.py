#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找可商用照片、下载、并留下授权记录。

在当期项目的 _工作文件/ 里跑（脚本按 __file__ 的上一级当项目根）：

    python _工作文件/stock_photos.py search "ai data center" --top 8
    python _工作文件/stock_photos.py search --theme cyberpunk --top 8 --min-width 1600
    python _工作文件/stock_photos.py pick 2 --used-in 封面
    python _工作文件/stock_photos.py list
    python _工作文件/stock_photos.py record --file 素材/图库/我的截图.png \
        --source "自测截图" --license "自有" --author "本人"

来源与授权：
    commons    默认来源，Wikimedia Commons，无需密钥；只取公共领域 / CC0 / CC-BY / CC-BY-SA
    Openverse  无需密钥（偶发 401/429 会自动重试）；设 OPENVERSE_API_KEY 可提高配额
    Pexels     设了 PEXELS_API_KEY 才可选（画质好，授权宽松，不强制署名）
    Unsplash   设了 UNSPLASH_ACCESS_KEY 才可选（画质好，授权宽松，不强制署名）

输出：
    素材/图库/<来源>-<序号>-<slug>.jpg     下载好的照片
    素材/图库/图片来源.md                 授权记录（qa.py 会检查它存在）
    素材/图库/_搜索_<slug>.json           上一次搜索结果，供 pick 按序号取

禁止用非商用授权（CC BY-NC / BY-ND）——公众号是商业场景，见 references/compliance.md。

题材：用 --theme 直接取科技 / AI / 赛博朋克这几套关键词（英文检索命中更好），
见 references/visual-recipes.md 第二节；也可以自己给中英文关键词。
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "素材" / "图库"
CREDITS = LIB / "图片来源.md"
UA = "Mozilla/5.0 (compatible; skill-radar/1.0; personal curation bot)"

ALLOWED_LICENSES = {"cc0", "pdm", "by", "by-sa", "pexels", "unsplash"}
COMMONS_OK = re.compile(r"(public domain|cc0|cc[ -]by(-sa)?\b|attribution)", re.I)
COMMONS_BAD = re.compile(r"(\bnc\b|non-?commercial|\bnd\b|no-?deriv)", re.I)
# 疑似 AI 生成的素材：可以用，但发布时要按 compliance.md 标识，别当成实拍照片
AI_HINT = re.compile(r"(stable diffusion|midjourney|dall[- ]?e|flux|sdxl|generative|ai[- ]?generated|"
                     r"artificial intelligence|\bsd ?\d(?:\.\d)?\b)", re.I)

# 题材关键词：英文命中率更高，一组多问句合并去重（详见 references/visual-recipes.md 第二节）
THEMES: dict[str, list[str]] = {
    "tech": ["data center servers", "server room lights", "circuit board macro",
             "technology abstract dark"],
    "ai": ["artificial intelligence abstract", "neural network visualization",
           "ai chip processor", "robot hand technology"],
    "cyberpunk": ["cyberpunk city night neon", "neon lights dark street",
                  "futuristic city rain", "hologram neon abstract"],
    "code": ["programming code screen dark", "developer workspace night",
             "terminal screen closeup", "keyboard backlight macro"],
    "robot": ["robot arm industry", "humanoid robot", "drone technology"],
    "data": ["data visualization screen", "dashboard screen dark", "charts monitor glow"],
    "abstract": ["abstract dark gradient texture", "digital particles dark",
                 "network nodes dark", "glowing mesh abstract"],
}
LICENSE_LABEL = {
    "cc0": "CC0", "pdm": "公共领域", "by": "CC BY", "by-sa": "CC BY-SA",
    "pexels": "Pexels 许可", "unsplash": "Unsplash 许可",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def slug(text: str, limit: int = 40) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", text).strip("-").lower()[:limit] or "img"


def get_json(url: str, headers: dict[str, str] | None = None, tries: int = 3) -> dict:
    """取 JSON；401/403/429/5xx 退避重试，重试仍失败就给一条可操作的提示。"""
    last = ""
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in (401, 403, 429) or exc.code >= 500:
                time.sleep(4 * (attempt + 1))
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"图库接口请求失败：{last}\n"
                     f"  可以换来源再试：--source commons|pexels|unsplash（commons 无需密钥）\n"
                     f"  或等几分钟重试；Openverse 偶发限流，设 OPENVERSE_API_KEY 可以放宽配额")


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
    key = os.environ.get("OPENVERSE_API_KEY") or os.environ.get("OPENVERSE_TOKEN")
    headers = {"Authorization": f"Bearer {key}"} if key else None
    data = get_json(url, headers)
    out = []
    for item in data.get("results", []):
        lic = (item.get("license") or "").lower()
        if lic not in ALLOWED_LICENSES:
            continue
        tag_blob = " ".join((t or {}).get("name", "") for t in (item.get("tags") or []))
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
            "ai_generated": bool(AI_HINT.search(f"{item.get('title') or ''} {tag_blob}")),
        })
    return out


def search_commons(query: str, top: int) -> list[dict]:
    """Wikimedia Commons：无需密钥，附带许可与作者信息；只保留可商用的许可。"""
    url = ("https://commons.wikimedia.org/w/api.php?"
           + urllib.parse.urlencode({
               "action": "query", "format": "json", "generator": "search",
               "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": "6",
               "gsrlimit": str(max(top * 3, 10)), "prop": "imageinfo",
               "iiprop": "url|size|extmetadata", "iiurlwidth": "1600",
           }))
    data = get_json(url)
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = ((meta.get("LicenseShortName") or {}).get("value") or "").strip()
        if not COMMONS_OK.search(lic) or COMMONS_BAD.search(lic):
            continue
        url_orig = (info.get("url") or "").split("?")[0]
        if not url_orig:
            continue
        artist = html_mod.unescape(re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value") or ""))
        ai_flag = bool(AI_HINT.search(f"{artist} {page.get('title') or ''} "
                                      f"{' '.join(meta.get('Categories') or [])}"))
        out.append({
            "source": "commons",
            "title": (page.get("title") or "").replace("File:", ""),
            "author": artist.strip() or "见原始页面",
            "author_url": info.get("descriptionurl") or "",
            "license": "by-sa" if re.search(r"by-sa", lic, re.I) else ("cc0" if re.search(r"cc0|public domain", lic, re.I) else "by"),
            "license_version": lic,
            "landing_url": info.get("descriptionurl") or url_orig,
            "image_url": info.get("thumburl") or url_orig,
            "width": info.get("thumbwidth") or info.get("width") or 0,
            "height": info.get("thumbheight") or info.get("height") or 0,
            "origin": f"Wikimedia Commons（{lic}）",
            "ai_generated": ai_flag,
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


SEARCHERS = {"commons": search_commons, "openverse": search_openverse,
             "pexels": search_pexels, "unsplash": search_unsplash}


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
    ai_note = "（疑似 AI 生成，按 compliance.md 标识）" if rec.get("ai_generated") else ""
    with CREDITS.open("a", encoding="utf-8") as fh:
        fh.write(f"| {path.name} | {used_in} | {rec.get('author') or '未知'}／"
                 f"{rec.get('origin') or rec.get('source')} | "
                 f"{LICENSE_LABEL.get(rec['license'], rec['license'])}"
                 f"{' ' + rec['license_version'] if rec.get('license_version') else ''} | "
                 f"{rec.get('landing_url') or rec.get('image_url')} |\n")
        if ai_note:
            fh.write(f"\n<!-- {path.name} {ai_note} -->\n")
        fh.write(f"\n<!-- 图注可用：图片：{credit_line(rec)}　（标题：{title}） -->\n")


def resolve_source(name: str) -> str:
    """auto：有 Pexels / Unsplash 的密钥就用它们，否则用 Openverse（画质次之但免密钥）。"""
    if name != "auto":
        return name
    if os.environ.get("PEXELS_API_KEY"):
        return "pexels"
    if os.environ.get("UNSPLASH_ACCESS_KEY"):
        return "unsplash"
    return "openverse"


def gather(source: str, queries: list[str], top: int, min_width: int) -> list[dict]:
    recs: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        for rec in SEARCHERS[source](q, top):
            url = rec.get("image_url")
            if not url or url in seen:
                continue
            if min_width and (rec.get("width") or 0) < min_width:
                continue
            seen.add(url)
            rec["found_by"] = q
            recs.append(rec)
    return recs[:top]


def cmd_search(query: str | None, source: str, top: int, theme: str | None = None,
               min_width: int = 0) -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    if theme:
        queries = THEMES[theme]
        label = theme
    elif query:
        queries, label = [query], query
    else:
        raise SystemExit("给一个关键词（search \"dark server room\"），"
                         f"或者用 --theme 选一套：{ ' / '.join(THEMES) }")
    src = resolve_source(source)
    try:
        recs = gather(src, queries, top, min_width)
    except SystemExit as exc:
        if source != "auto" or src == "commons":
            raise
        log(f"[WARN] {src} 暂时不可用，自动改用 commons。原因：{exc}")
        src, recs = "commons", gather("commons", queries, top, min_width)
    source = src
    if not recs:
        raise SystemExit(f"没搜到可商用结果：{label}（换关键词、换来源，或调低 --min-width）")
    cache = LIB / f"_搜索_{slug(label)}.json"
    cache.write_text(json.dumps({"query": label, "theme": theme, "source": source,
                                 "results": recs}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    log(f"「{label}」可商用结果（来源 {source}"
        f"{'，题材 ' + theme if theme else ''}），用 pick <序号> 下载：\n")
    for i, rec in enumerate(recs, 1):
        mark = "⚠AI " if rec.get("ai_generated") else ""
        log(f"  [{i:>2}] {mark}{rec['width']}×{rec['height']}  "
            f"{LICENSE_LABEL.get(rec['license'], rec['license'])}  "
            f"{(rec.get('title') or '')[:40]}  — {rec.get('author')}"
            f"  [{rec.get('found_by', '')}]")
    log(f"\n搜索结果已存 {cache}")
    if any(r.get("ai_generated") for r in recs):
        log("⚠ 标 AI 的是疑似 AI 生成素材：可以用，但要在图注或文末标「本图由 AI 生成」，"
            "见 references/compliance.md")
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
    s.add_argument("query", nargs="?", help="关键词；用 --theme 时可以省")
    s.add_argument("--theme", choices=list(THEMES),
                   help="题材预设：tech / ai / cyberpunk / code / robot / data / abstract")
    s.add_argument("--source", default="auto", choices=["auto", *SEARCHERS],
                   help="auto=有 Pexels/Unsplash 密钥就用它们，否则 Openverse，失败自动退到 commons")
    s.add_argument("--top", type=int, default=8)
    s.add_argument("--min-width", type=int, default=0,
                   help="过滤小图；封面建议 1600，配图 1080 以上")

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
        cmd_search(args.query, args.source, args.top, args.theme, args.min_width)
    elif args.cmd == "pick":
        cmd_pick(args.index, args.used_in, args.keyword, args.max_width)
    elif args.cmd == "record":
        cmd_record(args.file, args.source, args.license, args.author, args.url,
                   args.title, args.used_in)
    else:
        cmd_list()


if __name__ == "__main__":
    main()

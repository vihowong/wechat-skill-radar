#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多源热点雷达：GitHub 新项目 + Hacker News + Reddit（RSS），外加手工线索。

在当期项目的 _工作文件/ 里跑（脚本按 __file__ 的上一级当项目根）：

    python _工作文件/trend_radar.py all --days 14 --top 20
    python _工作文件/trend_radar.py hn --days 14 --min-points 100
    python _工作文件/trend_radar.py github --days 90 --min-stars 300
    python _工作文件/trend_radar.py reddit --subs LocalLLaMA,AI_Agents
    python _工作文件/trend_radar.py link https://x.com/xxx/status/123 --note "为什么值得写"

产出：
    素材/热点雷达.md / .json   三个来源的当期热门（带链接与数字）
    素材/线索.md               人为追加的线索（X、网页搜索）
    素材/星标历史.csv          每次抓到的星标快照，用来对比出增速

Reddit 的公开 JSON 接口对服务器 IP 已封禁，这里走 RSS（只取标题、链接、时间）。
X 不做抓取，靠 `link` 子命令记录人工看到的线索。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "素材" / "raw"
OUT_MD = ROOT / "素材" / "热点雷达.md"
OUT_JSON = ROOT / "素材" / "热点雷达.json"
LINKS_MD = ROOT / "素材" / "线索.md"
STAR_HISTORY = ROOT / "素材" / "星标历史.csv"

UA = "Mozilla/5.0 (compatible; skill-radar/1.0; personal curation bot)"
CACHE_HOURS = 6
GITHUB_GAP_SECONDS = 7          # 未认证时搜索配额 10 次/分钟

# GitHub 侧默认查询：新项目（近似 trending）与几个 AI 方向的近期活跃项目
GITHUB_QUERIES: dict[str, str] = {
    "新项目冲刺": "created:>={since} stars:>={stars}",
    "LLM": "topic:llm pushed:>={since} stars:>={stars}",
    "Agent": "topic:ai-agent pushed:>={since} stars:>={stars}",
    "MCP": "topic:mcp pushed:>={since} stars:>={stars}",
    "Agent技能": "topic:agent-skills pushed:>={since} stars:>={stars}",
}

HN_DEFAULT_QUERIES = [
    "AI agent", "LLM", "agent skill", "MCP", "open source model",
    "coding agent", "local LLM", "AI coding",
]

REDDIT_DEFAULT_SUBS = [
    "LocalLLaMA", "MachineLearning", "AI_Agents", "ChatGPTCoding", "LLMDevs",
]
REDDIT_GAP_SECONDS = 11         # Reddit 对服务器 IP 限流很紧，间隔小了会连续 429


def log(msg: str) -> None:
    print(msg, flush=True)


def slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_")


def today() -> str:
    return dt.date.today().isoformat()


def days_ago(days: int) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


def fetch(url: str, accept: str = "*/*", timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def cached(path: Path, fetch_fn, refresh: bool, hours: float = CACHE_HOURS) -> bytes:
    if path.exists() and not refresh and (time.time() - path.stat().st_mtime) < hours * 3600:
        return path.read_bytes()
    data = fetch_fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


# ------------------------------------------------------------------ GitHub
def scan_github(days: int, min_stars: int, refresh: bool) -> list[dict]:
    since = days_ago(days)
    rows: dict[str, dict] = {}
    for idx, (label, tmpl) in enumerate(GITHUB_QUERIES.items()):
        query = tmpl.format(since=since, stars=min_stars)
        url = ("https://api.github.com/search/repositories?q="
               + urllib.parse.quote(query) + "&sort=stars&order=desc&per_page=25")
        cache_file = RAW_DIR / f"radar_github_{slug(label)}.json"

        def do_fetch(u=url):
            return fetch(u, "application/vnd.github+json")

        try:
            data = json.loads(cached(cache_file, do_fetch, refresh).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            log(f"[WARN] GitHub {label} 失败：HTTP {exc.code}（配额用尽先跑 fetch_missing.py 或稍后重试）")
            continue
        except Exception as exc:  # noqa: BLE001
            log(f"[WARN] GitHub {label} 失败：{exc}")
            continue

        for repo in data.get("items", []):
            full = repo["full_name"]
            rec = rows.setdefault(full, {
                "full_name": full,
                "stars": repo.get("stargazers_count", 0),
                "created_at": repo.get("created_at", "")[:10],
                "pushed_at": repo.get("pushed_at", "")[:10],
                "description": (repo.get("description") or "").strip(),
                "license": (repo.get("license") or {}).get("spdx_id"),
                "html_url": repo.get("html_url"),
                "found_by": [],
            })
            if label not in rec["found_by"]:
                rec["found_by"].append(label)
            rec["stars"] = max(rec["stars"], repo.get("stargazers_count", 0))
        log(f"[OK] GitHub {label}: 命中 {len(data.get('items', []))} 个")
        if idx < len(GITHUB_QUERIES) - 1:
            time.sleep(GITHUB_GAP_SECONDS)

    out = sorted(rows.values(), key=lambda r: -r["stars"])
    if out:
        STAR_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        new_file = not STAR_HISTORY.exists()
        with STAR_HISTORY.open("a", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            if new_file:
                writer.writerow(["date", "full_name", "stars"])
            for rec in out:
                writer.writerow([today(), rec["full_name"], rec["stars"]])
        log(f"星标快照已追加：{STAR_HISTORY.name}")
    return out


# ------------------------------------------------------------- Hacker News
def scan_hn(days: int, min_points: int, queries: list[str], refresh: bool) -> list[dict]:
    since_ts = int((dt.datetime.now() - dt.timedelta(days=days)).timestamp())
    hits: dict[str, dict] = {}
    for query in queries:
        url = ("https://hn.algolia.com/api/v1/search?"
               + urllib.parse.urlencode({
                   "query": query,
                   "tags": "story",
                   "numericFilters": f"created_at_i>{since_ts},points>{min_points}",
                   "hitsPerPage": "30",
               }))
        cache_file = RAW_DIR / f"radar_hn_{slug(query)}.json"

        def do_fetch(u=url):
            return fetch(u, "application/json")

        try:
            data = json.loads(cached(cache_file, do_fetch, refresh).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            log(f"[WARN] HN「{query}」失败：{exc}")
            continue

        count = 0
        for hit in data.get("hits", []):
            oid = hit.get("objectID")
            if not oid:
                continue
            rec = hits.setdefault(oid, {
                "id": oid,
                "title": (hit.get("title") or "").strip(),
                "points": hit.get("points") or 0,
                "comments": hit.get("num_comments") or 0,
                "created": (hit.get("created_at") or "")[:10],
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                "discuss": f"https://news.ycombinator.com/item?id={oid}",
                "found_by": [],
            })
            rec["points"] = max(rec["points"], hit.get("points") or 0)
            if query not in rec["found_by"]:
                rec["found_by"].append(query)
            count += 1
        log(f"[OK] HN「{query}」: 命中 {count} 条")
        time.sleep(0.6)

    return sorted(hits.values(), key=lambda r: -r["points"])


# ---------------------------------------------------------------- Reddit
def scan_reddit(days: int, subs: list[str], refresh: bool) -> list[dict]:
    window = "day" if days <= 1 else ("week" if days <= 7 else "month")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    posts: list[dict] = []
    blocked = 0
    for idx, sub in enumerate(subs):
        url = f"https://www.reddit.com/r/{sub}/top/.rss?t={window}"
        cache_file = RAW_DIR / f"radar_reddit_{slug(sub)}.xml"

        def do_fetch(u=url):
            return fetch(u, "application/atom+xml")

        root = None
        for attempt in range(3):
            try:
                raw = cached(cache_file, do_fetch, refresh and attempt == 0)
                root = ET.fromstring(raw.decode("utf-8", errors="replace"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 503):
                    blocked += 1
                    log(f"[retry {attempt + 1}] Reddit r/{sub}: HTTP {exc.code}（限流，等一会儿再试）")
                    time.sleep(25)
                    continue
                log(f"[WARN] Reddit r/{sub} 失败：HTTP {exc.code}")
                break
            except Exception as exc:  # noqa: BLE001
                log(f"[WARN] Reddit r/{sub} 失败：{exc}")
                break
        if root is None:
            continue

        count = 0
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title", "", ns) or "").strip()
            updated = (entry.findtext("a:updated", "", ns) or "")[:10]
            link_el = entry.find("a:link", ns)
            link = link_el.get("href") if link_el is not None else ""
            if not title or not link:
                continue
            posts.append({
                "sub": sub,
                "title": title,
                "created": updated,
                "url": link,
            })
            count += 1
        log(f"[OK] Reddit r/{sub}: {count} 条")
        if idx < len(subs) - 1:
            time.sleep(REDDIT_GAP_SECONDS)
    if blocked:
        log("提示：Reddit 限流时已抓到的子版会进缓存，隔几分钟重跑同一条命令"
            "（或分成几个 --subs 小批）就能补齐其余的。")
    return posts


# ------------------------------------------------------------------ 线索
def add_link(url: str, note: str, title: str = "") -> None:
    LINKS_MD.parent.mkdir(parents=True, exist_ok=True)
    if not LINKS_MD.exists():
        LINKS_MD.write_text(
            "# 线索\n\n"
            "人工看来的线索（X、网页搜索、私下看到的东西）。每条至少要有链接、日期、一个数字和一句为什么值得写。\n",
            encoding="utf-8",
        )
    with LINKS_MD.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {today()}\n\n")
        if title:
            fh.write(f"- 标题：{title}\n")
        fh.write(f"- 链接：{url}\n")
        fh.write(f"- 为什么值得写：{note or '（待补）'}\n")
        fh.write("- 需要补的数字：转发 / 点赞 / 作者给出的数字\n")
    log(f"已记入 {LINKS_MD}")


# ------------------------------------------------------------------ 输出
def write_report(github: list[dict], hn: list[dict], reddit: list[dict], top: int,
                 scanned: set[str]) -> None:
    """只扫描了部分来源时，其余来源沿用上一次的结果，避免把报告写残缺。"""
    if scanned != {"github", "hn", "reddit"} and OUT_JSON.exists():
        try:
            old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = {}
        if "github" not in scanned:
            github = old.get("github", [])
        if "hn" not in scanned:
            hn = old.get("hn", [])
        if "reddit" not in scanned:
            reddit = old.get("reddit", [])
        if old:
            log(f"（本次只扫描了 {'/'.join(sorted(scanned))}，其余来源沿用上次结果）")
    lines = [
        "# 热点雷达",
        "",
        f"- 生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 结构：GitHub {len(github)} 个 · Hacker News {len(hn)} 条 · Reddit {len(reddit)} 条",
        "- 提醒：星标、分数、投票都是当期快照；写进稿件前回原始页面核对一次。",
        "",
    ]
    if github:
        lines += ["## GitHub", "",
                  "| 星标 | 仓库 | 建库 | 最近更新 | 许可 | 简介 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for rec in github[:top]:
            desc = rec["description"].replace("|", "/")[:70]
            lines.append(f"| {rec['stars']:,} | [{rec['full_name']}]({rec['html_url']}) "
                         f"| {rec['created_at']} | {rec['pushed_at']} | {rec['license'] or '—'} | {desc} |")
        lines.append("")
    if hn:
        lines += ["## Hacker News", "",
                  "| 分数 | 评论 | 标题 | 日期 |",
                  "| --- | --- | --- | --- |"]
        for rec in hn[:top]:
            title = rec["title"].replace("|", "/")[:80]
            lines.append(f"| {rec['points']} | {rec['comments']} | "
                         f"[{title}]({rec['discuss']}) | {rec['created']} |")
        lines.append("")
    if reddit:
        lines += ["## Reddit", "",
                  "| 子版 | 标题 | 日期 |",
                  "| --- | --- | --- |"]
        for rec in reddit[:top]:
            title = rec["title"].replace("|", "/")[:90]
            lines.append(f"| r/{rec['sub']} | [{title}]({rec['url']}) | {rec['created']} |")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps({"github": github, "hn": hn, "reddit": reddit, "generated": today()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"已写出 {OUT_MD.name} 与 {OUT_JSON.name}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="多源热点雷达")
    ap.add_argument("mode", nargs="?", default="all",
                    choices=["all", "github", "hn", "reddit", "link"])
    ap.add_argument("url", nargs="?", help="link 模式的链接")
    ap.add_argument("--days", type=int, default=14, help="回看天数")
    ap.add_argument("--top", type=int, default=20, help="报告里每个来源保留的条数")
    ap.add_argument("--min-stars", type=int, default=200, help="GitHub 星标下限")
    ap.add_argument("--min-points", type=int, default=100, help="HN 分数下限")
    ap.add_argument("--queries", help="HN 关键词，逗号分隔")
    ap.add_argument("--subs", help="Reddit 子版，逗号分隔")
    ap.add_argument("--note", default="", help="link 模式的备注：为什么值得写")
    ap.add_argument("--refresh", action="store_true", help="忽略缓存重新抓")
    args = ap.parse_args()

    if args.mode == "link":
        if not args.url:
            raise SystemExit("link 模式需要给一个链接：trend_radar.py link <url> --note \"...\"")
        add_link(args.url, args.note)
        return

    hn_queries = [q.strip() for q in (args.queries or "").split(",") if q.strip()] or HN_DEFAULT_QUERIES
    subs = [s.strip().lstrip("r/") for s in (args.subs or "").split(",") if s.strip()] or REDDIT_DEFAULT_SUBS

    github: list[dict] = []
    hn: list[dict] = []
    reddit: list[dict] = []
    scanned: set[str] = set()
    if args.mode in ("all", "github"):
        github = scan_github(args.days, args.min_stars, args.refresh)
        scanned.add("github")
    if args.mode in ("all", "hn"):
        hn = scan_hn(args.days, args.min_points, hn_queries, args.refresh)
        scanned.add("hn")
    if args.mode in ("all", "reddit"):
        reddit = scan_reddit(args.days, subs, args.refresh)
        scanned.add("reddit")
    write_report(github, hn, reddit, args.top, scanned)


if __name__ == "__main__":
    main()

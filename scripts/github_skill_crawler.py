#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 GitHub 上各行业热门 Agent Skill 仓库，供公众号选题与写作使用。

思路：
  1. 按行业关键词调用 GitHub Search API（仓库搜索），结果缓存到 素材/raw/；
  2. 客户端过滤：必须与 Skill/Agent 相关，且近期有更新；
  3. 对入选仓库抓 README（走 raw.githubusercontent.com，不占 API 配额），存到 素材/readmes/；
  4. 输出候选清单 素材/候选技能清单.json / .csv 与一份 Markdown 摘要。

未配置 token 时只有 10 次/分钟 的搜索配额，脚本默认做了节流与缓存，可重复运行。
可选：设置环境变量 GITHUB_TOKEN 提升配额（脚本不会写入或打印 token）。

用法：
    python github_skill_crawler.py search          # 只跑搜索与候选筛选
    python github_skill_crawler.py readme          # 只跑 README 抓取（读候选清单）
    python github_skill_crawler.py all             # 全流程（默认）
    python github_skill_crawler.py search --refresh   # 忽略缓存重新搜索
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # 项目根目录
RAW_DIR = ROOT / "素材" / "raw"
README_DIR = ROOT / "素材" / "readmes"
CANDIDATE_JSON = ROOT / "素材" / "候选技能清单.json"
CANDIDATE_CSV = ROOT / "素材" / "候选技能清单.csv"
SUMMARY_MD = ROOT / "素材" / "抓取摘要.md"

UA = "Mozilla/5.0 (compatible; skill-research-bot/1.0)"
CACHE_HOURS = 12
SEARCH_GAP_SECONDS = 7          # 未认证时搜索配额 10 次/分钟，留出余量
README_LIMIT_CHARS = 14000

# 行业 → 搜索语句。中文键用于文章分栏，英文用于 GitHub 搜索。
INDUSTRY_QUERIES: dict[str, str] = {
    "通用技能库": "topic:agent-skills",
    "Claude技能": "topic:claude-skills",
    "Codex技能": "topic:codex-skills",
    "设计": "skill design in:name,description",
    "图表可视化": "skill diagram in:name,description",
    "办公文档": "skill document pdf spreadsheet in:name,description",
    "表格数据": "skill excel data analysis in:name,description",
    "写作内容": "skill writing in:name,description",
    "营销增长": "skill marketing seo in:name,description",
    "财务金融": "skill finance accounting in:name,description",
    "法律合规": "skill legal contract in:name,description",
    "科研学术": "skill research science in:name,description",
    "视频音频": "skill video audio in:name,description",
    "编程开发": "skill code review in:name,description",
    "电商运营": "skill ecommerce in:name,description",
    "人力资源": "skill recruiting resume in:name,description",
}

SKILL_HINT = re.compile(
    r"skill|agent|claude|codex|copilot|plugin|workflow|prompt",
    re.I,
)

# 营销专题：按细分职能搜索，避免只搜"marketing"一个词导致结果同质化
MARKETING_QUERIES: dict[str, str] = {
    "营销综合": "skill marketing in:name,description",
    "SEO与GEO": "skill seo geo in:name,description",
    "文案与内容": "skill copywriting content in:name,description",
    "广告投放": "skill ads advertising campaign in:name,description",
    "社交媒体": "skill social media in:name,description",
    "邮件营销": "skill email marketing in:name,description",
    "转化率优化": "skill cro conversion landing in:name,description",
    "品牌与公关": "skill brand public relations in:name,description",
    "网红营销": "skill influencer creator in:name,description",
    "增长分析": "skill growth analytics attribution in:name,description",
}

# 金融专题：覆盖财务、投资、量化、会计、税务、风控等细分方向
FINANCE_QUERIES: dict[str, str] = {
    "金融综合": "skill finance in:name,description",
    "财务与分析": "skill financial analysis reporting in:name,description",
    "会计与审计": "skill accounting audit in:name,description",
    "投资研究": "skill investment research equity in:name,description",
    "量化交易": "skill quantitative trading backtest in:name,description",
    "股票与行情": "skill stock market data in:name,description",
    "银行与支付": "skill banking payments in:name,description",
    "保险": "skill insurance in:name,description",
    "税务": "skill tax in:name,description",
    "风控与合规": "skill risk compliance aml in:name,description",
    "加密与数字资产": "skill crypto defi trading in:name,description",
}

# 出海贸易专题：先按宽词捞热门（星标排序），再在客户端按相关性筛
TRADE_QUERIES: dict[str, str] = {
    "跨境电商": "ecommerce skill",
    "出海与全球化": "global business skill",
    "国际物流与履约": "logistics fulfillment skill",
    "关务与关税": "customs tariff skill",
    "选品与供应链": "sourcing supplier skill",
    "亚马逊运营": "amazon seller skill",
    "独立站与 Shopify": "shopify skill",
    "本地化与翻译": "localization translation skill",
    "收款与开票": "invoicing payment skill",
    "海外获客": "b2b lead generation skill",
    "出口营销": "export marketing skill",
    "支付与合规": "payments compliance skill",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_")


def api_get(url: str) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cached_json(path: Path, fetch, refresh: bool, hours: int = CACHE_HOURS):
    if path.exists() and not refresh:
        age = time.time() - path.stat().st_mtime
        if age < hours * 3600:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def days_since(iso: str) -> int:
    if not iso:
        return 9999
    try:
        t = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return 9999
    return (dt.datetime.now(dt.timezone.utc) - t).days


def run_search(refresh: bool, max_age_days: int, query_set: str = "general") -> list[dict]:
    items: dict[str, dict] = {}
    SETS = {
        "general": INDUSTRY_QUERIES,
        "marketing": MARKETING_QUERIES,
        "finance": FINANCE_QUERIES,
        "trade": TRADE_QUERIES,
    }
    queries = SETS.get(query_set, INDUSTRY_QUERIES)
    for idx, (industry, query) in enumerate(queries.items()):
        url = (
            "https://api.github.com/search/repositories?q="
            + urllib.parse.quote(query)
            + "&sort=stars&order=desc&per_page=25"
        )
        cache_file = RAW_DIR / f"search_{slug(industry)}.json"

        def fetch(u=url):
            return api_get(u)

        try:
            data = cached_json(cache_file, fetch, refresh)
        except urllib.error.HTTPError as exc:
            log(f"[WARN] {industry} 搜索失败：HTTP {exc.code}（配额用尽时稍后重试）")
            continue
        except Exception as exc:  # noqa: BLE001
            log(f"[WARN] {industry} 搜索失败：{exc}")
            continue

        count = 0
        for repo in data.get("items", []):
            full = repo["full_name"]
            blob = " ".join(
                [
                    repo.get("name", ""),
                    repo.get("description") or "",
                    " ".join(repo.get("topics") or []),
                ]
            )
            if not SKILL_HINT.search(blob):
                continue
            if days_since(repo.get("pushed_at", "")) > max_age_days:
                continue
            rec = {
                "industry": industry,
                "full_name": full,
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "topics": repo.get("topics") or [],
                "description": (repo.get("description") or "").strip(),
                "language": repo.get("language"),
                "created_at": repo.get("created_at", "")[:10],
                "pushed_at": repo.get("pushed_at", "")[:10],
                "days_since_push": days_since(repo.get("pushed_at", "")),
                "html_url": repo.get("html_url"),
                "default_branch": repo.get("default_branch") or "main",
                "license": (repo.get("license") or {}).get("spdx_id"),
                "open_issues": repo.get("open_issues_count", 0),
            }
            prev = items.get(full)
            if prev is None:
                rec["industries"] = [industry]
                items[full] = rec
            else:
                prev["industries"].append(industry)
                if prev["stars"] < rec["stars"]:
                    prev["stars"] = rec["stars"]
            count += 1
        log(f"[OK] {industry}: 命中 {count} 个（累计 {len(items)}）")
        if idx < len(queries) - 1:
            time.sleep(SEARCH_GAP_SECONDS)

    result = sorted(items.values(), key=lambda r: -r["stars"])
    for rec in result:
        rec["industries"] = sorted(set(rec["industries"]))
        # 热度分：星标为主，近 30 天有更新加权
        rec["heat"] = round(
            rec["stars"] * (1.25 if rec["days_since_push"] <= 30 else 1.0), 0
        )
    CANDIDATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with CANDIDATE_CSV.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "industry", "full_name", "stars", "heat", "description",
                "language", "created_at", "pushed_at", "days_since_push",
                "license", "html_url",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for rec in result:
            row = dict(rec)
            row["industry"] = "/".join(rec["industries"])
            writer.writerow(row)
    log(f"候选清单已写出：{CANDIDATE_JSON.name}（{len(result)} 个仓库）")
    return result


def fetch_readme(repo: dict) -> tuple[str, str] | None:
    owner_repo = repo["full_name"]
    for branch in [repo.get("default_branch") or "main", "main", "master"]:
        for name in ("README.md", "readme.md", "README.MD"):
            url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{name}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=40) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                return (name, text[:README_LIMIT_CHARS])
            except Exception:  # noqa: BLE001
                continue
    return None


def run_readmes(top_n: int, only: list[str] | None) -> None:
    README_DIR.mkdir(parents=True, exist_ok=True)
    candidates = json.loads(CANDIDATE_JSON.read_text(encoding="utf-8"))
    if only:
        wanted = {name.lower() for name in only}
        candidates = [c for c in candidates if c["full_name"].lower() in wanted]
    else:
        candidates = candidates[:top_n]
    for repo in candidates:
        target = README_DIR / (repo["full_name"].replace("/", "__") + ".md")
        if target.exists() and target.stat().st_size > 200:
            log(f"[SKIP] {repo['full_name']} 已有 README")
            continue
        got = fetch_readme(repo)
        if not got:
            log(f"[WARN] {repo['full_name']} 未取到 README")
            continue
        _, text = got
        header = (
            f"<!-- source: {repo['html_url']} | stars: {repo['stars']} "
            f"| pushed: {repo['pushed_at']} -->\n\n"
        )
        target.write_text(header + text, encoding="utf-8")
        log(f"[OK] {repo['full_name']} README {len(text)} 字符")
        time.sleep(0.6)


def write_summary(candidates: list[dict]) -> None:
    lines = [
        "# 抓取摘要",
        "",
        f"- 抓取时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 候选仓库：{len(candidates)} 个",
        "",
        "| 热度 | 星标 | 仓库 | 最近更新 | 行业 | 简介 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rec in candidates[:60]:
        desc = rec["description"].replace("|", "/")[:90]
        lines.append(
            f"| {int(rec['heat'])} | {rec['stars']:,} | [{rec['full_name']}]({rec['html_url']}) "
            f"| {rec['pushed_at']} | {'/'.join(rec['industries'])} | {desc} |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"摘要已写出：{SUMMARY_MD.name}")
    log("")
    log("热度 Top 20：")
    for rec in candidates[:20]:
        log(
            f"  {int(rec['heat']):>7}  {rec['stars']:>8,}  {rec['full_name']:<45} "
            f"{rec['pushed_at']}  {rec['description'][:60]}"
        )


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="GitHub 热门 Skill 抓取")
    ap.add_argument("mode", nargs="?", default="all", choices=["search", "readme", "all"])
    ap.add_argument("--refresh", action="store_true", help="忽略缓存重新搜索")
    ap.add_argument("--max-age-days", type=int, default=45, help="仓库最近更新时间上限")
    ap.add_argument("--top", type=int, default=40, help="抓 README 的仓库数量")
    ap.add_argument("--only", nargs="*", help="只抓指定仓库的 README，如 owner/repo")
    ap.add_argument("--set", dest="query_set", default="general",
                    choices=["general", "marketing", "finance", "trade"], help="搜索词集合")
    args = ap.parse_args()

    if args.mode in ("search", "all"):
        candidates = run_search(args.refresh, args.max_age_days, args.query_set)
    else:
        candidates = json.loads(CANDIDATE_JSON.read_text(encoding="utf-8"))

    if args.mode in ("readme", "all"):
        run_readmes(args.top, args.only)

    write_summary(candidates)


if __name__ == "__main__":
    main()

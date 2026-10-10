#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补齐被 GitHub 限流挡掉的行业分类，再合并成候选清单。

未登录时搜索配额约 10 次/分钟，`github_skill_crawler.py search` 一次跑完 16 个分类
必然有一批返回 HTTP 403。这个脚本只补没抓到的分类：跳过已缓存且没过期的，
按 7.5 秒间隔逐条补抓，写进同一套 `素材/raw/` 缓存，最后复用 crawler 的合并逻辑。

在当期项目的 _工作文件/ 里跑：

    python _工作文件/fetch_missing.py
    python _工作文件/fetch_missing.py --set finance --max-age-days 45

缓存有效期默认 6 小时；想强制重抓就先删掉 `素材/raw/search_<行业>.json`。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import github_skill_crawler as g  # noqa: E402

SETS = {
    "general": lambda: g.INDUSTRY_QUERIES,
    "skill": lambda: g.SKILL_QUERIES,
    "ai": lambda: g.AI_QUERIES,
    "marketing": lambda: g.MARKETING_QUERIES,
    "finance": lambda: g.FINANCE_QUERIES,
    "trade": lambda: g.TRADE_QUERIES,
}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="补齐被限流的行业分类并合并候选")
    ap.add_argument("--set", dest="query_set", default="general", choices=list(SETS))
    ap.add_argument("--max-age-days", type=int, default=45)
    ap.add_argument("--gap", type=float, default=7.5, help="两次请求之间的间隔秒数")
    ap.add_argument("--cache-hours", type=float, default=6, help="跳过多新的缓存")
    ap.add_argument("--allow-projects", action="store_true", help="与 search 保持一致")
    ap.add_argument("--new-days", type=int, default=90)
    ap.add_argument("--min-stars", type=int, default=100)
    args = ap.parse_args()

    queries = SETS[args.query_set]()
    since = (dt.date.today() - dt.timedelta(days=args.new_days)).isoformat()
    missing = []
    for industry, query in queries.items():
        if "{" in query:
            query = query.format(since=since, stars=args.min_stars)
        path = g.RAW_DIR / f"search_{g.slug(industry)}.json"
        if path.exists() and (time.time() - path.stat().st_mtime) < args.cache_hours * 3600:
            print(f"[skip] {industry}")
            continue
        missing.append((industry, query, path))

    print(f"待补分类：{len(missing)} 个")
    for i, (industry, query, path) in enumerate(missing):
        url = ("https://api.github.com/search/repositories?q="
               + urllib.parse.quote(query) + "&sort=stars&order=desc&per_page=25")
        for attempt in range(3):
            try:
                data = g.api_get(url)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                encoding="utf-8")
                print(f"[OK] {industry}: {len(data.get('items', []))} 条")
                break
            except urllib.error.HTTPError as exc:
                print(f"[retry {attempt + 1}] {industry}: HTTP {exc.code}")
                time.sleep(20)
            except Exception as exc:  # noqa: BLE001
                print(f"[retry {attempt + 1}] {industry}: {exc}")
                time.sleep(10)
        else:
            print(f"[FAIL] {industry}")
        if i < len(missing) - 1:
            time.sleep(args.gap)

    print("--- 合并候选 ---")
    g.run_search(False, args.max_age_days, args.query_set,
                 args.allow_projects, args.new_days, args.min_stars)


if __name__ == "__main__":
    main()

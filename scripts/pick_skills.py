#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按行业挑当期候选：过滤行业 → 剔除已收录 → 按热度排序。

在当期项目的 _工作文件/ 里跑（脚本按 __file__ 的上一级当项目根）：

    python _工作文件/pick_skills.py --list-industries
    python _工作文件/pick_skills.py 金融
    python _工作文件/pick_skills.py --any --top 20        # 不限方向，看全部候选
    python _工作文件/pick_skills.py 设计 --covered 已收录仓库.txt --top 20
    python _工作文件/pick_skills.py 科研 --json > 素材/候选_科研.json

- 行业名支持包含匹配：「金融」能命中候选里的「财务金融」。
- --covered 每行一个 owner/repo；空行与 # 开头的行忽略。
- 挑完会打印一条 readme 抓取命令，可直接复制执行。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAND = ROOT / "素材" / "候选技能清单.json"


def load_covered(path: str | None) -> set[str]:
    if not path:
        return set()
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"找不到已收录清单：{p}")
    out: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s.split()[0].lower())
    return out


def industries_of(rec: dict) -> list[str]:
    inds = rec.get("industries")
    if inds:
        return [str(i) for i in inds]
    one = rec.get("industry")
    return [str(one)] if one else []


def match(keys: list[str], industry: str) -> bool:
    industry = industry.strip()
    return any(industry in k or k in industry for k in keys)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="按行业挑当期候选")
    ap.add_argument("industry", nargs="?", help="行业名，如 金融 / 设计 / 科研")
    ap.add_argument("--any", action="store_true", help="不限方向，直接按热度排全部候选")
    ap.add_argument("--candidates", default=str(DEFAULT_CAND), help="候选清单 json")
    ap.add_argument("--covered", help="已收录仓库清单，每行一个 owner/repo")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-stars", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="输出 JSON，便于后续处理")
    ap.add_argument("--list-industries", action="store_true", help="列出候选里有哪些行业")
    args = ap.parse_args()

    src = Path(args.candidates)
    if not src.exists():
        raise SystemExit(f"找不到候选清单：{src}\n先跑 github_skill_crawler.py search 生成它。")
    data = json.loads(src.read_text(encoding="utf-8"))

    if args.list_industries:
        tally: dict[str, int] = {}
        for rec in data:
            for k in industries_of(rec):
                tally[k] = tally.get(k, 0) + 1
        print(f"候选共 {len(data)} 个仓库，涉及 {len(tally)} 个方向/标签：")
        for k, n in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<12} {n:>3} 个")
        return

    if not args.industry and not args.any:
        raise SystemExit("要指定方向名（先加 --list-industries 看看有哪些），或者用 --any 看全部。")

    covered = load_covered(args.covered)
    rows = []
    for rec in data:
        keys = industries_of(rec)
        if args.industry and not match(keys, args.industry):
            continue
        if rec["full_name"].lower() in covered:
            continue
        if rec.get("stars", 0) < args.min_stars:
            continue
        rows.append(rec)
    rows.sort(key=lambda r: (-r.get("heat", r.get("stars", 0)), -r.get("stars", 0)))
    rows = rows[: args.top]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    scope = f"方向「{args.industry}」" if args.industry else "全部方向"
    print(f"{scope}可选题材 {len(rows)} 个（已剔除 {len(covered)} 个已收录仓库）\n")
    for r in rows:
        print(f"{r.get('stars', 0):>7}  {r['full_name']:<46} {r.get('pushed_at', '')}  "
              f"[{'/'.join(industries_of(r))}]")
        print(f"         {(r.get('description') or '')[:88]}")
    if rows:
        names = " ".join(r["full_name"] for r in rows[:10])
        print(f"\n下一步（清单类先定好 8–10 个再抓；单项目深挖只抓主角加 1–3 个对照）：\n"
              f"  python _工作文件/github_skill_crawler.py readme --only {names}")


if __name__ == "__main__":
    main()

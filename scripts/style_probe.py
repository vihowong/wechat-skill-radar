#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对标账号版式探针：抓一个公众号的若干篇文章，测出它的排版规格、结构、配图与标题句式。

用途：把「某个账号为什么读起来舒服」变成可核对的数字，再决定学什么、不学什么。
产物落盘到 `_对标/<账号>/`，可反复跑、可对比。

用法：
    # 1) 从一篇已知文章出发，拿账号标识与合集 id
    python style_probe.py seed "https://mp.weixin.qq.com/s/xxxxxxxx"

    # 2) 抓文章列表（合集分页 + 文章内相关推荐）
    python style_probe.py index --biz MzUxNjg4NDEzNA== --album 1339316622149992449 --max 20

    # 3) 抓正文
    python style_probe.py fetch --max 20

    # 4) 出报告（版式 / 结构 / 配图 / 标题）
    python style_probe.py report

    # 一次性全跑
    python style_probe.py all --seed "https://mp.weixin.qq.com/s/xxxxxxxx" --max 20

说明：
  - 只读公开页面，不登录、不绕过验证；频率默认 1.2s/次，被限流会自动退避重试。
  - 微信接口偶尔返回 200 但内容是空的（限流），脚本按"body 太短"判定并重试。
  - 合集分页的关键参数是 `begin_itemidx=1`；传 0 会返回空列表（这是最容易踩的坑）。
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HDRS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
ROOT = Path("_对标")
SLEEP = 1.2


# ------------------------------------------------------------------ 抓取
def fetch(url: str, referer: str = "https://mp.weixin.qq.com/"):
    """取原始字节。微信文章是 UTF-8，必须显式解码，否则中文会乱码。"""
    req = urllib.request.Request(url, headers={**HDRS, "Referer": referer})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


def decode(raw: bytes) -> str:
    head = raw[:5000].decode("latin-1", "ignore")
    m = re.search(r'charset=["\']?([A-Za-z0-9\-]+)', head)
    enc = (m.group(1).lower() if m else "utf-8")
    if enc in ("gb2312", "gbk", "gb18030"):
        enc = "gb18030"
    for e in (enc, "utf-8", "gb18030"):
        try:
            return raw.decode(e)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def get(url: str, min_len: int = 800, tries: int = 5, referer: str = "https://mp.weixin.qq.com/") -> str:
    """带退避的取页。微信限流时返回 200 但 body 很短，按长度判定后重试。"""
    last = ""
    for i in range(tries):
        try:
            last = decode(fetch(url, referer))
            if len(last) >= min_len:
                return last
        except Exception as e:                       # noqa: BLE001
            print(f"    retry{i} {type(e).__name__}: {e}")
        time.sleep(4 + i * 6 + random.random() * 3)
    return last


# ------------------------------------------------------------------ 解析
def get_body(h: str) -> str:
    m = re.search(r'id="js_content"[^>]*>(.*?)(?:<script|</div>\s*</div>\s*<div id="js_)', h, re.S)
    if not m:
        m = re.search(r'id="js_content"[^>]*>(.*)', h, re.S)
    return m.group(1) if m else ""


def text_of(node: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", node)
    t = re.sub(r"</(p|section|div|h\d|li|blockquote|tr)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"[\u00a0\u200b]+", " ", html.unescape(t))


def prop(style: str, name: str):
    m = re.search(rf"(?:^|;)\s*{re.escape(name)}\s*:\s*([^;]+)", style)
    return m.group(1).strip() if m else None


def unq(s: str) -> str:
    return (s or "").replace("&quot;", '"').replace("&amp;", "&")


def title_of(h: str) -> str:
    m = re.search(r"var msg_title = (.*?);", h, re.S)
    if not m:
        return ""
    t = html.unescape(m.group(1).strip())
    return re.sub(r"^['\"]|['\"]\.html\(false\)$|['\"]$", "", t).strip()


def seed_info(h: str) -> dict:
    def f(pat, g=1):
        m = re.search(pat, h, re.S)
        return html.unescape(m.group(g).strip()) if m else None
    return {
        "title": title_of(h),
        "nickname": (f(r"var nickname = (.*?);") or "").replace("htmlDecode(", "").strip('" )'),
        "biz": f(r"__biz=([A-Za-z0-9=+/]+)"),
        "album_id": (re.search(r"album_id=(\d+)", h) or [None, None])[1] if re.search(r"album_id=(\d+)", h) else None,
        "ct": f(r'var ct = "(\d+)"'),
        "og_image": f(r'property="og:image" content="([^"]+)"'),
    }


def extract_article_list(txt: str) -> list:
    """从响应里挖出 article_list 数组（括号配对，避免正则截断 JSON）。"""
    out = []
    for m in re.finditer(r'"article_list"\s*:\s*\[', txt):
        start, depth, i = m.end() - 1, 0, m.end() - 1
        while i < len(txt):
            c = txt[i]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try:
            arr = json.loads(txt[start:i + 1])
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(arr, list):
            out.extend(arr)
    return out


def norm_key(u: str) -> str:
    m = re.search(r"mid=(\d+).*?idx=(\d+)", html.unescape(u or ""))
    return f"{m.group(1)}_{m.group(2)}" if m else (u or "")


# ------------------------------------------------------------------ 子命令
def cmd_seed(a):
    h = get(a.url, min_len=50000)
    info = seed_info(h)
    d = ROOT / (info["nickname"] or "unknown")
    d.mkdir(parents=True, exist_ok=True)
    (d / "seed.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=1))
    print(f"\n已保存到 {d/'seed.json'}；接着跑：")
    print(f'  python style_probe.py index --biz {info["biz"]} --album {info["album_id"]} --max 20')


def cmd_index(a):
    d = ROOT / a.name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "index.json"
    idx = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if a.album:
        begin, last = 0, None
        for page in range(60):
            url = (f"https://mp.weixin.qq.com/mp/appmsgalbum?action=getalbum&__biz={a.biz}"
                   f"&album_id={a.album}&count=20&begin_msgid={begin}&begin_itemidx=1&f=json")
            txt = get(url)
            arr = extract_article_list(txt)
            new = 0
            for it in arr:
                if not isinstance(it, dict) or not it.get("url") or not it.get("title"):
                    continue
                k = norm_key(it["url"])
                if k not in idx:
                    idx[k] = {"title": it["title"].strip(), "url": it["url"],
                              "msgid": it.get("msgid", ""), "ct": it.get("create_time", ""),
                              "cover": it.get("cover_img_1_1", ""), "src": "album"}
                    new += 1
            print(f"  album page={page} got={len(arr)} new={new} total={len(idx)}")
            if not arr or len(idx) >= a.max:
                break
            mids = sorted(int(x) for x in re.findall(r'"msgid"\s*:\s*"?(\d+)', txt))
            if not mids:
                break
            nxt = mids[0]
            if nxt == begin or nxt == last:
                break
            last, begin = begin, nxt
            time.sleep(SLEEP)
    f.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"共 {len(idx)} 篇 → {f}")


def cmd_fetch(a):
    d = ROOT / a.name
    art = d / "articles"
    art.mkdir(exist_ok=True)
    # 两种来源：index.json（列表抓取），或 --urls 直接给文章链接（列表接口被限流时的退路）
    if getattr(a, "urls", None):
        items = [(f"url{i:02d}", {"title": f"url{i:02d}", "url": u})
                 for i, u in enumerate(a.urls, 1)]
    else:
        f = d / "index.json"
        if not f.exists():
            raise SystemExit(f"没有 {f}；先跑 index（或给 fetch 传 --urls 直接指定文章链接）")
        idx = json.loads(f.read_text(encoding="utf-8"))
        if not idx:
            raise SystemExit(
                "index.json 是空的——列表接口这会儿被限流了。\n"
                "  退路：等几分钟重跑 index，或直接用文章链接抓正文：\n"
                "    python style_probe.py fetch --name <账号名> --urls <文章链接> [<文章链接> ...]"
            )
        items = list(idx.items())[:a.max]
    done = 0
    for k, v in items:
        out = art / f"{re.sub(r'[^0-9A-Za-z_]+', '_', k)[:60]}.html"
        if out.exists() and out.stat().st_size > 50000:
            done += 1
            continue
        print(f"[{done+1}/{len(items)}] {v['title'][:44]}")
        h = get(v["url"], min_len=50000)
        if "js_content" in h:
            out.write_text(h, encoding="utf-8")
            done += 1
        else:
            print("    FAIL（可能是限流或链接失效；等几分钟再跑，它会续抓）")
        time.sleep(SLEEP + random.random())
    print(f"完成 {done}/{len(items)}")


def cmd_report(a):
    d = ROOT / a.name
    files = sorted(f for f in os.listdir(d / "articles") if f.endswith(".html"))
    if not files:
        raise SystemExit("还没有正文，先跑 fetch")
    sizes, lh, ls, colors, aligns = Counter(), Counter(), Counter(), Counter(), Counter()
    para_lens, titles, firsts, sec_titles = [], [], [], []
    sec_per_article, img_per_article = [], []
    img_fmt, img_w, img_ratio = Counter(), Counter(), Counter()
    joined = []
    n_paras = n_textstyle = 0
    n_articles = 0

    for fn in files:
        h = (d / "articles" / fn).read_text(encoding="utf-8", errors="ignore")
        body = get_body(h)
        if len(body) < 2000:
            continue
        n_articles += 1
        titles.append(title_of(h))
        n_imgs_this = 0
        for s in re.findall(r'style="([^"]*)"', body):
            if prop(s, "font-size"):
                sizes[prop(s, "font-size")] += 1
            if prop(s, "line-height"):
                lh[prop(s, "line-height")] += 1
            if prop(s, "letter-spacing"):
                ls[prop(s, "letter-spacing")] += 1
            if prop(s, "color"):
                colors[prop(s, "color")] += 1
            if prop(s, "text-align"):
                aligns[prop(s, "text-align")] += 1
        # 段落：区分外层默认字号与手动覆盖字号，取最终生效的
        for p in re.findall(r"<p[^>]*>.*?</p>", body, re.S):
            t = text_of(p).strip()
            n_paras += 1
            ts = re.findall(r'<span[^>]*textstyle=""[^>]*style="([^"]*)"', p)
            if ts:
                n_textstyle += 1
            fs = [prop(s, "font-size") for s in (ts or re.findall(r'<span[^>]*style="([^"]*)"', p))]
            fs = [x for x in fs if x]
            if t and not re.fullmatch(r"\d{2}", t):
                para_lens.append(len(t))
        lines = [x.strip() for x in text_of(body).split("\n") if x.strip()]
        prose = [x for x in lines if not re.fullmatch(r"\d{2}", x)]
        if prose:
            firsts.append(prose[0])
        joined.extend(prose)
        secs_this = 0
        for i, x in enumerate(lines):
            if re.fullmatch(r"\d{2}", x):
                secs_this += 1
                if i + 1 < len(lines):
                    sec_titles.append(lines[i + 1])
        sec_per_article.append(secs_this)
        for m in re.finditer(r"<img[^>]*>", body):
            tag = m.group(0)
            s = re.search(r'data-src="([^"]+)"', tag) or re.search(r'src="([^"]+)"', tag)
            u = html.unescape(s.group(1)) if s else ""
            n_imgs_this += 1
            img_fmt["gif" if ("wx_fmt=gif" in u or u.endswith(".gif")) else
                    "png" if "wx_fmt=png" in u else
                    "jpeg" if ("wx_fmt=jpeg" in u or "wx_fmt=jpg" in u) else "other"] += 1
            dw = re.search(r'data-w="(\d+)"', tag)
            dr = re.search(r'data-ratio="([\d.]+)"', tag)
            if dw:
                img_w[int(dw.group(1))] += 1
            if dr:
                r = float(dr.group(1))
                img_ratio["长图 <0.5" if r < 0.5 else "竖 0.5-0.9" if r < 0.9 else
                          "方 0.9-1.2" if r < 1.2 else "4:3 1.2-1.5" if r < 1.5 else
                          "16:10 1.5-1.9" if r < 1.9 else "宽 1.9-3" if r < 3 else "超宽 >3"] += 1
        img_per_article.append(n_imgs_this)

    j = "\n".join(joined)
    sents = [s for s in re.split(r"[。！？]", j) if s.strip()]
    sl = [len(s) for s in sents]
    R = []
    R.append(f"# 对标报告：{a.name}\n")
    R.append(f"样本 {n_articles} 篇 · 正文 {len(j)} 字 · 段落 {n_paras} 个\n")

    R.append("## 一、排版\n")
    R.append("| 项 | 值 |")
    R.append("| --- | --- |")
    R.append(f"| 字号（出现最多） | {sizes.most_common(5)} |")
    R.append(f"| 行高 | {lh.most_common(5)} |")
    R.append(f"| 字距 | {ls.most_common(5)} |")
    R.append(f"| 正文色 | {colors.most_common(8)} |")
    R.append(f"| 对齐 | {aligns.most_common(4)} |")
    R.append(f"| 手动覆盖字号的段落 | {n_textstyle}/{n_paras} |\n")

    R.append("## 二、结构\n")
    R.append("| 项 | 值 |")
    R.append("| --- | --- |")
    if para_lens:
        R.append(f"| 段落字数 | 中位 {statistics.median(para_lens)} · 均值 {round(statistics.mean(para_lens),1)} · 最长 {max(para_lens)} |")
        R.append(f"| ≤80 字段落占比 | {round(100*sum(1 for x in para_lens if x<=80)/len(para_lens),1)}% |")
    if sec_per_article:
        R.append(f"| 节数 | 中位 {statistics.median(sec_per_article)} · 区间 {min(sec_per_article)}–{max(sec_per_article)} |")
        R.append(f"| 节数分布 | {dict(sorted(Counter(sec_per_article).items()))} |")
    if img_per_article:
        R.append(f"| 图/篇 | 中位 {statistics.median(img_per_article)} · 均值 {round(statistics.mean(img_per_article),1)} |")
    if joined and img_per_article:
        R.append(f"| 图/千字 | {round(sum(img_per_article)/max(1,len(j)) * 1000, 1)} |")
    R.append("")

    R.append("## 三、图片\n")
    R.append("| 项 | 值 |")
    R.append("| --- | --- |")
    R.append(f"| 格式 | {img_fmt.most_common()} |")
    R.append(f"| 宽度 | {img_w.most_common(8)} |")
    R.append(f"| 比例分布 | {img_ratio.most_common()} |")
    R.append("")

    R.append("## 四、写作\n")
    R.append("| 项 | 值 |")
    R.append("| --- | --- |")
    if sl:
        R.append(f"| 句长 | 中位 {statistics.median(sl)} · 均值 {round(statistics.mean(sl),1)} |")
    if titles:
        L = [len(re.sub(r"[^\u4e00-\u9fff]", "", t)) for t in titles]
        R.append(f"| 标题汉字数 | 中位 {statistics.median(L)} · 区间 {min(L)}–{max(L)} |")
    for p, nm in [("——", "破折号"), ("！", "感叹号"), ("？", "问号"), ("，", "逗号"), ("。", "句号")]:
        R.append(f"| {nm} | {j.count(p)} 处（每千字 {round(j.count(p)/max(1,len(j))*1000,1)}） |")
    R.append(f"| 「你」/「我」 | {j.count('你')} / {j.count('我')} |\n")

    R.append("## 五、标题与开篇\n")
    R.append("**标题**\n")
    for t in titles:
        R.append(f"- {t}")
    R.append("\n**开篇第一句**\n")
    for f_ in firsts:
        R.append(f"- {f_[:90]}")
    R.append("\n**小节标题（编号后一行）**\n")
    for s in sec_titles[:40]:
        R.append(f"- {s[:70]}")

    out = d / "对标报告.md"
    out.write_text("\n".join(R), encoding="utf-8")
    print("\n".join(R[:60]))
    print(f"\n…完整报告 → {out}")


def cmd_all(a):
    """seed → index → fetch → report。列表接口被限流时退到"只抓 seed 那一篇"，不抛裸异常。"""
    seed_url = getattr(a, "seed", None)
    if getattr(a, "urls", None):
        cmd_fetch(a)
        cmd_report(a)
        return
    if seed_url:
        h = get(seed_url, min_len=50000)
        info = seed_info(h)
        if not info.get("biz"):
            raise SystemExit("没能从这篇文章里读出账号标识（biz）——换一篇该账号的文章再试。")
        d = ROOT / (info["nickname"] or "unknown")
        d.mkdir(parents=True, exist_ok=True)
        (d / "seed.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(info, ensure_ascii=False, indent=1))
        a.name, a.biz, a.album = d.name, info["biz"], info["album_id"]
    cmd_index(a)
    # 列表拿到了就按列表抓；没拿到（限流）就至少把 seed 这篇抓下来，仍能出版式报告
    idx_file = ROOT / a.name / "index.json"
    has_list = False
    if idx_file.exists():
        try:
            has_list = bool(json.loads(idx_file.read_text(encoding="utf-8")))
        except Exception:                            # noqa: BLE001
            has_list = False
    if has_list:
        cmd_fetch(a)
    elif seed_url:
        print("列表接口被限流，退到只抓 seed 这一篇（报告仍可出，只是样本为 1 篇）")
        a.urls = [seed_url]
        cmd_fetch(a)
    else:
        raise SystemExit("没有文章可抓：列表接口被限流，且没给 seed 链接。")
    cmd_report(a)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="对标账号版式探针")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("seed", help="从一篇文章拿到账号标识与合集 id")
    p.add_argument("url")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("index", help="抓文章列表")
    p.add_argument("--name", required=True, help="账号目录名（seed 输出的 nickname）")
    p.add_argument("--biz", required=True)
    p.add_argument("--album")
    p.add_argument("--max", type=int, default=20)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("fetch", help="抓正文")
    p.add_argument("--name", required=True)
    p.add_argument("--max", type=int, default=20)
    p.add_argument("--urls", nargs="*", default=None,
                   help="直接给文章链接（列表接口被限流时的退路；可只给一篇文章的链接，"
                        "再从中拿账号与合集 id 去抓列表）")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("report", help="出版式报告")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("all", help="seed → index → fetch → report")
    p.add_argument("--seed", required=True)
    p.add_argument("--name")
    p.add_argument("--biz")
    p.add_argument("--album")
    p.add_argument("--max", type=int, default=20)
    p.set_defaults(func=cmd_all)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()

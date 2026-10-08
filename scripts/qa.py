#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前自检：排版一致性、图片比例与体积、段落长度、必备模块、禁用元素、标题候选、AI 腔。

用法：python qa.py 发布稿.md 公众号粘贴版.html

可配置（可选）：在项目根目录放一个 qa_config.json，覆盖默认值——
    {
      "forbidden": ["旧品牌名", "旧脚本名"],        // 出现即 FAIL
      "colors": ["#0E7C66", "#0F172A", ...],        // 正文允许出现的文字颜色
      "install_prefixes": ["**装它**"],             // 这些开头的段落是命令行，不计入长度
      "max_paragraph": 110,
      "titles_min": 6,                              // 元信息里标题候选的最少条数
      "recommend_max_len": 20,                      // 推荐标题字数上限（超过只报警）
      "ai_hard": ["赋能", ...],                     // AI 腔硬禁用词，出现即 FAIL
      "ai_soft": ["其实", ...],                     // 慎用词，超过 ai_soft_max 报警
      "ai_soft_max": 2,
      "em_dash_max": 8,                             // 破折号「——」上限
      "field_dash_max": 3,                          // 同一个字段里用「——」接续的段数上限
      "exclaim_max": 2                              // 感叹号上限
    }
不写就用下面的默认值；改版式时记得同步改 colors。写作口径见 references/writing-craft.md。
"""

from __future__ import annotations

import re
import struct
import sys
from collections import Counter
from pathlib import Path

# 默认禁用词：自己账号的旧标识（旧品牌名、旧配色、旧脚本名）加到这里
DEFAULT_FORBIDDEN = ["往期推荐", "公众号名片", "扫码关注", "点击上方蓝字"]
DEFAULT_COLORS = {"#0E7C66", "#0F172A", "#1F2937", "#374151", "#6B7280", "#FFFFFF"}
DEFAULT_INSTALL_PREFIXES = ("**装它**",)
DEFAULT_MAX_PARAGRAPH = 110

# 标题党词：出现在标题里即 FAIL
DEFAULT_TITLE_BAN = ["震惊", "必看", "宝藏", "神器", "YYDS", "绝了", "速看", "限时",
                     "月入", "稳赚", "免费领", "禁止错过"]
DEFAULT_TITLES_MIN = 6
DEFAULT_RECOMMEND_MAX_LEN = 20

# AI 腔硬禁用词（出现即 FAIL）；慎用词超标只报警。口径见 references/writing-craft.md
DEFAULT_AI_HARD = ["赋能", "抓手", "闭环", "生态位", "全方位", "一站式", "在当今",
                   "综上所述", "总而言之", "众所周知", "不难看出", "值得注意的是",
                   "让我们", "不可否认", "显而易见", "极大地", "大大提升", "助力",
                   "打造生态", "深度赋能"]
DEFAULT_AI_SOFT = ["其实", "非常", "极其", "深度", "重磅", "堪称", "海量", "强大", "完美", "极致"]
DEFAULT_AI_SOFT_MAX = 2
DEFAULT_EM_DASH_MAX = 8
DEFAULT_FIELD_DASH_MAX = 3
DEFAULT_EXCLAIM_MAX = 2
DEFAULT_FLAT_RUN_MAX = 2          # 连续等长段落的窗口数上限
DEFAULT_REPEAT_MAX = 4            # 同一句式开头（前 4 字）最多出现的段落数


def _merge(base: list[str], extra) -> list[str]:
    return base + [w for w in (extra or []) if w not in base]


def load_config(root: Path) -> dict:
    """读可选的 qa_config.json；没有就用默认值。"""
    cfg = {
        "forbidden": list(DEFAULT_FORBIDDEN),
        "colors": set(DEFAULT_COLORS),
        "install_prefixes": tuple(DEFAULT_INSTALL_PREFIXES),
        "max_paragraph": DEFAULT_MAX_PARAGRAPH,
        "title_ban": list(DEFAULT_TITLE_BAN),
        "titles_min": DEFAULT_TITLES_MIN,
        "recommend_max_len": DEFAULT_RECOMMEND_MAX_LEN,
        "ai_hard": list(DEFAULT_AI_HARD),
        "ai_soft": list(DEFAULT_AI_SOFT),
        "ai_soft_max": DEFAULT_AI_SOFT_MAX,
        "em_dash_max": DEFAULT_EM_DASH_MAX,
        "field_dash_max": DEFAULT_FIELD_DASH_MAX,
        "exclaim_max": DEFAULT_EXCLAIM_MAX,
        "flat_run_max": DEFAULT_FLAT_RUN_MAX,
        "repeat_max": DEFAULT_REPEAT_MAX,
    }
    p = root / "qa_config.json"
    if p.exists():
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        cfg["forbidden"] += [w for w in data.get("forbidden", []) if w not in cfg["forbidden"]]
        if data.get("colors"):
            cfg["colors"] = {c.upper() for c in data["colors"]}
        if data.get("install_prefixes"):
            cfg["install_prefixes"] = tuple(data["install_prefixes"])
        cfg["max_paragraph"] = int(data.get("max_paragraph", DEFAULT_MAX_PARAGRAPH))
        cfg["title_ban"] = _merge(cfg["title_ban"], data.get("title_ban"))
        cfg["ai_hard"] = _merge(cfg["ai_hard"], data.get("ai_hard"))
        cfg["ai_soft"] = _merge(cfg["ai_soft"], data.get("ai_soft"))
        for key in ("titles_min", "recommend_max_len", "ai_soft_max", "em_dash_max",
                    "field_dash_max", "exclaim_max", "flat_run_max", "repeat_max"):
            if data.get(key) is not None:
                cfg[key] = int(data[key])
    return cfg


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    return struct.unpack(">II", head[16:24])


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    md_path = Path(sys.argv[1] if len(sys.argv) > 1 else "发布稿.md")
    html_path = Path(sys.argv[2] if len(sys.argv) > 2 else "公众号粘贴版.html")
    md = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    cfg = load_config(md_path.parent)

    fails: list[str] = []
    warns: list[str] = []
    passes: list[str] = []

    # 1. 禁用元素（只查正文：Markdown 的 > 元信息与 HTML 注释不算）
    md_body = "\n".join(l for l in md.splitlines() if not l.startswith(">"))
    html_body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    hits = [(w, md_body.count(w) + html_body.count(w)) for w in cfg["forbidden"]]
    hits = [(w, n) for w, n in hits if n]
    if hits:
        fails.append("出现不该有的标识：" + "、".join(f"{w}×{n}" for w, n in hits))
    else:
        passes.append("无禁用元素（往期推荐、公众号名片、自定义旧标识）")

    # 2. 段落长度（安装命令行天然偏长，只查正文段落）
    body = "\n".join(l for l in md.splitlines()
                     if l.strip() and not l.startswith(("#", ">", "!", "- "))
                     and not l.strip().startswith(cfg["install_prefixes"]))
    paras = [p.strip() for p in body.splitlines() if p.strip()]
    lens = [len(p) for p in paras]
    if lens:
        avg = sum(lens) / len(lens)
        longest = max(lens)
        if longest > cfg["max_paragraph"]:
            warns.append(f"有段落偏长：最长 {longest} 字（建议 ≤{cfg['max_paragraph']}）")
        else:
            passes.append(f"段落长度：平均 {avg:.0f} 字、最长 {longest} 字")

    # 3. 图片比例与体积
    imgs = re.findall(r"<img[^>]+src=\"([^\"]+)\"", html)
    ratios, missing = [], []
    total = 0
    for src in imgs:
        p = html_path.parent / src
        if not p.exists():
            missing.append(src)
            continue
        w, h = png_size(p)
        if h:
            ratios.append(round(w / h, 2))
        total += p.stat().st_size
    if missing:
        fails.append("图片缺失：" + "、".join(missing))
    if ratios:
        uniq = sorted(set(ratios))
        if len(uniq) > 1:
            fails.append(f"正文配图比例不一致：{uniq}")
        else:
            passes.append(f"配图比例一致：{uniq[0]}:1 × {len(ratios)} 张")
        mb = total / 1024 / 1024
        (passes if mb <= 3 else fails).append(f"配图总体积 {mb:.2f}MB（上限 3MB）")

    # 4. 结构完整性
    # 本期按链路组织，刻意不设「本文要点」；只校验必备的首尾模块
    for sec in ("导语", "结语", "免责声明"):
        if f"## {sec}" not in md:
            fails.append(f"缺少模块：{sec}")
    if not fails:
        passes.append("首尾模块齐全：导语、结语、免责声明（不设要点与往期推荐）")

    # 5. 内联样式（第一期版式：15px / 行高 1.75 / 字距 0.02em）
    if "letter-spacing: 0.02em" in html and "line-height: 1.75" in html:
        passes.append("正文内联样式已注入（15px / 行高 1.75 / 字距 0.02em）")
    else:
        fails.append("正文内联样式缺失")
    colors = set(re.findall(r"(?<![\w-])color:\s*(#[0-9A-Fa-f]{3,6})", html))
    bad = {c for c in colors if c.upper() not in cfg["colors"]}
    if bad:
        warns.append("出现约定外的文字颜色：" + "、".join(sorted(bad)))
    else:
        passes.append(f"文字颜色只用约定色：{'、'.join(sorted(colors))}")

    # 6. 标题候选（写在 Markdown 的 > 元信息里，口径见 references/titles.md）
    meta_lines = [l[2:].strip() for l in md.splitlines() if l.startswith("> ")]
    title_lines = [l for l in meta_lines if re.match(r"^[①-⑳]", l)]
    recommend_line = next((l for l in meta_lines if l.startswith("推荐标题")), "")
    rec_text = ""
    if recommend_line:
        rec_text = re.split(r"[（(｜|]", recommend_line.split("：", 1)[-1], maxsplit=1)[0].strip()
    title_problems = []
    if len(title_lines) < cfg["titles_min"]:
        title_problems.append(f"标题候选只有 {len(title_lines)} 条（要求 ≥{cfg['titles_min']} 条，含推荐与备选）")
    if not recommend_line:
        title_problems.append("元信息里缺少「推荐标题」一行")
    bang = sorted({w for w in cfg["title_ban"] for t in title_lines + [recommend_line] if w in t})
    if bang:
        title_problems.append("标题里出现标题党词：" + "、".join(bang))
    if title_problems:
        fails.extend(title_problems)
    else:
        passes.append(f"标题候选 {len(title_lines)} 条、推荐标题 {len(rec_text)} 字、无标题党词")
    if recommend_line and len(rec_text) > cfg["recommend_max_len"]:
        warns.append(f"推荐标题 {len(rec_text)} 字，建议 ≤{cfg['recommend_max_len']} 字（列表页容易截断）")

    # 7. AI 腔：硬禁用词 FAIL，慎用词超标 WARN（清单见 references/writing-craft.md）
    tone_text = md_body + "\n" + html_body
    hard = [(w, tone_text.count(w)) for w in cfg["ai_hard"]]
    hard = [(w, n) for w, n in hard if n]
    if hard:
        fails.append("出现 AI 腔硬禁用词：" + "、".join(f"{w}×{n}" for w, n in hard)
                     + "（换成人话，见 references/writing-craft.md）")
    soft = [(w, tone_text.count(w)) for w in cfg["ai_soft"]]
    soft_total = sum(n for _, n in soft)
    if soft_total > cfg["ai_soft_max"]:
        warns.append("AI 腔慎用词偏多：" + "、".join(f"{w}×{n}" for w, n in soft if n)
                     + f"（合计 {soft_total}，建议 ≤{cfg['ai_soft_max']}）")
    elif not hard:
        passes.append(f"无 AI 腔硬禁用词，慎用词 {soft_total} 处")

    # 8. 标点克制
    em = md_body.count("——")
    bangs = md_body.count("！")
    if em > cfg["em_dash_max"]:
        warns.append(f"破折号「——」用了 {em} 处（建议 ≤{cfg['em_dash_max']}）")
    if bangs > cfg["exclaim_max"]:
        warns.append(f"感叹号用了 {bangs} 处（建议 ≤{cfg['exclaim_max']}）")
    field_dash = Counter()
    for para in paras:
        m = re.match(r"^\*\*([^*]{1,12})\*\*[：:]\s*", para)
        if m and "——" in para:
            field_dash[m.group(1)] += 1
    if field_dash:
        worst, cnt = field_dash.most_common(1)[0]
        if cnt > cfg["field_dash_max"]:
            warns.append(f"字段「{worst}」有 {cnt} 条用「——」接续（模板痕迹，换几种句式）")
        elif em <= cfg["em_dash_max"] and bangs <= cfg["exclaim_max"]:
            passes.append(f"标点克制：破折号 {em} 处、感叹号 {bangs} 处")
    elif em <= cfg["em_dash_max"] and bangs <= cfg["exclaim_max"]:
        passes.append(f"标点克制：破折号 {em} 处、感叹号 {bangs} 处")

    # 9. 段落节奏与句式重复
    if len(lens) >= 3:
        flat = 0
        for i in range(2, len(lens)):
            trio = lens[i - 2:i + 1]
            if min(trio) >= 30 and (max(trio) - min(trio)) <= 0.15 * max(trio):
                flat += 1
        if flat > cfg["flat_run_max"]:
            warns.append(f"有 {flat} 处连续三段字数接近（节奏太平，拆一句短句）")
        else:
            passes.append("段落节奏：长短有交替")

    opens = []
    for para in paras:
        s = re.sub(r"^\*\*[^*]{1,12}\*\*[：:]\s*", "", para).strip("「『\"'“”")
        if len(s) >= 8:
            opens.append(s[:4])
    if opens:
        top, n = Counter(opens).most_common(1)[0]
        if n > cfg["repeat_max"]:
            warns.append(f"有 {n} 段以「{top}…」开头（句式重复，换几种起句）")
        else:
            passes.append(f"句式不重复：最高重复开头「{top}…」{n} 段")

    print("=" * 70)
    print(f"发布自检　{md_path.name} / {html_path.name}")
    print(f"结论：FAIL {len(fails)}　WARN {len(warns)}")
    print("-" * 70)
    for f in fails:
        print("[FAIL]", f)
    for w in warns:
        print("[WARN]", w)
    for p in passes:
        print("[PASS]", p)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

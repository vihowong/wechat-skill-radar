#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前自检：排版一致性、图片比例与体积、段落长度、必备模块、禁用元素。

用法：python qa.py 发布稿.md 公众号粘贴版.html

可配置（可选）：在项目根目录放一个 qa_config.json，覆盖默认值——
    {
      "forbidden": ["旧品牌名", "旧脚本名"],        // 出现即 FAIL
      "colors": ["#0E7C66", "#0F172A", ...],        // 正文允许出现的文字颜色
      "install_prefixes": ["**装它**"],             // 这些开头的段落是命令行，不计入长度
      "max_paragraph": 110
    }
不写就用下面的默认值；改版式时记得同步改 colors。
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

# 默认禁用词：自己账号的旧标识（旧品牌名、旧配色、旧脚本名）加到这里
DEFAULT_FORBIDDEN = ["往期推荐", "公众号名片", "扫码关注", "点击上方蓝字"]
DEFAULT_COLORS = {"#0E7C66", "#0F172A", "#1F2937", "#374151", "#6B7280", "#FFFFFF"}
DEFAULT_INSTALL_PREFIXES = ("**装它**",)
DEFAULT_MAX_PARAGRAPH = 110


def load_config(root: Path) -> dict:
    """读可选的 qa_config.json；没有就用默认值。"""
    cfg = {
        "forbidden": list(DEFAULT_FORBIDDEN),
        "colors": set(DEFAULT_COLORS),
        "install_prefixes": tuple(DEFAULT_INSTALL_PREFIXES),
        "max_paragraph": DEFAULT_MAX_PARAGRAPH,
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

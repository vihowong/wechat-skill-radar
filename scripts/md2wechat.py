#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 发布稿 → 公众号可直接粘贴的内联样式 HTML（本项目自有版式）。

支持：# 标题、> 元信息（转 HTML 注释）、## 小标题、### 三级标题、
普通段落、- 列表、**强调**、![图注](图片路径)、## 免责声明 / ## 往期推荐 / ## 平台引导。

用法：python md2wechat.py 发布稿.md 公众号粘贴版.html
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 版式：接入第一期（GitHub热门AI技能Skill合集）的排版设计
#   正文 15px / 行高 1.75 / 字距 0.02em；单一墨绿强调 #0E7C66；正文色 #1F2937、标题 #0F172A、小字 #6B7280
#   全程不声明 font-family（交给微信默认字体，与第一期一致）
ACCENT = "#0E7C66"
WRAP = "overflow-wrap: anywhere; word-break: break-word; "

BODY = (WRAP + "font-size: 15px; line-height: 1.75; letter-spacing: 0.02em; color: #1F2937; "
        "margin: 0 0 18px; text-align: justify;")
LI = (WRAP + "font-size: 15px; line-height: 1.75; letter-spacing: 0.02em; color: #1F2937; "
      "margin: 0 0 8px;")
LEAD = (WRAP + "font-size: 15px; line-height: 1.8; letter-spacing: 0.02em; color: #374151; "
        "margin: 0 0 10px;")
# 「装它」这类含命令的行：样式同正文，但不做两端对齐——否则命令里的空格会被拉出大缝
INSTALL = (WRAP + "font-size: 15px; line-height: 1.75; letter-spacing: 0.02em; color: #1F2937; "
           "margin: 0 0 18px; text-align: left;")
# 一级小标题：左侧 4px 墨绿竖条 + 10px 内缩
H1 = ("font-size: 19px; font-weight: 700; color: #0F172A; line-height: 1.5; margin: 0; "
      f"border-left: 4px solid {ACCENT}; padding-left: 10px;")
H2 = "font-size: 16px; font-weight: 700; color: #0F172A; line-height: 1.6; margin: 0;"
CAP = "font-size: 13px; line-height: 1.7; color: #6B7280; margin: 0 0 22px; text-align: center;"
# 免责声明与平台引导：13px / 行高 1.9 / #6B7280，不声明字体族
NOTE = "font-size: 13px; line-height: 1.9; color: #6B7280; margin: 0 0 3px;"
NOTE_ONE = "font-size: 13px; line-height: 1.9; color: #6B7280; margin: 0;"
PAST = WRAP + "font-size: 15px; line-height: 2; margin: 0;"
H_MARGIN = {1: "30px 0 12px", 2: "22px 0 10px", 3: "20px 0 8px"}
H_STYLE = {1: H1, 2: H2, 3: H2}
H_TAG = {1: "h2", 2: "h3", 3: "h4"}


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", rf'<strong style="color: {ACCENT};">\1</strong>', text)


def heading(text: str, level: int) -> list[str]:
    # 第一期的做法：标题一律纯文字，一级小标题靠 border-left 竖条区分
    return [f'<section style="margin: {H_MARGIN[level]};">',
            f'  <{H_TAG[level]} style="{H_STYLE[level]}">{inline(text)}</{H_TAG[level]}>',
            "</section>"]


def figure(path: str, caption: str) -> list[str]:
    # 官方截图与界面图可以不带图注：写 ![](配图/xxx.png)。外部素材（图库照片、官方图）必须
    # 在图注或紧跟的一行里署名，见 references/compliance.md。
    if caption:
        return ['<section style="text-align: center; margin: 0 0 8px;">',
                f'  <img src="{path}" alt="{caption}" style="width: 100%; height: auto; '
                'display: block; border-radius: 10px; border: 1px solid #E2E8F0;">',
                "</section>",
                f'<p style="{CAP}">图注：{inline(caption)}</p>']
    return ['<section style="text-align: center; margin: 0 0 22px;">',
            f'  <img src="{path}" alt="" style="width: 100%; height: auto; '
            'display: block; border-radius: 10px; border: 1px solid #E2E8F0;">',
            "</section>"]


class Converter:
    def __init__(self) -> None:
        self.title = ""
        self.meta: list[str] = []
        self.out: list[str] = []
        self.section = ""
        self.in_ul = False
        self.open_wrap = False
        self.lead_slot: int | None = None
        self.lead_used = 0

    def close_ul(self) -> None:
        if self.in_ul:
            self.out.append("</ul>")
            self.in_ul = False

    def open_ul(self) -> None:
        if not self.in_ul:
            self.out.append('<ul style="margin: 0 0 18px; padding-left: 1.2em;">')
            self.in_ul = True

    def close_wrap(self) -> None:
        self.close_ul()
        if self.open_wrap:
            self.out.append("</section>")
            self.open_wrap = False
            self.lead_slot = None

    def start_section(self, name: str) -> None:
        self.close_wrap()
        self.section = name
        if name == "导语":
            # 第一期：浅灰圆角卡片，无左边框
            self.out.append('<section style="background-color: #F8FAFC; border-radius: 10px; '
                            'padding: 16px 18px; margin: 0 0 24px;">')
            self.open_wrap = True
            self.lead_used = 0
        elif name == "本文要点":
            self.out += heading("本文要点", 2)
        elif name == "免责声明":
            self.out.append('<section style="margin: 30px 0 0;">')
            self.open_wrap = True
        elif name == "往期推荐":
            self.out += heading("往期推荐", 1)
        elif name == "平台引导":
            self.out.append('<section style="margin: 22px 0 0;">')
            self.open_wrap = True
        else:
            self.out += heading(name, 1)

    def push_text(self, text: str) -> None:
        self.close_ul()
        html = inline(text)
        if text.startswith("**装它**"):
            # 第一期没有色块，装它走正文段落，只是不做两端对齐
            self.out.append(f'<p style="{INSTALL}">{html}</p>')
        elif self.section == "导语" and self.lead_used < 3:
            self.out.append(f'  <p style="{LEAD}">{html}</p>')
            self.lead_used += 1
        elif self.section == "平台引导":
            self.out.append(f'  <p style="{NOTE_ONE}">{html}</p>')
        else:
            self.out.append(f'<p style="{BODY}">{html}</p>')

    def push_item(self, item: str) -> None:
        if self.section == "免责声明":
            self.out.append(f'  <p style="{NOTE}">{inline(item)}</p>')
            return
        if self.section == "往期推荐":
            m = re.match(r"^\[(.+?)\]\((.+?)\)$", item)
            if m:
                self.out.append(f'<p style="{PAST}">'
                                f'<span style="color: {ACCENT};">· </span>'
                                f'<a href="{m.group(2)}" style="text-decoration: none;">'
                                f'{inline(m.group(1))}</a></p>')
            else:
                self.out.append(f'<p style="{PAST}"><span style="color: {ACCENT};">· </span>'
                                f'{inline(item)}</p>')
            return
        self.open_ul()
        self.out.append(f'  <li style="{LI}">{inline(item)}</li>')

    def run(self, md: str) -> tuple[str, list[str], str]:
        for raw in md.splitlines():
            line = raw.rstrip()
            if line.startswith("# ") and not self.title:
                self.title = line[2:].strip()
                continue
            if line.startswith("> "):
                self.meta.append(line[2:].strip())
                continue
            if line.startswith("## "):
                self.start_section(line[3:].strip())
                continue
            if line.startswith("### "):
                self.close_ul()
                self.out += heading(line[4:].strip(), 3)
                continue
            if not line.strip():
                continue
            img = re.match(r"^!\[(.*?)\]\((.+?)\)$", line.strip())
            if img:
                self.close_ul()
                self.out += figure(img.group(2).strip(), img.group(1).strip())
                continue
            if line.startswith("- "):
                self.push_item(line[2:].strip())
                continue
            self.push_text(line.strip())
        self.close_wrap()
        return self.title, self.meta, "\n".join(self.out)


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  /* 本地预览外壳，复制进公众号时不要带上这段 CSS */
  body {{ margin: 0; background: #EEF1F5; padding: 24px 0; display: flex; justify-content: center; }}
  #stage {{ width: 375px; background: #fff; padding: 24px 20px 40px; box-sizing: border-box; }}
  /* 正文不声明 font-family（与微信一致），这里只给本地预览补一套系统字体，复制时不会带上 */
  #stage, #stage * {{ font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif; }}
</style>
</head>
<body>
{meta}
<div id="stage">

<!-- ===== 从这里开始，整段复制进公众号编辑器 ===== -->

{body}

<!-- ===== 复制范围到此结束 ===== -->

</div>
</body>
</html>
"""


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Markdown → 公众号 HTML")
    ap.add_argument("md")
    ap.add_argument("out")
    args = ap.parse_args()
    src = Path(args.md)
    if not src.exists():
        raise SystemExit(f"找不到文件：{src}")
    title, meta, body = Converter().run(src.read_text(encoding="utf-8"))
    html = PAGE.format(
        title=title,
        meta="".join(f"<!-- {m} -->\n" for m in meta),
        body=body,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"已生成 {out}（{out.stat().st_size / 1024:.1f} KB）")


if __name__ == "__main__":
    main()

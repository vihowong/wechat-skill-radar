#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 发布稿 → 公众号可直接粘贴的内联样式 HTML（本项目自有版式）。

支持：# 标题、> 元信息（转 HTML 注释）、## 小标题、### 三级标题、
`## 01 小标题` 的编号式章节（渲染成橙色大号编号 + 标题）、
普通段落、- 列表、**强调**、![图注](图片路径)、## 免责声明 / ## 往期推荐 / ## 平台引导。

用法：python md2wechat.py 发布稿.md 公众号粘贴版.html

版式来源：正文行高 2em / 字距 0.034em / 8px 缩进，以及"大号单色编号独占一行"的章节件，
都取自对标账号「逛逛GitHub」的实测规格（见 references/benchmark-guangguang-github.md）；
强调色仍用本账号的墨绿 #0E7C66，不抄它的橙色。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ACCENT = "#0E7C66"
WRAP = "overflow-wrap: anywhere; word-break: break-word; "
# 行高 2em + 8px 左右缩进：字不大但行距宽，手机上"透气"，这是对标账号最值得学的一条
LH = "line-height: 2em; "
LS = "letter-spacing: 0.034em; "

BODY = (WRAP + "font-size: 15px; " + LH + LS + "color: #1F2937; "
        "margin: 0 8px 16px; text-align: justify;")
LI = (WRAP + "font-size: 15px; " + LH + LS + "color: #1F2937; "
      "margin: 0 0 8px;")
LEAD = (WRAP + "font-size: 15px; line-height: 1.8; " + LS + "color: #374151; "
        "margin: 0 0 10px;")
# 「装它」这类含命令的行：样式同正文，但不做两端对齐——否则命令里的空格会被拉出大缝
INSTALL = (WRAP + "font-size: 15px; " + LH + LS + "color: #1F2937; "
           "margin: 0 8px 16px; text-align: left;")
# 章节编号：大号 + 单色 + 独占一行（对标做法），颜色用本账号强调色
NUM = (f"font-size: 28px; font-weight: 700; color: {ACCENT}; line-height: 1.2; "
       "letter-spacing: 1px; margin: 24px 8px 0;")
# 一级小标题：左侧 4px 墨绿竖条 + 10px 内缩（无编号的章节用它）
H1 = ("font-size: 19px; font-weight: 700; color: #0F172A; line-height: 1.5; margin: 0; "
      f"border-left: 4px solid {ACCENT}; padding-left: 10px;")
H2 = "font-size: 16px; font-weight: 700; color: #0F172A; line-height: 1.6; margin: 0;"
CAP = "font-size: 13px; line-height: 1.7; color: #6B7280; margin: 0 0 22px; text-align: center;"
# 行内命令：等宽 + 浅灰底，让"能照抄的东西"在一段话里一眼认出来
CODE = ("font-family: Consolas, Menlo, monospace; font-size: 0.92em; color: #0F172A; "
        "background-color: #F1F5F9; padding: 1px 5px; border-radius: 4px; "
        "overflow-wrap: anywhere; word-break: break-word;")
# 表格：选型指南的必答项。微信对 table 支持有限，所以全部内联、不用外边框，只用底色分行。
# 不用 table-layout:fixed —— 那会强制各列等宽，短列浪费空间、长列被迫折行。
TABLE = (WRAP + "width: 100%; border-collapse: collapse; margin: 0 8px 18px; "
         "font-size: 13px; line-height: 1.7;")
TH = (WRAP + "background-color: #F1F5F9; color: #0F172A; font-weight: 700; font-size: 13px; "
      "padding: 8px 6px; text-align: left; border-bottom: 2px solid #E2E8F0; "
      "vertical-align: top;")
TD = (WRAP + "color: #1F2937; font-size: 13px; padding: 8px 6px; "
      "border-bottom: 1px solid #E2E8F0; vertical-align: top;")
# 免责声明与平台引导：13px / 行高 1.9 / #6B7280，不声明字体族
NOTE = "font-size: 13px; line-height: 1.9; color: #6B7280; margin: 0 0 3px;"
NOTE_ONE = "font-size: 13px; line-height: 1.9; color: #6B7280; margin: 0;"
PAST = WRAP + "font-size: 15px; line-height: 2; margin: 0;"
H_MARGIN = {1: "30px 0 12px", 2: "22px 0 10px", 3: "20px 0 8px"}
H_STYLE = {1: H1, 2: H2, 3: H2}
H_TAG = {1: "h2", 2: "h3", 3: "h4"}

# 章节编号：`## 01 它是什么` 里的前导两位数字
SEC_NUM = re.compile(r"^(\d{2})\s*[.、:：]?\s+(.+)$")


def needs_left_align(text: str) -> bool:
    """判断这一段是否该改用左对齐（而不是两端对齐）。

    `text-align: justify` 在中文段落上很整齐，但只要段落里出现较长的西文串或命令，
    它就会把西文之间的空格、以及被西文挤开的中文字距全部拉开——视觉上变成
    「官 方 描 述 是 "Production-grade..."」这种散字，很难看。

    触发条件（任一成立就左对齐）：
      1. 含行内代码（`…`）——命令和参数一律左对齐；
      2. 含 ≥18 个连续 ASCII 字符的串（URL、英文长句、包名）；
      3. 整段 ASCII 占比超过 35%（英文为主的段落）。
    """
    if "`" in text:
        return True
    if re.search(r"[\x20-\x7e]{18,}", text):
        return True
    ascii_n = sum(1 for c in text if " " <= c <= "~")
    return bool(text) and ascii_n / len(text) > 0.35


def inline(text: str) -> str:
    """行内标记：**强调** → 墨绿加粗；`命令` → 等宽小字块（可照抄的东西要看得出来）。

    先转义，再依次处理反引号与星号——反引号里的内容不再走强调替换，
    否则 `npx add **x**` 这类命令会被改坏。
    """
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    codes: list[str] = []

    def _stash(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", _stash, text)
    text = re.sub(r"\*\*(.+?)\*\*", rf'<strong style="color: {ACCENT};">\1</strong>', text)
    for i, c in enumerate(codes):
        text = text.replace(f"\x00{i}\x00", f'<code style="{CODE}">{c}</code>')
    return text


def heading(text: str, level: int) -> list[str]:
    # 第一期的做法：标题一律纯文字，一级小标题靠 border-left 竖条区分
    return [f'<section style="margin: {H_MARGIN[level]};">',
            f'  <{H_TAG[level]} style="{H_STYLE[level]}">{inline(text)}</{H_TAG[level]}>',
            "</section>"]


def numbered_heading(num: str, text: str) -> list[str]:
    """编号式章节：大号单色编号独占一行 + 加粗标题。

    取自对标账号「逛逛GitHub」：编号是它最标志性的视觉件（32px、单色、独占一行），
    辨识度来自编号而不是标题本身——所以标题保持与正文同色，只大 1px 并加粗。
    我们的字号取 28px（比它的 32px 略收），颜色用本账号强调色墨绿。
    """
    return [f'<p style="{NUM}">{num}</p>',
            '<section style="margin: 6px 0 18px;">',
            f'  <h3 style="{H2}">{inline(text)}</h3>',
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
            m = SEC_NUM.match(name)
            if m:
                self.out += numbered_heading(m.group(1), m.group(2))
            else:
                self.out += heading(name, 1)

    def push_text(self, text: str) -> None:
        self.close_ul()
        html = inline(text)
        if self.section == "导语" and self.lead_used < 3:
            self.out.append(f'  <p style="{LEAD}">{html}</p>')
            self.lead_used += 1
        elif self.section == "平台引导":
            self.out.append(f'  <p style="{NOTE_ONE}">{html}</p>')
        elif needs_left_align(text):
            # 含命令或大段英文的段落不做两端对齐：justify 会把西文之间的空格拉开成大缝，
            # 中文也会被撑成「官 方 描 述 是」这种散字。
            self.out.append(f'<p style="{INSTALL}">{html}</p>')
        else:
            self.out.append(f'<p style="{BODY}">{html}</p>')

    @staticmethod
    def _split_row(line: str) -> list[str]:
        s = line.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        return [c.strip() for c in s.split("|")]

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

    def push_table(self, rows: list[list[str]]) -> None:
        """Markdown 表格 → 公众号可粘贴的表格。

        选型指南的必答项是"一张对比表"，没有表格支持就等于逼作者用图片代替，
        而表格里的数字应该是可复制、可核对的文本。
        微信编辑器对 table 支持有限，所以样式全部内联、去掉边框，只用底色分行。
        """
        if not rows:
            return
        # 手机宽度只有 375px，列数超过 4 列时每列不到 90px，中文会被折成两三个字一行。
        # 这里不拦（拦了作者没法交付），但把提示打到终端，让作者自己决定是否减列。
        if len(rows[0]) > 4:
            print(f"  提示：表格有 {len(rows[0])} 列，手机上每列偏窄，"
                  f"建议压到 4 列以内，或把长内容改成「维度 + 说明」两列。")
        head, body_rows = rows[0], rows[1:]
        cells = []
        cells.append("<thead><tr>")
        for c in head:
            cells.append(f'<th style="{TH}">{inline(c)}</th>')
        cells.append("</tr></thead><tbody>")
        for r in body_rows:
            cells.append("<tr>")
            for c in r:
                cells.append(f'<td style="{TD}">{inline(c)}</td>')
            cells.append("</tr>")
        cells.append("</tbody>")
        self.out.append(f'<table style="{TABLE}">{"".join(cells)}</table>')

    def run(self, md: str) -> tuple[str, list[str], str]:
        lines_all = md.splitlines()
        i = 0
        while i < len(lines_all):
            raw = lines_all[i]
            line = raw.rstrip()
            i += 1
            # 表格：当前行与下一行都以 | 开头，且下一行是分隔行（---）
            if line.strip().startswith("|") and i < len(lines_all):
                nxt = lines_all[i].strip()
                if re.fullmatch(r"\|[\s:|-]+\|", nxt) and "-" in nxt:
                    self.close_ul()
                    rows = [self._split_row(line)]
                    i += 1                                    # 跳过分隔行
                    while i < len(lines_all) and lines_all[i].strip().startswith("|"):
                        rows.append(self._split_row(lines_all[i]))
                        i += 1
                    self.push_table(rows)
                    continue
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

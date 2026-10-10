#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出图基础件：封面与配图都用它画，再交给 render.py 渲染成 PNG。

设计约定
  · 一期一个色系：深色底 + 一个主色 + 一个点缀色；配图尽量换骨架，只统一色板与页脚。
  · 中文用系统字体，绝不用 AI 生图——中文不会变形，改文案就是改代码。
  · 尺寸：封面 1276×544 / 543×544；配图 16:9 建议 1080×608。

用法（当库用）
    from design_kit import use_palette, page, figure_page, cover_page, svg_fixed, txt, rrect

    use_palette(mint="#3AC98F", mint_hi="#5CD971", orange="#FF7A59")   # 换成本期色系
    html = page("fig1", 1350, 760, body_html)          # 画布外壳（渐变底 + 点阵 + 暗角）
    open("pages/fig1.html", "w", encoding="utf-8").write(html)

用法（看效果）
    python design_kit.py demo         # 生成 demo/*.html，再用 render.py 渲染
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT = Path.cwd()

# ---------------------------------------------------------------- 默认色板
# 深色底 → 主色 → 点缀色。use_palette() 可以整体换掉。
DEEP = "#0A1019"      # 最深的底
NAVY = "#101928"
MID = "#16333A"       # 中间过渡
BASE = "#204740"      # 底色亮端
BASE_L = "#2A4F49"
MINT = "#3AC98F"      # 主色
MINT_HI = "#5CD971"   # 主色提亮
MINT_D = "#1E8F66"    # 主色暗调（描边/填充）
ORANGE = "#FF7A59"    # 点缀色（数字、警示、星光）
TXT = "#FFFFFF"
SUB = "#93A3BC"
DIM = "#5C7086"
LINE = "rgba(255,255,255,.08)"

FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif'
MONO = '"Cascadia Mono", "Consolas", monospace'


def use_palette(**kw) -> None:
    """换本期色系，例如 use_palette(mint="#0E7C66", mint_hi="#16A34A", orange="#F97316")。"""
    g = globals()
    for k, v in kw.items():
        name = k.upper()
        if name not in g:
            raise KeyError(f"未知色名：{k}")
        g[name] = v


# ------------------------------------------------ 配色：从素材照片里取色
# 逻辑：底子（DEEP→BASE_L）从照片最暗的那一族色相里拉出一条明度阶，保证画面同源；
# 主色（MINT）取照片里最有存在感的高饱和色；点缀（ORANGE）取画面里的第二色相，
# 没有第二色相就用主色的互补色。这样"照片 + 文字"永远在同一套色系里，
# 不会出现照片冷、标题暖各说各话的情况。用法见 references/visual-recipes.md 第四节。

def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb) -> str:
    r, g, b = (max(0, min(255, int(round(v)))) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _hls(color: str) -> tuple[float, float, float]:
    import colorsys
    r, g, b = hex_to_rgb(color)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)  # (h, l, s)


def _from_hls(h: float, l: float, s: float) -> str:
    import colorsys
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return rgb_to_hex((r * 255, g * 255, b * 255))


def _luminance(color: str) -> float:
    def channel(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hex_to_rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 对比度。正文 ≥4.5，大标题 ≥3.0 就够看。"""
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(fg: str, bg: str, target: float = 4.5) -> str:
    """把前景色往亮/往暗推到目标对比度，返回新色值（不满足就返回最接近的）。"""
    if contrast_ratio(fg, bg) >= target:
        return fg.upper()
    h, l, s = _hls(fg)
    bg_dark = _luminance(bg) < 0.5
    for step in range(1, 21):
        nl = l + step * 0.045 if bg_dark else l - step * 0.045
        if not 0 <= nl <= 1:
            break
        cand = _from_hls(h, nl, s)
        if contrast_ratio(cand, bg) >= target:
            return cand.upper()
    return "#FFFFFF" if bg_dark else "#000000"


def palette_from_photo(path, sample: int = 8, deep_l: float = 0.055, base_l: float = 0.30) -> dict:
    """从素材照片里抽出一套能直接 use_palette 的色板。

    返回 dict：deep / navy / mid / base / base_l / mint / mint_hi / mint_d / orange。
    需要 Pillow；读不出图时退回当前默认色板。
    """
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return {}
    try:
        im = Image.open(path).convert("RGB")
        im.thumbnail((240, 240))
        quant = im.quantize(colors=sample, method=Image.Quantize.FASTOCTREE)
        pal = quant.getpalette() or []
        entries = [(cnt, tuple(pal[i * 3:i * 3 + 3])) for cnt, i in quant.getcolors()]
    except Exception:  # noqa: BLE001
        return {}
    if not entries:
        return {}
    entries.sort(reverse=True)
    total = sum(c for c, _ in entries) or 1
    cols = [(c / total, rgb_to_hex(rgb)) for c, rgb in entries]

    # 底色：占比最高的那一族里，取明度最低的色相当骨架
    dark_key = min((hexv for _, hexv in cols), key=lambda c: _luminance(c))
    h_base, _, s_base = _hls(dark_key)
    sat_base = min(0.42, max(0.10, s_base * 0.85))
    palette = {
        "deep": _from_hls(h_base, deep_l, sat_base * 0.7),
        "navy": _from_hls(h_base, deep_l + 0.035, sat_base * 0.85),
        "mid": _from_hls(h_base, (deep_l + base_l) / 2, sat_base),
        "base": _from_hls(h_base, base_l, sat_base),
        "base_l": _from_hls(h_base, min(0.42, base_l + 0.06), sat_base),
    }

    # 主色：饱和度高、又不太暗的那个色相
    def accent_score(hexv: str) -> float:
        _, l, s = _hls(hexv)
        return s * (0.35 + l)
    h_acc, l_acc, s_acc = _hls(max((hexv for _, hexv in cols), key=accent_score))
    sat_acc = max(0.55, s_acc)
    palette["mint"] = _from_hls(h_acc, max(0.52, min(0.62, l_acc)), sat_acc)
    palette["mint_hi"] = _from_hls(h_acc, min(0.78, max(0.66, l_acc + 0.14)), sat_acc)
    palette["mint_d"] = _from_hls(h_acc, max(0.34, min(0.46, l_acc - 0.12)), sat_acc)

    # 点缀色：优先用照片里的第二个色相，没有就用主色的互补色
    others = [hexv for _, hexv in cols
              if abs((_hls(hexv)[0] - h_acc + 0.5) % 1.0 - 0.5) > 0.16]
    if others:
        h_alt = _hls(max(others, key=accent_score))[0]
    else:
        h_alt = h_acc + 0.5
    palette["orange"] = _from_hls(h_alt, 0.64, 0.78)

    # 明度校准：色相照照片走，明度按可读性推（并封顶，避免主色被推成白色）。
    # 大字用 3.0 就够，正文小字才需要 4.5。
    palette["mint"] = ensure_contrast(palette["mint"], palette["base_l"], 3.0)
    palette["mint_hi"] = ensure_contrast(palette["mint_hi"], palette["base_l"], 3.5)
    palette["mint_d"] = palette["mint_d"].upper()
    palette["orange"] = ensure_contrast(palette["orange"], palette["base_l"], 3.2)
    return palette


def use_palette_from_photo(path, **overrides) -> dict:
    """从照片取色并直接换掉本期色板；overrides 可再手动压某一项（如 orange="#FF7A59"）。"""
    pal = palette_from_photo(path)
    pal.update(overrides)
    if pal:
        use_palette(**pal)
    return pal


def contrast_report(bg: str | None = None) -> list[tuple[str, float]]:
    """对比度体检：标题/正文/点缀色在底色上是否够看（正文 ≥4.5，大字 ≥3.0）。

    不传 bg 就把最暗端（DEEP）和亮端（BASE_L）都测一遍——封面文字压在上面时，
    照片被压暗的区域接近 DEEP，卡片区域接近 BASE_L，两边都要过。
    """
    bgs = [bg] if bg else [DEEP, BASE_L]
    rows: list[tuple[str, float]] = []
    for b in bgs:
        print(f"底色 {b}：")
        for name, color in (("大标题 TXT", TXT), ("主色标题 MINT_HI", MINT_HI),
                            ("主色 MINT", MINT), ("次级文案 SUB", SUB),
                            ("点缀 ORANGE", ORANGE)):
            ratio = contrast_ratio(color, b)
            flag = "OK" if ratio >= 4.5 else ("大字可用" if ratio >= 3.0 else "偏弱，换色值")
            print(f"  {name:<18} {ratio:4.2f}:1  {flag}")
            rows.append((f"{name}@{b}", ratio))
    return rows


# ---------------------------------------------------------------- 基础图形
def svg(w, h, body, defs=""):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" '
            f'xmlns="http://www.w3.org/2000/svg" font-family=\'{FONT}\'>{defs}{body}</svg>')


def svg_fixed(w, h, body, defs=""):
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'xmlns="http://www.w3.org/2000/svg" font-family=\'{FONT}\'>{defs}{body}</svg>')


def glow_defs(colors, blur=7):
    """文字/面块发光。注意：水平或垂直的细线用它会被裁掉（包围盒高度 0），线条请用 path(glow=True)。"""
    d = "<defs>"
    for c in colors:
        cid = c.replace("#", "")
        d += (f'<filter id="gl-{cid}" x="-60%" y="-60%" width="220%" height="220%">'
              f'<feGaussianBlur stdDeviation="{blur}" result="b"/>'
              f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    return d + "</defs>"


def arrow_defs(colors):
    """箭头定义。配图是单独一层 SVG，必须把它一起传给 svg_fixed/svg，否则 marker-end 不显示也不报错。"""
    d = ""
    for i, c in enumerate(colors):
        d += (f'<marker id="ar{i}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" '
              f'markerHeight="6" orient="auto-start-reverse">'
              f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    return d


def txt(x, y, s, size=14, fill=None, weight="400", anchor="start", family=None, ls=None,
        op=None, stroke=None, sw=0, glow=None):
    fam = f' font-family="{family}"' if family else ""
    lsp = f' letter-spacing="{ls}"' if ls else ""
    o = f' fill-opacity="{op}"' if op is not None else ""
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    g = f' filter="url(#gl-{glow.replace("#", "")})"' if glow else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill or TXT}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{fam}{lsp}{o}{st}{g}>{s}</text>')


# ------------------------------------------------------ 大字报：串联排版
def _adv_units(ch: str) -> float:
    """字符宽度（以字号为单位）：中文/全角按 1，ASCII 按 0.6，空格按 0.35。"""
    if ch == " ":
        return 0.35
    return 0.6 if ord(ch) < 0x2E80 else 1.0


def _chain_layout(s: str, size: float, gap_ratio: float):
    """算出一行里每个字的落点与整行宽度，供 chain_line 使用。"""
    gap = size * gap_ratio
    pos, cursor = [], 0.0
    for i, ch in enumerate(s):
        w = _adv_units(ch) * size
        pos.append((ch, cursor, w))
        cursor += w + (gap if i < len(s) - 1 else 0)
    return pos, cursor


def chain_line(x, y, s, size, color=None, dot_color=None, gap_ratio=0.18, align="start",
               weight="800", dot_ratio=0.055, hi_color=None, hi_words=(), glow=None, op=1.0):
    """一行"大字报"串联字：逐字排布，字间用小圆点串起来。

    hi_words —— 要点亮的字/词（用主色），对应位置同时发光
    返回 (svg 片段, 整行宽度)，宽度可用来做自动字号。
    """
    pos, total = _chain_layout(s, size, gap_ratio)
    start = x - total / 2 if align == "middle" else (x - total if align == "end" else x)
    gap = size * gap_ratio
    flags = [False] * len(pos)
    for word in hi_words or ():
        if not word:
            continue
        idx = s.find(word)
        while idx >= 0:
            for k in range(idx, idx + len(word)):
                flags[k] = True
            idx = s.find(word, idx + len(word))
    body = ""
    for i, (ch, off, w) in enumerate(pos):
        lit = flags[i] and hi_color
        if ch != " ":
            body += txt(start + off, y, ch, size, lit or color, weight, "start",
                        glow=(glow if lit else None), op=op)
        if i < len(pos) - 1:
            body += circle(start + off + w + gap / 2, y - size * 0.33,
                           max(1.5, size * dot_ratio), dot_color or color, op=0.9)
    return body, total


def rrect(x, y, w, h, r, fill, stroke="none", sw=1.5, dash=None, op=None, glow=None, extra=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' fill-opacity="{op}"' if op is not None else ""
    g = f' filter="url(#gl-{glow.replace("#", "")})"' if glow else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}{o}{g}{extra}/>')


def circle(cx, cy, r, fill, stroke="none", sw=1.5, op=None, glow=None):
    o = f' fill-opacity="{op}"' if op is not None else ""
    g = f' filter="url(#gl-{glow.replace("#", "")})"' if glow else ""
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{o}{g}/>')


def path(d, color, sw=2.5, dash=None, marker=None, glow=False, op=None, cap="round"):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    mk = f' marker-end="url(#{marker})"' if marker else ""
    # 线条发光一律用 drop-shadow：直线包围盒高度为 0，feGaussianBlur 滤镜会把它整条裁掉
    g = f' style="filter:drop-shadow(0 0 7px {color})"' if glow else ""
    o = f' stroke-opacity="{op}"' if op is not None else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="{cap}" stroke-linejoin="round"{ds}{mk}{g}{o}/>')


def line(x1, y1, x2, y2, color=None, sw=1.5, dash=None, cap="round"):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color or LINE}" '
            f'stroke-width="{sw}" stroke-linecap="{cap}"{ds}/>')


def dot_grid(w, h, pitch=34, color="#FFFFFF", op=0.035, r=1.3):
    """细点阵。间距太密会显著增加 PNG 体积——34 左右就够，22 是上限。"""
    out = ""
    y = pitch
    while y < h:
        x = pitch
        while x < w:
            out += circle(x, y, r, color, op=op)
            x += pitch
        y += pitch
    return out


def rgba(hex_color: str, alpha: float) -> str:
    """#3AC98F + 0.12 → rgba(58,201,143,.12)，用于描边与浅底。"""
    c = hex_color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def spark(x, y, s, color=None, op=0.95, glow=False):
    """四角星光：点缀色只用在这种小面积元素上。"""
    c = color or ORANGE
    k = s * 0.2
    d = (f"M{x},{y - s} L{x + k},{y - k} L{x + s},{y} L{x + k},{y + k} "
         f"L{x},{y + s} L{x - k},{y + k} L{x - s},{y} L{x - k},{y - k} Z")
    g = f' filter="url(#gl-{c.replace("#", "")})"' if glow else ""
    return f'<path d="{d}" fill="{c}" fill-opacity="{op}"{g}/>'


def dots3(x, y, filled, total=3, gap=15, r=5, color=None):
    """上手门槛：●○○ / ●●○ / ●●●。"""
    c = color or MINT
    out = ""
    for i in range(total):
        if i < filled:
            out += circle(x + i * gap, y, r, c)
        else:
            out += circle(x + i * gap, y, r, "none", "rgba(255,255,255,.35)", 1.6)
    return out


def panel(x, y, w, h, r=14, fill="rgba(255,255,255,.035)", stroke=None):
    return rrect(x, y, w, h, r, fill, stroke or LINE, 1.4)


def bullet(x, y, text, size=13, fill=None, dotc=None):
    return (circle(x, y - size * 0.3, 3, dotc or MINT)
            + txt(x + 12, y, text, size, fill or SUB, "500"))


def doc_icon(x, y, s=1.0, color=None):
    c = color or MINT
    return (rrect(x, y, 34 * s, 44 * s, 5 * s, "none", c, 2)
            + line(x + 8 * s, y + 14 * s, x + 26 * s, y + 14 * s, c, 2 * s)
            + line(x + 8 * s, y + 23 * s, x + 26 * s, y + 23 * s, c, 2 * s)
            + line(x + 8 * s, y + 32 * s, x + 20 * s, y + 32 * s, c, 2 * s))


def card_stack(cx, cy, s=1.0, op=1.0):
    """卡片堆叠图形（可直接当封面左侧的标记用，也可以自己画一个）。"""
    out = ""
    w, h = 168 * s, 116 * s
    offs = [(-34, 22, -9), (-17, 11, -4.5), (0, 0, 0)]
    cols = [DIM, MINT_D, MINT]
    for (dx, dy, rot), c in zip(offs, cols):
        out += (f'<g transform="translate({cx + dx * s},{cy + dy * s}) rotate({rot})">'
                + rrect(-w / 2, -h / 2, w, h, 16 * s, "rgba(10,20,30,.55)", c, 2.0, op=op)
                + line(-w / 2 + 18 * s, -h / 2 + 30 * s, w / 2 - 30 * s, -h / 2 + 30 * s, c, 3 * s)
                + line(-w / 2 + 18 * s, -h / 2 + 48 * s, w / 2 - 60 * s, -h / 2 + 48 * s, c, 2 * s)
                + line(-w / 2 + 18 * s, -h / 2 + 64 * s, w / 2 - 44 * s, -h / 2 + 64 * s, c, 2 * s)
                + "</g>")
    return out


# ---------------------------------------------------------------- 画布外壳
SHELL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: {deep}; }}
  body {{ font-family: {font}; color: {txt}; -webkit-font-smoothing: antialiased; }}
  .canvas {{
    position: relative; overflow: hidden; width: {w}px; height: {h}px;
    background:
      radial-gradient(110% 130% at 6% -10%, rgba(58,201,143,.20) 0%, rgba(58,201,143,0) 46%),
      radial-gradient(90% 110% at 100% 108%, rgba(255,122,89,.10) 0%, rgba(255,122,89,0) 55%),
      linear-gradient(133deg, {base_l} 0%, {base} 18%, {mid} 46%, {navy} 74%, {deep} 100%);
  }}
  .grid {{ position: absolute; inset: 0; }}
  .vignette {{ position: absolute; inset: 0;
    background: radial-gradient(120% 120% at 50% 40%, rgba(0,0,0,0) 40%, rgba(4,8,14,.55) 100%); }}
</style>
</head>
<body><div class="canvas">
{body}
</div></body>
</html>"""


def photo_bg(photo, dark=0.6, blur=0.0, focus="left"):
    """照片底图 + 色板遮罩：照片压暗、统一色偏后，正文与标题才压得住。

    photo 传相对路径时以写出的 HTML 文件为基准（pages/xxx.html 引素材用 "../../素材/图库/xx.jpg"）。
    dark 越大越暗（0.5 干净的场景照，0.7–0.8 画面很杂或文字很多时）。
    blur 给背景一点柔化（2–4px 够），画面越花越有用——文字会更跳出来。
    focus  "left" 左重右轻（封面用：左边压暗放标题，右边留出照片）；
           "uniform" 整屏均匀压暗（配图用：文字和图形铺满时要保证哪一块都能读）。
    压暗分两层：色板色偏 + 一层纯黑渐变，避免照片里的高亮细节跟标题抢注意力。
    """
    tint = round(min(1.0, dark * 0.62), 3)              # 色板色偏，保住账号色
    if focus == "uniform":
        shade = round(min(0.95, 0.32 + dark * 0.66), 3)
        scrim = (f"linear-gradient(180deg,rgba(4,8,14,{shade}) 0%,"
                 f"rgba(4,8,14,{round(min(0.97, shade + 0.06), 3)}) 100%)")
    else:
        scrim = (f"linear-gradient(100deg,"
                 f"rgba(4,8,14,{round(min(0.97, 0.55 + dark * 0.55), 3)}) 0%,"
                 f"rgba(4,8,14,{round(min(0.92, 0.32 + dark * 0.46), 3)}) 46%,"
                 f"rgba(4,8,14,{round(min(0.85, dark * 0.38), 3)}) 100%)")
    return (
        f'<div style="position:absolute;inset:0;background-image:url(\'{photo}\');'
        f'background-size:cover;background-position:center;'
        f'filter:saturate(.75) brightness(.85) contrast(1.04)'
        f'{f" blur({blur:g}px)" if blur else ""}"></div>'
        f'<div style="position:absolute;inset:0;background:'
        f'linear-gradient(133deg,{rgba(BASE_L, tint)} 0%,{rgba(MID, tint)} 46%,'
        f'{rgba(DEEP, tint)} 100%),'
        f'radial-gradient(110% 130% at 6% -10%,{rgba(MINT, .16)} 0%,rgba(MINT, 0) 46%)"></div>'
        f'<div style="position:absolute;inset:0;background:{scrim}"></div>'
    )


def page(title, w, h, body, grid=True, pitch=34, gop=0.035, photo=None, dark=0.6, blur=0.0,
         focus="left"):
    layers = ""
    if photo:
        layers += photo_bg(photo, dark, blur, focus)
    if grid:
        layers += f'<div class="grid">{svg_fixed(w, h, dot_grid(w, h, pitch=pitch, op=gop))}</div>'
    layers += '<div class="vignette"></div>'
    return SHELL.format(title=title, w=w, h=h, font=FONT, txt=TXT, base_l=BASE_L, base=BASE,
                        mid=MID, navy=NAVY, deep=DEEP, body=layers + body)


# ---------------------------------------------------------------- 画框与封面
def figure_page(w, h, code, category, title, art, footer_left="", footer_total=7,
                photo=None, dark=0.78, blur=2.0, focus="uniform"):
    """配图画框：左上 F 角标 + 类别 + 大标题，中部是 art（另画），底部 mono 页脚。

    photo 给了照片时，照片只做底图（会被压暗到 dark），文字与图形仍然靠代码画。
    """
    defs = glow_defs([MINT, MINT_HI, ORANGE]) + arrow_defs([MINT, ORANGE])
    head = svg_fixed(
        320, 60,
        rrect(0, 0, 58, 58, 14, "rgba(58,201,143,.16)", "rgba(58,201,143,.6)", 1.6)
        + txt(29, 38, code, 20, MINT_HI, "800", "middle")
        + txt(78, 27, category, 15, SUB, "600")
        + txt(78, 50, footer_left or "本次收录", 12.5, DIM, "500"),
        glow_defs([MINT_HI]))
    title_svg = svg_fixed(w - 120, 70, txt(0, 46, title, 42, TXT, "800"))
    body = f"""
  <div style="position:absolute;left:60px;top:50px">{head}</div>
  <div style="position:absolute;left:60px;top:150px">{title_svg}</div>
  <div style="position:absolute;left:0;top:230px;width:{w}px;height:{h - 350}px">{svg_fixed(w, h - 350, art, defs)}</div>
  <div style="position:absolute;left:60px;right:60px;bottom:26px">
    {svg_fixed(w - 120, 34, line(0, 2, w - 120, 2, LINE, 1.2))}
    <div style="display:flex;justify-content:space-between;margin-top:10px">
      <span style="font-family:{MONO};font-size:11.5px;letter-spacing:.1em;color:#5C7086">{footer_left} · {code}</span>
      <span style="font-family:{MONO};font-size:11.5px;letter-spacing:.1em;color:#5C7086">{code} / {footer_total:02d}</span>
    </div>
  </div>
"""
    return page(code, w, h, body, photo=photo, dark=dark, blur=blur, focus=focus)


def cover_page(w, h, mark_svg, eyebrow, title, subtitle, chips, footer_left,
               brand_line="", highlight=None, layout=None, photo=None, dark=0.62):
    """封面骨架，按尺寸自动切两种版式。

    wide（2.35:1，1276×544）：左侧图形 + 右侧左对齐标题，标题下一条主色短下划线
    square（1:1，543×544）：顶部徽标 + 居中标题 + 一行分类标签 + 下方图形

    mark_svg  —— 左侧/下方的图形（SVG 片段，例如 card_stack(...)）
    title     —— 用 \\n 换行，例如 "按你要干的活\\n挑 10 个 AI 技能"
    highlight —— 标题里要换主色点亮的片段，例如 "10"
    chips     —— ["画图", "写字", …] 渲染成一排圆角标签
    photo     —— 可商用照片的相对路径（做底图，会被压暗）；文字与图形仍是代码画的
    """
    wide = (layout or ("wide" if w / h > 1.6 else "square")) == "wide"
    head = "<br>".join(title.split("\n"))
    if highlight and highlight in head:
        head = head.replace(
            highlight,
            f'<span style="color:{MINT};text-shadow:0 0 {30 if wide else 24}px {rgba(MINT, .55)}">'
            f'{highlight}</span>')
    title_size = 62 if wide else 42
    chip_html = "".join(f'<span class="c">{c}</span>' for c in chips)
    eyebrow_html = (
        f'<span style="display:inline-flex;align-items:center;gap:9px;'
        f'border:1.4px solid {rgba(MINT, .5)};background:{rgba(MINT, .12)};color:{MINT_HI};'
        f'font-size:{15 if wide else 12.5}px;font-weight:700;letter-spacing:.14em;'
        f'padding:{8 if wide else 7}px {20 if wide else 16}px;border-radius:999px;">'
        f'<i style="width:8px;height:8px;background:{MINT_HI};border-radius:2px;'
        f'display:inline-block"></i>{eyebrow}</span>')

    if wide:
        mark_box, text_left, text_right = (40, 120, 380, 340), 432, 60
        y_eyebrow, y_title, y_rule, y_sub, y_chips = 96, 158, 318, 343, 398
        align, rule_w = "left", 74
    else:
        mark_box, text_left, text_right = (0, 300, w, 150), 0, 0
        y_eyebrow, y_title, y_rule, y_sub, y_chips = 38, 104, 238, 258, 296
        align, rule_w = "center", 66

    mx, my, mw, mh = mark_box
    box = f'position:absolute;left:{mx}px;top:{my}px;width:{mw}px;height:{mh}px;text-align:center;'

    def block(top: int, extra: str = "") -> str:
        """文本块统一定位：left/right 给宽，top 定位，样式串一定以分号收尾。"""
        return (f'position:absolute;left:{text_left}px;right:{text_right}px;top:{top}px;'
                f'text-align:{align};{extra}')

    rule_left = f'left:{text_left}px;' if wide else 'left:50%;transform:translateX(-50%);'
    body = f"""
  <div style="{box}">{svg_fixed(mw, mh, mark_svg, glow_defs([MINT, ORANGE, MINT_HI]))}</div>
  <div style="{block(y_eyebrow)}">{eyebrow_html}</div>
  <div style="{block(y_title, f'font-size:{title_size}px;font-weight:800;line-height:{1.16 if wide else 1.24};')}">{head}</div>
  <div style="position:absolute;{rule_left}top:{y_rule}px;width:{rule_w}px;
              height:{6 if wide else 5}px;border-radius:3px;
              background:linear-gradient(90deg,{MINT_HI},{MINT});"></div>
  <div style="{block(y_sub, f'font-size:{22 if wide else 15}px;color:#93A3BC;')}">{subtitle}</div>
  <div class="chips">{chip_html}</div>
  <div style="position:absolute;left:60px;right:60px;bottom:30px;display:flex;
              align-items:center;justify-content:space-between">
    <span style="font-family:{MONO};font-size:11px;letter-spacing:.13em;color:#5C7086">{footer_left}</span>
    <span style="font-size:13px;color:#C8D6E5">{brand_line}</span>
  </div>
"""
    css = f"""
  .chips {{ position: absolute; left: 0; right: 0; top: {y_chips}px; display: flex; gap: 8px;
           justify-content: {'flex-start' if wide else 'center'};
           {'padding-left: 432px;' if wide else ''} }}
  .chips .c {{ display: inline-flex; align-items: center; height: {'34' if wide else '28'}px;
              padding: 0 {'18' if wide else '11'}px; border: 1.4px solid {rgba(MINT, .45)};
              border-radius: 999px; background: {rgba(MINT, .07)}; color: #FFFFFF;
              font-size: {'15' if wide else '12.5'}px; font-weight: 600; }}
  .chips .c::before {{ content: ""; width: {'7' if wide else '6'}px; height: {'7' if wide else '6'}px;
              border-radius: 50%; background: {MINT}; margin-right: {'9' if wide else '6'}px; }}
"""
    return page("cover", w, h, body, photo=photo, dark=dark).replace("</style>", css + "</style>")


def poster_cover_page(w, h, photo, title, subtitle="", tags=None, footer_left="",
                      brand_line="", kicker="", hi_words=(), dark=0.80, layout=None,
                      rail=True, chain=True, blur=2.5, stair=0.14, hi_color=None):
    """大字报封面：整屏素材照片做底，主标题按行大字串联，左侧竖线把各行串成一条动线。

    title    —— 用 \\n 分行；每行 4–7 字最稳（越长字号自动变小）
    hi_words —— 要换主色点亮的字或词，例如 ["41 分钟"]，也可以直接传字符串
    hi_color —— 点亮用的颜色，默认主色 MINT_HI；主色偏浅（跟白色差别不大）时传点缀色更跳
    kicker   —— 标题上方的一行小标签（短）
    tags     —— 标题下方的一行关键词，渲染成「A · B · C」
    chain    —— True 时字与字之间用小圆点串联（每行建议 ≤7 字，太长就关掉）
    rail     —— 左侧一条竖线 + 每行一个节点，形成阅读动线
    stair    —— 每行相对上一行右移的比例（相对字号），做出阶梯式串联；0 就是齐头排
    blur     —— 背景柔化像素数；画面很花时 2–4 会让大字更跳
    """
    wide = (layout or ("wide" if w / h > 1.6 else "square")) == "wide"
    lines = [ln.strip() for ln in str(title).split("\n") if ln.strip()]
    if not lines:
        lines = [""]
    hi = [hi_words] if isinstance(hi_words, str) else list(hi_words or ())
    tags = list(tags or ())
    hi_color = hi_color or MINT_HI

    pad = 76 if wide else 36
    rail_x = pad + 8
    text_x = rail_x + (44 if rail else 0)
    avail = w - text_x - pad
    gap_ratio = 0.18 if chain else 0.02

    units = [sum(_adv_units(c) for c in ln) + gap_ratio * max(0, len(ln) - 1) for ln in lines]
    max_size, min_size = (108.0, 38.0) if wide else (64.0, 28.0)
    size = round(max(min_size, min(max_size, avail / (max(units) or 1))), 1)

    line_h = size * 1.16
    sub_size = 21 if wide else 15
    tag_size = 15 if wide else 12.5
    block_h = line_h * len(lines) + (44 if subtitle else 0) + (32 if tags else 0)
    y0 = (h - block_h) / 2 + size * 0.80
    y_last = y0 + (len(lines) - 1) * line_h

    sub_color = ensure_contrast(SUB, DEEP, 4.5)
    tag_color = ensure_contrast(DIM, DEEP, 4.0)

    art = ""
    # 左侧动线：竖线 + 每行一个节点（节点与点亮词同色，一张图里只出现一个强调色）
    if rail:
        top, bottom = y0 - size * 0.36, y_last - size * 0.36
        if bottom - top > 2:
            art += line(rail_x, top, rail_x, bottom, rgba(hi_color, 0.45), 3)
        for i in range(len(lines)):
            cy = y0 + i * line_h - size * 0.36
            art += circle(rail_x, cy, max(4.0, size * 0.07), hi_color, glow=hi_color)
    else:
        art += rrect(rail_x - 4, y0 - size * 0.86, 6, size * 0.95, 3, hi_color)

    if kicker:
        art += line(text_x, y0 - size * 1.30, text_x + 26, y0 - size * 1.30, hi_color, 3)
        art += txt(text_x + 38, y0 - size * 1.24, kicker, 15 if wide else 12.5,
                   ensure_contrast(SUB, DEEP, 4.5), "600", ls=".12em")

    for i, ln in enumerate(lines):
        y = y0 + i * line_h
        x = text_x + (size * stair * i if stair else 0)
        if chain:
            part, _ = chain_line(x, y, ln, size, TXT, hi_color, gap_ratio,
                                 hi_color=hi_color, hi_words=hi, glow=hi_color)
            art += part
        else:
            art += txt(x, y, ln, size, TXT, "800", ls=".02em")

    y_sub = y_last + (58 if wide else 40)
    if subtitle:
        art += txt(text_x, y_sub, subtitle, sub_size, sub_color, "500")
    if tags:
        art += txt(text_x, y_sub + (34 if subtitle else 0), " · ".join(tags),
                   tag_size, tag_color, "600", ls=".06em")

    body = (f'<div style="position:absolute;left:0;top:0;width:{w}px;height:{h}px">'
            f'{svg_fixed(w, h, art, glow_defs([MINT_HI, MINT, ORANGE, TXT, hi_color]))}</div>'
            f'<div style="position:absolute;left:{pad}px;right:{pad}px;bottom:28px;display:flex;'
            f'align-items:center;justify-content:space-between">'
            f'<span style="font-family:{MONO};font-size:11.5px;letter-spacing:.13em;'
            f'color:{tag_color}">{footer_left}</span>'
            f'<span style="font-size:13px;color:{ensure_contrast(SUB, DEEP, 4.5)}">{brand_line}</span>'
            f"</div>")
    return page("cover-poster", w, h, body, photo=photo, dark=dark, blur=blur)


# ---------------------------------------------------------------- 看效果
def demo() -> None:
    demo_dir = OUT / "demo"
    demo_dir.mkdir(exist_ok=True)

    mark = card_stack(240, 268, 1.25) + spark(392, 168, 13, glow=True)
    cover2 = cover_page(
        1276, 544, mark, eyebrow="10 个热门 AI 技能",
        title="按你要干的活\n挑 10 个 AI 技能", highlight="10",
        subtitle="五类活，各 2 个，附安装命令",
        chips=["画图", "写字", "查资料", "写代码", "记事"],
        footer_left="GITHUB SNAPSHOT · 2026-01-01", brand_line="● 你的账号名")
    (demo_dir / "cover-2x1.html").write_text(cover2, encoding="utf-8")

    cover1 = cover_page(
        543, 544, card_stack(272, 68, 0.72) + spark(470, 118, 9, glow=True),
        eyebrow="10 个热门 AI 技能",
        title="按你要干的活\n挑 10 个 AI 技能", highlight="10",
        subtitle="五类活，各 2 个",
        chips=["画图", "写字", "查资料", "写代码", "记事"],
        footer_left="GITHUB SNAPSHOT · 2026-01-01", brand_line="● 你的账号名")
    (demo_dir / "cover-1x1.html").write_text(cover1, encoding="utf-8")

    art = (panel(40, 20, 380, 200)
           + txt(64, 70, "配图示例", 26, TXT, "800")
           + path("M60,180 L300,180", MINT, 3, marker="ar0", glow=True)
           + dots3(60, 120, 2, gap=20, r=7))
    (demo_dir / "fig1.html").write_text(
        figure_page(1350, 760, "F1", "示例 · 骨架", "这张图在演示什么", art,
                    footer_left="GITHUB 开源项目 · SKILL 技能实战"), encoding="utf-8")
    print(f"已写出 {demo_dir}\\cover-2x1.html 与 fig1.html；用 render.py 渲染即可")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        print(__doc__)

# -*- coding: utf-8 -*-
"""当期出图模板：封面（方案 A 大字报串联 / 方案 B 黑底主体 + 右侧粗白字）+ 配图（照片做底 / 代码信息图）。

**封面两方案二选一，一期只用一种**：清单与盘点类用 B（列表页里最跳），科普与选型类用 A（要氛围）。
方案 B 在文件末尾的 `main_block()` 里，默认不跑；要用就把 `__main__` 里那行取消注释。

用法（在当期项目的 _工作文件/ 里，或把这几个文件放平在同级目录）：

    1. 先下素材：python _工作文件/stock_photos.py search --theme cyberpunk --top 8 --min-width 1200
                 python _工作文件/stock_photos.py pick 3 --used-in 封面
    2. 改下面 PHOTO_* 的路径与所有文案
    3. 跑：python _工作文件/make_pages.py
    4. 渲染（照片底图一定出 jpg）：
       python _工作文件/render.py _工作文件/pages/cover-2x1.html 封面/封面_1276x544.jpg --width 1276 --height 544
       python _工作文件/render.py _工作文件/pages/fig1.html 配图/配图1_xxx.jpg --width 1080 --height 608

排版规则与配色口径见 references/visual-recipes.md；这里的文字全是占位示例，换成当期内容。
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import design_kit as dk  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
# 脚本放在 <项目根>/_工作文件/ 里时，项目根就是它的上一级；放在项目根就取自己
ROOT = HERE.parent if HERE.name == "_工作文件" else HERE
PAGES = HERE / "pages"
PAGES.mkdir(exist_ok=True)

# —— 当期素材：从 素材/图库/ 里挑两张（相对路径以 pages/*.html 为基准，所以要 ../../）
PHOTO_COVER = "../../素材/图库/xxx-cyberpunk.jpg"       # 封面底图：暗调、有留白、无文字物体
PHOTO_FIG = "../../素材/图库/xxx-tech.jpg"               # 配图底图：可同一张，也可换
COVER_PHOTO_ABS = ROOT / "素材" / "图库" / pathlib.Path(PHOTO_COVER).name


def main() -> None:
    # 1. 从素材照片取色，并做可读性体检（见 references/visual-recipes.md 第四节）
    if COVER_PHOTO_ABS.exists():
        pal = dk.use_palette_from_photo(COVER_PHOTO_ABS)
        print("取色：", pal)
    print("对比度体检：")
    dk.contrast_report()

    # 2. 封面 2.35:1：每行 4–7 字，点亮最多两处
    (PAGES / "cover-2x1.html").write_text(dk.poster_cover_page(
        1276, 544, PHOTO_COVER,
        title="每行四到七字\n分两三行最好",
        hi_words=["四到七字"],
        kicker="框架 · 一句话说明",
        subtitle="副标题承接标题没说完的部分",
        tags=["来源", "门槛 ●○○", "2026-10-10"],
        footer_left="GITHUB · README / DOCS SNAPSHOT",
        brand_line="● 你的skill好友",           # 账号锚点，位置不要动
    ), encoding="utf-8")

    # 3. 封面 1:1：三行短句
    (PAGES / "cover-1x1.html").write_text(dk.poster_cover_page(
        543, 544, PHOTO_COVER,
        title="方图用\n三行短句",
        hi_words=["三行短句"],
        kicker="框架",
        subtitle="一句副标题",
        tags=["来源", "门槛 ●○○"],
        footer_left="2026-10-10",
        brand_line="● 你的skill好友",
    ), encoding="utf-8")

    # 4. 配图一：照片做底 + 代码排版（步骤 / 命令 / 要点）
    art = (dk.panel(30, 10, 520, 210, 16, "rgba(8,12,18,.66)", dk.rgba(dk.MINT, .45))
           + dk.txt(58, 66, "命令或步骤", 25, dk.MINT_HI, "800")
           + dk.txt(58, 108, "一句前提条件（环境 / 密钥 / 账号）", 15, dk.SUB, "500")
           + dk.line(58, 132, 470, 132, dk.rgba(dk.MINT, .45), 2)
           + dk.dots3(62, 163, 1, gap=22, r=6)
           + dk.txt(102, 169, "做完会看到什么，怎么判断成功了", 15, dk.SUB, "500")
           + dk.txt(620, 90, "右侧放结论", 22, dk.TXT, "800")
           + dk.txt(620, 130, "一句话一件事", 22, dk.TXT, "800")
           + dk.spark(600, 68, 11, dk.MINT_HI, glow=True))
    (PAGES / "fig1.html").write_text(dk.figure_page(
        1080, 608, "F1", "来源 · 这一段讲什么", "配图标题写结论，不写名词",
        art, footer_left="框架 · 来源", photo=PHOTO_FIG,
    ), encoding="utf-8")

    # 5. 配图二：信息图（对照表这类要靠代码画，别用照片）
    rows = [("候选", "上手门槛", "价格 / 额度", "最适合的活"),
            ("A", "●○○ 一条命令", "以官网为准", "先出草稿"),
            ("B", "●●○ 要配密钥", "按量计费", "要求稳"),
            ("C", "●●● 要装环境", "开源自备", "数据不出门")]
    art_tbl = dk.panel(20, 4, 970, 300, 16, "rgba(8,12,18,.70)", dk.rgba(dk.MINT, .40))
    for r, row in enumerate(rows):
        y = 56 + r * 66
        if r == 0:
            art_tbl += dk.rrect(40, y - 30, 930, 44, 10, dk.rgba(dk.MINT, .16))
        art_tbl += dk.line(40, y + 22, 970, y + 22, dk.rgba("#FFFFFF", .08), 1)
        for c, cell in enumerate(row):
            art_tbl += dk.txt(62 + c * 236, y, cell, 17 if r == 0 else 16,
                              dk.MINT_HI if (r == 0 or c == 1) else dk.TXT,
                              "700" if r == 0 else "500")
    (PAGES / "fig2.html").write_text(dk.figure_page(
        1080, 608, "F2", "对照 · 一张表看全", "维度固定，别每行换说法",
        art_tbl, footer_left="框架 · 来源", photo=PHOTO_FIG,
    ), encoding="utf-8")

    print(f"已写出 {PAGES} 下的 cover-2x1 / cover-1x1 / cover-b-2x1 / cover-b-1x1 / fig1 / fig2")


def main_block() -> None:
    """封面方案 B：黑底主体 + 右侧粗白字（清单与盘点类首选）。

    与方案 A **二选一**，不要同期混用。末行放进彩色实心块是这套封面的记忆点。
    做法来自对标账号「逛逛GitHub」的封面公式，见 references/benchmark-guangguang-github.md 第四节。
    """
    # 左侧主体：用基础件拼一个立体件（也可以换成抠好的素材照片主体）
    subject = (dk.card_stack(200, 268, 1.15)
               + dk.spark(330, 150, 12, dk.ORANGE, glow=True))

    # 2.35:1：2–3 行，每行 4–6 字，末行在色块里
    (PAGES / "cover-b-2x1.html").write_text(dk.block_cover_page(
        1276, 544,
        title="装它只要一条命令\n但要先有 Node",
        block_words=["但要先有 Node"],          # 这一行会变成彩色块 + 白字
        kicker="项目手册 · 10 分钟上手",
        subject_svg=subject,
        block_color=dk.ORANGE,
        footer_left="GITHUB · README SNAPSHOT",
        brand_line="● 你的skill好友",            # 账号锚点，位置不要动
    ), encoding="utf-8")

    # 1:1：自动切成上下排布（主体在上、文字在下），不用手动调。
    # 方图里主体请放在**上方约 35%** 以内，否则会压到 kicker 与标题。
    (PAGES / "cover-b-1x1.html").write_text(dk.block_cover_page(
        543, 544,
        title="装它只要\n一条命令\n先有 Node",
        block_words=["先有 Node"],
        kicker="项目手册",
        subject_svg=dk.card_stack(110, 105, 0.62),
        block_color=dk.ORANGE,
        footer_left="README",
        brand_line="● 你的skill好友",
    ), encoding="utf-8")

    print(f"已写出 {PAGES} 下的 cover-b-2x1 / cover-b-1x1（方案 B）")


if __name__ == "__main__":
    main()
    # 想用方案 B 就再跑一次（两套都写出来只为对照，正式出图只留一套）：
    # main_block()

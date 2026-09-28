---
name: wechat-skill-radar
description: 把 GitHub 上近期热门的 Agent Skill（AI 技能）抓取、筛选并写成微信公众号文章的全流程技能——抓候选仓库、去重选题、按统一字段成稿、用代码绘制封面与配图、转成公众号内联样式 HTML、跑发布前自检。Use when the user asks to find trending GitHub AI or Agent skills, turn skills into a WeChat article or 公众号推文, build a 热门技能清单/技能合集, or keep a recurring "skill radar" publishing workflow. Do not use for unrelated article writing or for marketing copy that is not about Agent Skills.
---

# 技能雷达 · 公众号成稿

把"GitHub 上最近什么技能值得装"这件事，做成一篇能直接粘进公众号编辑器的文章：候选靠抓取、数据靠 README、配图靠代码画、版式靠内联样式、交付前跑自检。

## 什么时候用

- 用户要"抓一批近期热门的 AI 技能 / Agent Skill"，尤其是要写成公众号文章。
- 用户要按行业或场景做技能清单（营销、金融、出海、设计、办公、科研、编程……）。
- 用户要维护一个每天或每周更新的技能专栏。

不要用于：与 Agent Skill 无关的选题；纯营销文案；把技能清单写成带货软文。

## 硬性规则

1. **数据必须真实**。仓库名、星标数、安装命令、功能描述只能来自 GitHub 页面或对应仓库的 README，一律照抄，不发明、不四舍五入、不凭印象编。每个数字都要能说明是哪天抓的。
2. **不要套用上一期的编辑模式**。章节怎么分、开篇怎么写、图注什么语气、结尾用什么模块，都按当期内容自己决定；同一期里**逐个技能的字段必须统一**，读者才能横向比较。
3. **结尾固定**：结语 → 免责声明 → 平台引导。不加往期推荐，不加公众号名片。
4. **封面与配图**必须同时满足：一眼看出这批技能是干什么的 + 有科技感；画面以图形为主、文字精简；不出现第三方账号标识、logo、联系方式。
5. **正文排版固定**用 `references/wechat-layout.md` 里那套规格（已经过用户确认），不要每期自己另起一套。
6. 图片一律**用代码画**（HTML/SVG → 无头浏览器渲染 PNG），不用 AI 生图：中文不会变形，风格可控，改文案就是改代码。

## 工作流

把 `scripts/` **里面的文件**复制进当期项目的 `_工作文件/`（是平铺复制这些文件，不要在 `_工作文件/` 里再套一层 `scripts/`）。脚本按 `__file__` 的上一级当项目根，会自动在项目里建 `素材/`、`封面/`、`配图/`；多套一层目录，`素材/` 就会建到 `_工作文件/` 里面去：

```
<项目根>/
├── 发布稿.md                 # 主文件：元信息 + 正文 + 图片引用 + 结尾模块
├── 公众号粘贴版.html          # 交付：内联样式版
├── 封面/                     # 封面_1276x544.png、封面_543x544.png
├── 配图/                     # 正文配图
├── 素材/                     # raw/ 搜索缓存、readmes/ 仓库说明、候选技能清单.csv
└── _工作文件/                # 脚本（平铺）+ pages/（出图 HTML 源）+ 项目说明.md
```

1. **抓取**

   ```
   python _工作文件/github_skill_crawler.py search --set general --refresh --max-age-days 60
   python _工作文件/github_skill_crawler.py readme --only owner/repo owner/repo2 ...
   ```

   `--set` 可选 `general | marketing | finance | trade`，也可以直接改脚本里的关键词字典。仓库读取在 `素材/readmes/`，候选清单在 `素材/候选技能清单.csv`。

2. **去重与选题**。翻一遍同一条内容线里已经发过的项目，把写过的仓库剔掉；优先选当期星标高、最近仍在更新、且没写过的，一期 8–10 个。跑 `readme` 之前先定入选名单，别把配额浪费在不会用的仓库上。

3. **写作**。产出 `发布稿.md`，顶部用 `>` 写发布元信息（标题、备选标题、分享摘要、封面说明、配图清单、版式约定、数据来源）。每个技能用同一套字段，字段名和顺序全期不要变。

4. **出图**。用 `scripts/design_kit.py` 里的基础件（色板、图形、封面骨架、画框）写当期自己的 `make_pages.py`，再用 `render.py` 渲染：

   ```
   python _工作文件/make_pages.py
   python _工作文件/render.py _工作文件/pages/cover-2x1.html 封面/封面_1276x544.png --width 1276 --height 544
   python _工作文件/render.py _工作文件/pages/fig1.html 配图/配图1_xxx.png --width 1080 --height 608
   ```

   出图前读 `references/visual-recipes.md`，里面有配色取法、封面两种尺寸的做法，以及三个会让图直接画错的坑。

5. **交付与自检**

   ```
   python _工作文件/md2wechat.py 发布稿.md 公众号粘贴版.html
   python _工作文件/qa.py 发布稿.md 公众号粘贴版.html     # 必须 0 FAIL 才交付
   ```

   `qa.py` 只查机器能查的（图片比例与体积、段落长度、颜色白名单、必备模块、禁用词、内联样式）。人在交付前还要过一遍 `references/qa-checklist.md` 里的目视项。

## 交付物

- `发布稿.md`：主文件，含发布元信息、正文、图片引用、结尾模块；同一份可分发到知乎、百家号、今日头条。
- `公众号粘贴版.html`：浏览器打开后全选复制，粘进公众号编辑器（正文全部内联样式）。
- `封面/` 两张：1276×544（2.35:1）与 543×544（1:1，单独排版，不是裁大图）。
- `配图/`：正文配图，同一期比例必须一致。
- 汇报给用户时说明：文章路径、当期收录清单（含星标）、这期在结构或视觉上换了什么做法。

## 失败时

- 抓取失败、当天没有值得收录的新技能、或自检始终过不了：**说明原因并停下**，不要产出重复或凑数的内容。
- 星标和项目数量都是抓取当天的快照，交付时写明日期；用户要发布前建议再回仓库核对一次。

## 参考文件

- `references/editorial-rules.md` —— 内容边界、结构规则、统一字段、结尾模块。
- `references/wechat-layout.md` —— 公众号内联样式版式规格（正文/标题/图片/尾部），以及粘贴与预览的注意事项。
- `references/visual-recipes.md` —— 出图配方、配色取法、体积预算、常见坑。
- `references/qa-checklist.md` —— 发布前自检清单（机器项 + 目视项）。

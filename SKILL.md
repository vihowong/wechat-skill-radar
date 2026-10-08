---
name: wechat-skill-radar
description: 把 GitHub 上近期热门的 Agent Skill（AI 技能）抓取、筛选并写成微信公众号文章的全流程技能——抓候选仓库、去重选题、按统一字段成稿、给 6–8 条标题候选、按去 AI 腔的写作口径成文、用代码绘制封面与配图、转成公众号内联样式 HTML、跑发布前自检。Use when the user asks to find trending GitHub AI or Agent skills, turn skills into a WeChat article or 公众号推文, build a 热门技能清单/技能合集, ask for 标题/点击率优化 or 去 AI 味改写 on such an article, or keep a recurring "skill radar" publishing workflow. Do not use for unrelated article writing or for marketing copy that is not about Agent Skills.
---

# 技能雷达 · 公众号成稿

把"GitHub 上最近什么技能值得装"这件事，做成一篇能直接粘进公众号编辑器的文章：候选靠抓取、数据靠 README、标题给一组候选、正文按去 AI 腔的手感写、配图靠代码画、版式靠内联样式、交付前跑自检。

## 什么时候用

- 用户要"抓一批近期热门的 AI 技能 / Agent Skill"，尤其是要写成公众号文章。
- 用户要按行业或场景做技能清单（营销、金融、出海、设计、办公、科研、编程……）。
- 用户要维护一个每天或每周更新的技能专栏。

不要用于：与 Agent Skill 无关的选题；纯营销文案；把技能清单写成带货软文。

## 硬性规则

1. **一期一个行业**。每期只围绕一个行业选题，正文里出现的技能必须全部属于这个行业；行业写进项目文件夹名与稿件元信息。跨行业内容只允许在结语里一句话带过。判定标准：读者扫一眼标题和封面，能说出「这篇是给谁看的」。细则见 `references/topic-selection.md`。
2. **数据必须真实**。仓库名、星标数、安装命令、功能描述只能来自 GitHub 页面或对应仓库的 README，一律照抄，不发明、不四舍五入、不凭印象编。每个数字都要能说明是哪天抓的。
3. **实用与上手优先**。选当期热度高、45 天内仍在更新、未收录过的；同一条候选里优先「一条命令装完」的，要装环境或配密钥的一期最多 2–3 个。每个技能都要能回答三件事：装它要多久、装完第一步干什么、什么人不用装。
4. **不要套用上一期的编辑模式**。章节怎么分、开篇怎么写、图注什么语气、结尾用什么模块，都按当期内容自己决定；同一期里**逐个技能的字段必须统一**，读者才能横向比较。
5. **每期给一组标题候选**：6–8 条，其中 1 条推荐、3–5 条备选，覆盖至少 4 种钩子类型；推荐标题 ≤20 个汉字，不写标题党词、不承诺结果。写进发布稿元信息，交付时把推荐标题和备选一起报给用户。做法见 `references/titles.md`。
6. **去 AI 腔是硬要求**：禁用词、句式黑名单、标点频次、段落节奏、写出人味的具体做法，全部按 `references/writing-craft.md` 执行；机器能查的部分由 `qa.py` 拦（标题候选、AI 腔词表、破折号与感叹号频次、连续等长段落、句式重复）。
7. **结尾固定**：结语 → 免责声明 → 平台引导。不加往期推荐，不加公众号名片。
8. **封面与配图**必须同时满足：一眼看出这批技能是干什么的 + 有科技感；画面以图形为主、文字精简；不出现第三方账号标识、logo、联系方式。**色板每期可以换**——`references/visual-recipes.md` 备了五套基调，但三个账号锚点不能动：封面右下角的账号小字、深底亮主色的明暗关系、封面的五件套信息骨架。
9. **正文排版固定**用 `references/wechat-layout.md` 里那套规格（已经过用户确认），不要每期自己另起一套；排版层面的去 AI 腔（字段块别连着平铺、图注别一个句式、列表少用）见该文件第七节。
10. 图片一律**用代码画**（HTML/SVG → 无头浏览器渲染 PNG），不用 AI 生图：中文不会变形，风格可控，改文案就是改代码。

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

1. **定行业 → 抓取**

   先定这一期写哪个行业（相邻两期不重复），再抓：

   ```
   python _工作文件/github_skill_crawler.py search --set general --refresh --max-age-days 45
   python _工作文件/github_skill_crawler.py readme --only owner/repo owner/repo2 ...
   ```

   `--set` 可选 `general | marketing | finance | trade`，也可以直接改脚本里的关键词字典。
   **未登录时搜索配额约 10 次/分钟，一次跑完 16 个分类会有一片 HTTP 403**——被限流就直接跑
   `python _工作文件/fetch_missing.py`：它只补没抓到的分类，按间隔补完再合并。
   仓库 README 落在 `素材/readmes/`，候选清单在 `素材/候选技能清单.csv`。

2. **按行业筛 + 去重 + 选题**

   ```
   python _工作文件/pick_skills.py --list-industries
   python _工作文件/pick_skills.py 金融 --covered 已收录仓库.txt --top 20
   ```

   `pick_skills.py` 按行业过滤、剔掉 `--covered` 里的已收录仓库、按热度排序，并打印下一步要用的
   readme 命令。定下 8–10 个再抓 README，别把配额浪费在不会用的仓库上。
   这个行业实在凑不够数量时怎么办，见 `references/topic-selection.md` 第六节。

3. **起标题 → 写作**。先按 `references/titles.md` 写 12 条草稿、留下 6–8 条候选（含 1 条推荐）；定下推荐标题再动笔——标题决定正文要交付什么。然后按 `references/writing-craft.md` 写正文，产出 `发布稿.md`，顶部用 `>` 写发布元信息（**标题候选 6–8 条 + 推荐标题 + 备选标题**、分享摘要、封面说明、配图清单、版式约定、数据来源）。每个技能用同一套字段，字段名和顺序全期不要变。写完留一轮"去 AI 腔"改写，逐条过 `writing-craft.md` 的清单。

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
   python _工作文件/qa.py 发布稿.md 公众号粘贴版.html     # 必须 0 FAIL 才交付（含标题候选与 AI 腔检查）
   ```

   `qa.py` 只查机器能查的（图片比例与体积、段落长度、颜色白名单、必备模块、禁用词、内联样式、标题候选条数与字数、AI 腔词表、破折号与感叹号频次、连续等长段落、句式重复）。人在交付前还要过一遍 `references/qa-checklist.md` 里的目视项。

   > 本期字段名如果换成了别的（比如「进场要多久」而不是「装它」），要在项目根目录放一个 `qa_config.json` 声明 `install_prefixes`，否则含命令的长段落会被算进段落长度、误报"段落偏长"。

## 交付物

- `发布稿.md`：主文件，含发布元信息（标题候选表在内）、正文、图片引用、结尾模块；同一份可分发到知乎、百家号、今日头条。
- `公众号粘贴版.html`：浏览器打开后全选复制，粘进公众号编辑器（正文全部内联样式）。
- `封面/` 两张：1276×544（2.35:1）与 543×544（1:1，单独排版，不是裁大图）。
- `配图/`：正文配图，同一期比例必须一致。
- 汇报给用户时说明：本期写的**行业**、文章路径、当期收录清单（含星标）、**推荐标题与备选标题**（让人直接挑）、这期在结构或视觉上换了什么做法（换了哪套基调色板也算）。

## 失败时

- 抓取失败、当天没有值得收录的新技能、或自检始终过不了：**说明原因并停下**，不要产出重复或凑数的内容。
- 星标和项目数量都是抓取当天的快照，交付时写明日期；用户要发布前建议再回仓库核对一次。

## 参考文件

- `references/topic-selection.md` —— 一期一个行业：行业清单与抓取参数对照、入选标准、"容易上手"要写到什么程度、行业轮换与去重、凑不够数量怎么办。
- `references/editorial-rules.md` —— 内容边界、选题口径、结构规则、统一字段、标题要求、结尾模块。
- `references/writing-craft.md` —— **去 AI 腔与留存**：禁用词与句式黑名单、标点频次、写出人味的具体做法、开头与每节的留存结构、交稿前自问清单。
- `references/titles.md` —— **标题候选**：钩子类型表、从 12 条草稿到 6–8 条候选的流程、标题与封面的分工、写进元信息的格式。
- `references/wechat-layout.md` —— 公众号内联样式版式规格（正文/标题/图片/尾部）、排版层面的去 AI 腔，以及粘贴与预览的注意事项。
- `references/visual-recipes.md` —— 出图配方、配色取法、**五套基调色板与账号锚点**、体积预算、常见坑。
- `references/qa-checklist.md` —— 发布前自检清单（机器项 + 目视项）。

## 附带脚本

- `scripts/github_skill_crawler.py` —— 搜索候选（`search`）与抓 README（`readme`）。
- `scripts/fetch_missing.py` —— 被 GitHub 限流时，按间隔补齐缺失的行业分类再合并。
- `scripts/pick_skills.py` —— 按行业筛候选、剔除已收录仓库、按热度排序。
- `scripts/design_kit.py` / `make_pages.py`（当期自写）/ `render.py` —— 出图与渲染。
- `scripts/md2wechat.py` —— 转公众号内联样式 HTML；`scripts/qa.py` —— 发布前自检。

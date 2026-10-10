---
name: wechat-skill-radar
description: 把 AI 与科技领域的热点、GitHub 热门项目与 Agent Skill（AI 技能）做成微信公众号文章：多源找选题、自己装一遍跑一遍取证、按实测派手感成稿、给一组标题候选、用可商用素材加代码排版出图、过版权与违规词自检、转成公众号内联样式 HTML。Use when the user asks to find trending AI projects or Agent skills, turn a trending AI repo / model / project into a WeChat article or 公众号推文, build a 热门技能清单/技能合集, write a 单项目深度实测, ask for 标题优化 or 去 AI 味改写 on such an article, or keep a recurring "skill radar" publishing workflow. Do not use for unrelated article writing or for marketing copy that is not about AI or tech.
---

# 技能雷达 · 公众号成稿

把"最近 AI 圈什么值得看"这件事，做成一篇能直接粘进公众号编辑器的文章：选题靠多源雷达、事实靠公开页面、结论靠自己的实测、标题给一组候选、正文按实测派的手感写、配图用可商用素材加代码排版、交付前过一遍版权与违规词。

## 什么时候用

- 用户要"看看最近有什么热门的 AI 项目 / 技能 / 模型"，并写成公众号文章。
- 用户要把某一个 GitHub 项目、模型或功能做成整篇文章（单项目实测）。
- 用户要按场景或人群做技能清单（给做视频的、给做研究的、给财务的……）。
- 用户要维护一条每天或每周更新的技术专栏。

不要用于：与 AI、科技无关的选题；纯营销文案；把清单写成带货软文。

## 硬性规则

1. **一条线：人工智能 / 科技。** 主题可以是一个项目、一个技术方向、一类人的需求或一个事件，不限定行业；但一篇只能有一个主角群，读者扫一眼标题和封面就能说出"这篇讲什么、给谁看"。三种形态与入选标准见 `references/topic-selection.md`。
2. **实测优先。** 每篇至少三处"我做过"的证据：装过、跑过、数过、花过多少钱或时间。能在本机跑的就跑一遍并记录；跑不成的（要密钥、要特定账号或硬件）**写清没跑成的原因**，绝不假装跑过。凑不出实测就把定位降级成"资料整理"，并在开头告诉读者。写法见 `references/writing-craft.md`。
3. **数据分两类，分开标。** 公开页面上的（项目名、星标、许可证、命令、官方公布的性能）照抄并注明抓取日期；自己实测的（耗时、成本、成功率）写明测试条件。两者不许混着写。星标与榜单都是快照。
4. **授权与合规是前置条件。** 只用四类素材（自己实测的、公开页面事实、短引用、可商用素材）；极限词、违规题材、隐私、AI 生成标识按 `references/compliance.md` 执行。碰红线就换选题，不要想着绕。
5. **不要套用上一期的编辑模式。** 章节怎么分、开篇怎么写、图注什么语气、用什么骨架，都按当期内容自己决定；但**篇内平行字段必须统一**，读者才能横向比较。形态与骨架见 `references/editorial-rules.md`。
6. **每期给一组标题候选**：6–8 条，1 条推荐 + 3–5 条备选，覆盖至少 4 种钩子类型；推荐标题 ≤20 个汉字，不写标题党词与极限词，数字与正文一致。做法见 `references/titles.md`。
7. **去 AI 腔是硬要求**：禁用词、句式黑名单、标点频次、段落节奏，按 `references/writing-craft.md` 执行；机器能查的部分由 `qa.py` 拦。
8. **结尾固定**：结语 → 免责声明 → 平台引导。不加往期推荐，不加公众号名片。
9. **配图分三类，按需选**：实测类用真实截图（一步一图、关键处画红框、打码隐私、裁掉无关区域）；封面与氛围图用可商用照片做底、文字与图形靠代码排版合成；清单盘点类用代码画的图形骨架。不出现第三方账号标识、logo、联系方式、水印；照片页面一律输出 JPEG。色板每期可换（`references/visual-recipes.md` 备了五套），但三个账号锚点不能动：封面右下角的账号小字、深底亮主色的明暗关系、封面的五件套信息骨架。
10. **正文排版固定**用 `references/wechat-layout.md` 里那套规格（已经过用户确认），不要每期另起一套。
11. **单项目深挖必答四项**：测试设计、对照对象、耗时或成本、失败点。缺任何一项就不是深挖，是转述。
12. **交付前必须 0 FAIL**：`qa.py` 的机器项（含违规词、极限词、图片授权记录）全过，目视项按 `references/qa-checklist.md` 逐条看。

## 工作流

把 `scripts/` **里面的文件**复制进当期项目的 `_工作文件/`（平铺复制，不要在 `_工作文件/` 里再套一层 `scripts/`）。脚本按 `__file__` 的上一级当项目根，会自动在项目里建目录；多套一层目录，`素材/` 就会建到 `_工作文件/` 里面去。

```
<项目根>/
├── 发布稿.md                 # 主文件：元信息 + 正文 + 图片引用 + 结尾模块
├── 公众号粘贴版.html          # 交付：内联样式版
├── 封面/                     # 封面_1276x544.jpg、封面_543x544.jpg（有照片底图就是 jpg）
├── 配图/                     # 正文配图
├── 素材/
│   ├── 热点雷达.md / .json   # trend_radar.py 产出的多源热门
│   ├── 线索.md               # 人为追加的线索（X、网页搜索）
│   ├── 实测记录.md           # 自己跑的每一次：任务、耗时、结果、失败点
│   ├── 引用与授权.md         # 外部文章、帖子、截图、图片的来源与许可
│   ├── 图库/                 # stock_photos.py 下载的可商用照片 + 图片来源.md
│   ├── raw/ readmes/         # GitHub 搜索缓存与仓库说明
│   └── 候选技能清单.csv / 星标历史.csv
└── _工作文件/                # 脚本（平铺）+ pages/（出图 HTML 源）+ 项目说明.md
```

1. **定形态 → 找选题**

   先看内容线根目录的 `_已做主题.md`，确认这一期换什么；再从多源雷达开工：

   ```
   python _工作文件/trend_radar.py all --days 14 --top 20
   python _工作文件/github_skill_crawler.py search --set ai --refresh --max-age-days 45
   python _工作文件/github_skill_crawler.py search --set skill --allow-projects
   python _工作文件/trend_radar.py link <x 或网页链接> --note "为什么值得写"
   ```

   雷达产出 `素材/热点雷达.md`（GitHub、Hacker News、Reddit 三个来源，带链接与数字）。X 与网页搜索由人看到后记进 `素材/线索.md`。来源怎么用、怎么判断"够不够热"、可信度分级，见 `references/sources.md`。

2. **核实 → 抓 README → 自己跑一遍**

   ```
   python _工作文件/pick_skills.py --list-industries
   python _工作文件/pick_skills.py --any --top 20          # 不限主题，看全部候选
   python _工作文件/github_skill_crawler.py readme --only owner/repo owner/repo2
   ```

   被限流（HTTP 403）就跑 `python _工作文件/fetch_missing.py`，它按间隔补齐没抓到的分类再合并。
   入选的每个项目都要在本地装一次、跑一次，把任务、耗时、成本、失败点写进 `素材/实测记录.md`。跑不成的写明原因。这一步不能省——它是文章和"AI 洗稿"的分界线。

3. **起标题 → 写作**

   先按 `references/titles.md` 写 12 条草稿、留下 6–8 条候选（含 1 条推荐）；定下推荐标题再动笔——标题决定正文要交付什么。然后按 `references/writing-craft.md` 与 `references/editorial-rules.md` 写正文，产出 `发布稿.md`，顶部用 `>` 写发布元信息（**标题候选 6–8 条 + 推荐标题 + 备选标题**、选题形态、分享摘要、封面说明、配图清单、素材与授权、数据来源、实测口径）。稿件格式照 `examples/sample-article.md`（清单）或 `examples/sample-single-project.md`（单项目深挖）抄。

4. **出图**

   ```
   python _工作文件/stock_photos.py search "ai data center" --top 6
   python _工作文件/stock_photos.py pick 1 --used-in 封面
   python _工作文件/make_pages.py            # 当期自写：用 design_kit 的基础件排版
   python _工作文件/render.py _工作文件/pages/cover-2x1.html 封面/封面_1276x544.jpg --width 1276 --height 544
   python _工作文件/render.py _工作文件/pages/fig1.html 配图/配图1_xxx.png --width 1080 --height 608
   ```

   实测稿的正文配图直接用截图（放进 `配图/`），关键处用红框标出来；照片做底图的页面输出后缀写 `.jpg`
   （同样画面 PNG 约 700KB、JPEG 约 100–250KB，这是体积预算的关键）。出图前读 `references/visual-recipes.md`：
   截图怎么裁怎么标、照片怎么挑怎么压暗、五套色板，以及几个会让图直接画错的坑。

5. **交付与自检**

   ```
   python _工作文件/md2wechat.py 发布稿.md 公众号粘贴版.html
   python _工作文件/qa.py 发布稿.md 公众号粘贴版.html     # 必须 0 FAIL 才交付
   ```

   `qa.py` 查机器能查的：图片比例与体积、段落长度、颜色白名单、必备模块、禁用词、内联样式、标题候选条数与字数、AI 腔词表、标点频次、段落节奏、违规词与极限词、图片授权记录。人在交付前还要过一遍 `references/qa-checklist.md` 的目视项（版权署名、实验数据能否对上、图有没有被裁）。

   > 本期字段名如果换成了别的（比如「进场要多久」而不是「装它」），要在项目根目录放一个 `qa_config.json` 声明 `install_prefixes`，否则含命令的长段落会被算进段落长度、误报"段落偏长"。

## 交付物

- `发布稿.md`：主文件，含发布元信息（标题候选表在内）、正文、图片引用、结尾模块；同一份可分发到知乎、百家号、今日头条。
- `公众号粘贴版.html`：浏览器打开后全选复制，粘进公众号编辑器（正文全部内联样式）。
- `封面/` 两张：1276×544（2.35:1）与 543×544（1:1，单独排版，不是裁大图）。
- `配图/`：正文配图。清单与盘点类同一期比例一致；实测与教程类以截图为主，按内容裁，并在 `qa_config.json` 里写 `{"image_ratio": "loose"}`。
- `素材/`：选题证据链（热点雷达、线索、实测记录、引用与授权、图库来源）。
- 汇报给用户时说明：本期**形态与主题**、文章路径、收录清单（含星标）、**推荐标题与备选标题**、实测做了什么（跑了几个、花多久）、素材授权情况、这期在结构或视觉上换了什么做法。

## 失败时

- 抓取失败、当天没有值得写的热点、实测跑不起来、自检始终过不了：**说明原因并停下**，不要产出重复或凑数的内容。
- 实测跑不成但选题确实值得写：降级成"资料整理"，开头就讲清，并在稿末写明哪些是第一手、哪些只是公开信息。
- 星标与项目数量都是抓取当天的快照，交付时写明日期；建议用户发布前再回原始页面核对一次。

## 参考文件

- `references/topic-selection.md` —— 选题：三种形态、主题口径、热度判断、入选与淘汰、去重轮换、素材不够怎么办。
- `references/sources.md` —— 五个来源怎么用（GitHub / Hacker News / Reddit / X / 网页搜索）、抓取命令、线索落盘、可信度分级。
- `references/editorial-rules.md` —— 内容边界、三种形态的文章骨架、平行字段、写作口径、标题要求、数据口径。
- `references/writing-craft.md` —— **实测派写法与去 AI 腔**：一手证据链、对标账号的三种落笔模板、禁用词与句式黑名单、写出人味的具体做法、交稿前自问。
- `references/compliance.md` —— **版权与合规**：素材来源与许可证、短引用边界、平台红线、极限词与替换写法、图片授权与署名、AI 生成标识、免责声明。
- `references/titles.md` —— 标题候选：钩子类型表、从 12 条草稿到 6–8 条候选的流程、标题与封面的分工。
- `references/wechat-layout.md` —— 公众号内联样式版式规格（正文/标题/图片/图片署名/尾部）、排版层面的去 AI 腔、粘贴注意事项。
- `references/visual-recipes.md` —— 可商用图库与照片处理、出图配方、五套基调色板与账号锚点、体积预算、常见坑。
- `references/qa-checklist.md` —— 发布前自检清单（机器项 + 目视项 + 交付汇报）。

## 附带脚本

- `scripts/trend_radar.py` —— 多源热点雷达：Hacker News、Reddit（RSS）、GitHub 新项目；`link` 子命令记录 X 与网页线索。
- `scripts/github_skill_crawler.py` —— GitHub 搜索（`--set ai|skill|general|marketing|finance|trade`）与 README 抓取。
- `scripts/fetch_missing.py` —— 被 GitHub 限流时按间隔补齐缺失分类再合并。
- `scripts/pick_skills.py` —— 按方向筛候选、剔除已收录、按热度排序；`--any` 不限方向。
- `scripts/stock_photos.py` —— 找可商用照片（Openverse / Pexels / Unsplash）、下载、写授权记录。
- `scripts/design_kit.py` / `make_pages.py`（当期自写）/ `render.py` —— 排版与出图。
- `scripts/md2wechat.py` —— 转公众号内联样式 HTML；`scripts/qa.py` —— 发布前自检（含合规与授权检查）。

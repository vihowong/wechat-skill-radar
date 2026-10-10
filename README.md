# 技能雷达 · wechat-skill-radar

把**近期热门的 AI 项目、Agent Skill、模型与科技热点**做成一篇文章，并且能直接粘进公众号编辑器——
多源找选题、自己装一遍跑一遍取证、按实测派的手感成稿、给一组标题候选、用可商用素材加代码排版出图、
交付前过一遍版权与违规词。

这是一个 [Codex Skill](https://docs.openai.com/)：把 `SKILL.md` 和配套脚本放进 skills 目录，
之后直接说"看看最近有什么热门的 AI 技能，写成公众号文章"就能触发；也可以只把 `scripts/` 当普通工具链用。

## 它长什么样

封面按尺寸出两版（2.35:1 与 1:1，方图单独排版）：

![宽版封面示例](docs/demo-cover-wide.png)

![方图封面示例](docs/demo-cover-square.png)

正文配图用同一个色板和页脚，但每张换一种骨架（看板 / 对照 / 管线 / 阶梯 / 漏斗 / 矩阵）：

![配图示例](docs/demo-figure.png)

上面三张都是 `python scripts/design_kit.py demo` 生成的演示图，不是真实文章。
封面也可以拿可商用照片做底、文字与图形靠代码压在上面（`design_kit.photo_bg()`）。

## 三种选题形态

不再限定"一期一个行业"。主题可以是任何一件 AI / 科技圈的事，形态三选一：

| 形态 | 篇内数量 | 卖的是什么 |
| --- | --- | --- |
| 单项目深挖 | 1 个主角 + 1–3 个对照 | 实测：我跑了什么、花了多久、哪里不行 |
| 主题盘点 | 4–8 个 | 分布：谁在做什么、哪条路走得通 |
| 清单合集 | 8–10 个 | 省事：先装哪个、怎么装、装完干什么 |

选题口径见 `references/topic-selection.md`，来源清单见 `references/sources.md`。

## 一篇文章是怎么产出的

```
定形态 ─► 多源雷达 ─► 抓 README ─► 自己装一遍跑一遍 ─► 起一组标题 ─► 按统一字段成稿 ─► 出图 ─► 转 HTML ─► 自检
选题口径  trend_radar  crawler      实测记录             titles.md       发布稿.md        stock_photos  md2wechat  qa
          GitHub/HN/  pick_skills   素材/实测记录.md     6–8 条候选      去 AI 腔         + design_kit
          Reddit/X                                                                       + render
```

工具：

| 脚本 | 干什么 |
| --- | --- |
| `scripts/trend_radar.py` | 多源热点雷达：GitHub 新项目 + Hacker News + Reddit（RSS），`link` 子命令记录 X 与网页线索 |
| `scripts/github_skill_crawler.py` | 按关键词集抓 GitHub 仓库（`--set skill/ai/general/marketing/finance/trade`），`--allow-projects` 收更广的 AI 项目；README 走 raw 地址，不占 API 配额 |
| `scripts/fetch_missing.py` | 被 GitHub 限流（HTTP 403）时按间隔只补没抓到的分类，再合并成候选清单 |
| `scripts/pick_skills.py` | 按方向筛候选、剔除已收录仓库、按热度排序；`--any` 不限方向 |
| `scripts/stock_photos.py` | 找可商用照片（Openverse / Pexels / Unsplash）、下载、自动写授权记录 |
| `scripts/design_kit.py` | 出图基础件：色板、发光、箭头、点阵、图标、封面骨架、配图画框、照片底图 |
| `scripts/render.py` | 本机 Chrome / Edge 无头渲染 HTML → PNG 或 JPEG（照片页面必须出 JPEG） |
| `scripts/md2wechat.py` | Markdown → 公众号可粘贴的内联样式 HTML（版式规格见 `references/wechat-layout.md`） |
| `scripts/qa.py` | 发布前自检：图片比例与体积、段落长度、颜色白名单、必备模块、禁用词、标题候选、AI 腔词表、标点频次、段落节奏、**违规词与极限词**、**图片授权记录** |

## 快速开始

```bash
# 0. 依赖：Python 3.10+、本机装了 Chrome 或 Edge；抓取与装技能时用到 Node.js
#    （可选）pip install pillow  →  照片页面输出 JPEG、出图前压缩都用它
#    （可选）设 GITHUB_TOKEN 提速、设 PEXELS_API_KEY / UNSPLASH_ACCESS_KEY 换图库来源

# 1. 建一个当期项目，把脚本放进去（脚本按上一级目录当项目根，会自动创建素材/封面/配图）
mkdir -p ~/articles/2026-10-10_单项目_MCP实测/_工作文件
cp -r scripts ~/articles/2026-10-10_单项目_MCP实测/_工作文件/
cd ~/articles/2026-10-10_单项目_MCP实测

# 2. 多源找选题
python _工作文件/trend_radar.py all --days 14 --top 20
python _工作文件/github_skill_crawler.py search --set ai --refresh --max-age-days 45
python _工作文件/github_skill_crawler.py search --set skill --allow-projects
python _工作文件/trend_radar.py link https://x.com/... --note "为什么值得写"

# 3. 筛候选 → 抓入选仓库的 README → 自己装一遍跑一遍，记录写进 素材/实测记录.md
python _工作文件/pick_skills.py --list-industries
python _工作文件/pick_skills.py --any --top 20
python _工作文件/github_skill_crawler.py readme --only owner/repo owner/repo2

# 4. 起标题（references/titles.md）→ 写稿（references/writing-craft.md）→ 格式照 examples/

# 5. 出图：照片找 stock_photos，排版写 make_pages，渲染用 render
python _工作文件/stock_photos.py search "server room dark" --top 8
python _工作文件/stock_photos.py pick 3 --used-in 封面
python _工作文件/design_kit.py demo          # 先看基础件效果
python _工作文件/render.py _工作文件/pages/cover-2x1.html 封面/封面_1276x544.jpg --width 1276 --height 544
python _工作文件/render.py _工作文件/pages/fig1.html 配图/配图1_xxx.png --width 1080 --height 608

# 6. 转公众号 HTML + 自检
python _工作文件/md2wechat.py 发布稿.md 公众号粘贴版.html
python _工作文件/qa.py 发布稿.md 公众号粘贴版.html      # 必须 0 FAIL
```

抓取没有配置 GitHub token 时，搜索配额是 10 次/分钟，脚本已做节流与缓存；一次跑完十几个分类通常会有一片 403，
直接跑 `fetch_missing.py` 补齐即可。Reddit 对服务器 IP 限流很紧（RSS 也会 429），脚本会重试并把抓到的子版进缓存，
隔几分钟重跑同一条命令或分成几个 `--subs` 小批就能补齐。

## 几条刻意的设计取舍

- **不限定行业，限定形态。** 一期只讲一件事：一个项目、一个技术方向、一类人的需求，或一个事件。
  读者扫一眼标题和封面就知道这篇讲什么、给谁看。
- **实测优先，跑不动就说跑不动。** 每篇至少三处"我做过"的证据（装过、跑过、数过、花过多少）；跑不成的
  （要密钥、要特定账号或硬件）写清原因，绝不当成跑过。凑不出实测就降级成资料整理，并在开头说明。
- **数据分两类，分开标。** 公开页面上的照抄并注日期，自己实测的写明测试条件；星标与榜单都是快照。
- **合规前置。** 只用四类素材（自己实测的、公开页面事实、短引用、可商用素材）；违规词、极限词、隐私、
  AI 生成标识按 `references/compliance.md` 执行，`qa.py` 会拦违规词并检查图片授权记录。
- **配图分三类。** 实测类用真实截图（一步一图、关键处红框、打码隐私）；封面与氛围图用可商用照片做底 +
  代码排版（照片页面输出 JPEG，体积从 700KB 降到 100–250KB）；清单盘点类用代码画的图形骨架。
- **版式固定，内容换新。** 排版规格（15px 正文、墨绿单一强调色、导语灰卡、小标题左绿条、13px 图注、
  不声明 font-family）固定；每期换的是结构、叙事、封面构图和配图骨架。
- **每期给一组标题，而不是一个。** 6–8 条候选（1 条推荐 + 3–5 条备选），覆盖数字清单、身份认同、场景痛点、
  实测结果、对比选择等钩子，推荐标题 ≤20 字，写进发布稿元信息，交付时连理由一起报给用户挑。
- **正文按"去 AI 腔"写。** 禁用词与句式黑名单、标点频次、段落节奏、每节先给一句"这节看什么"、
  实测与转述分开标注——都写在 `references/writing-craft.md`，能机器查的部分由 `qa.py` 拦。
- **色板可换，风格不换。** 封面与配图每期可以换一套基调（`references/visual-recipes.md` 备了五套），
  但账号锚点固定：封面右下角的账号小字、深底亮主色的明暗关系、封面的五件套信息骨架。
- **自检分两层。** 机器能查的交给 `qa.py`（必须 0 FAIL），机器查不了的（截图有没有被裁、字段是否一致、
  命令能否对上、授权是否署名）走 `references/qa-checklist.md` 的目视清单。

## 仓库结构

```
SKILL.md                      技能入口（什么时候用、硬性规则、工作流）
references/
  topic-selection.md          选题：三种形态、主题口径、热度判断、入选与去重
  sources.md                  来源：GitHub / Hacker News / Reddit / X / 网页搜索怎么用
  editorial-rules.md          内容边界、三种形态的文章骨架、平行字段、数据口径
  writing-craft.md            实测派写法与去 AI 腔：证据链、落笔模板、禁用词、留存结构
  compliance.md               版权与合规：许可证、短引用、平台红线、极限词、图片授权、AI 标识
  titles.md                   标题候选：钩子类型表、起标题流程、写进元信息的格式
  wechat-layout.md            公众号排版规格、图片与署名、排版层面的去 AI 腔
  visual-recipes.md           图片从哪来、截图怎么做、照片做底怎么排、五套色板、体积预算、常见的坑
  qa-checklist.md             发布前自检清单（机器项 + 目视项 + 版权合规 + 交付汇报）
scripts/                      九个工具（trend_radar / stock_photos / render 支持 JPEG 等）
examples/
  sample-article.md           清单形态的稿件格式示例
  sample-single-project.md    单项目深挖形态的稿件格式示例
docs/                         README 里的演示图
```

## 许可

MIT

# 技能雷达 · wechat-skill-radar

把 GitHub 上近期热门的 **Agent Skill（AI 技能）**抓下来，写成一篇能直接粘进公众号编辑器的文章——候选靠抓取、数据靠 README、封面和配图靠代码画、版式靠内联样式、交付前跑自检。

这是一个 [Codex Skill](https://docs.openai.com/)：把 `SKILL.md` 和配套脚本放进 skills 目录，之后直接说"抓一批热门技能做成公众号文章"就能触发；也可以只把 `scripts/` 当普通工具链用。

## 它长什么样

封面按尺寸出两版（2.35:1 与 1:1，方图单独排版）：

![宽版封面示例](docs/demo-cover-wide.png)

![方图封面示例](docs/demo-cover-square.png)

正文配图用同一个色板和页脚，但每张换一种骨架（看板 / 对照 / 管线 / 阶梯 / 漏斗 / 矩阵）：

![配图示例](docs/demo-figure.png)

上面三张都是 `python scripts/design_kit.py demo` 生成的演示图，不是真实文章。

## 一片文章是怎么产出的

```
抓取候选 ──► 去重选题 ──► 按统一字段成稿 ──► 代码出封面与配图 ──► 转公众号 HTML ──► 自检
 crawler      general/      发布稿.md          design_kit + render    md2wechat        qa
              行业词集       （Markdown）       （HTML/SVG → PNG）     （内联样式）
```

四件工具：

| 脚本 | 干什么 |
| --- | --- |
| `scripts/github_skill_crawler.py` | 按关键词集抓 GitHub 仓库，客户端过滤 + 缓存 + 输出候选清单与摘要；README 走 raw 地址，不占 API 配额 |
| `scripts/md2wechat.py` | Markdown → 公众号可粘贴的内联样式 HTML（版式规格见 `references/wechat-layout.md`） |
| `scripts/design_kit.py` | 出图基础件：色板、发光、箭头、点阵、图标、封面骨架、配图画框 |
| `scripts/render.py` | 用本机 Chrome / Edge 无头渲染 HTML → PNG |
| `scripts/qa.py` | 发布前自检：图片比例与体积、段落长度、颜色白名单、必备模块、禁用词 |

## 快速开始

```bash
# 0. 依赖：Python 3.10+、本机装了 Chrome 或 Edge；抓取与装技能时用到 Node.js

# 1. 建一个当期项目，把脚本放进去（脚本按上一级目录当项目根，会自动创建素材/封面/配图）
mkdir -p ~/articles/2026-01-01_某主题/_工作文件
cp -r scripts ~/articles/2026-01-01_某主题/_工作文件/
cd ~/articles/2026-01-01_某主题

# 2. 抓候选 → 抓入选仓库的 README
python _工作文件/github_skill_crawler.py search --set general --refresh --max-age-days 60
python _工作文件/github_skill_crawler.py readme --only owner/repo owner/repo2

# 3. 写稿（照着 examples/sample-article.md 的格式）

# 4. 出图
python _工作文件/design_kit.py demo          # 先看基础件效果
python _工作文件/render.py _工作文件/pages/cover-2x1.html 封面/封面_1276x544.png --width 1276 --height 544
python _工作文件/render.py _工作文件/pages/fig1.html 配图/配图1_xxx.png --width 1080 --height 608

# 5. 转公众号 HTML + 自检
python _工作文件/md2wechat.py 发布稿.md 公众号粘贴版.html
python _工作文件/qa.py 发布稿.md 公众号粘贴版.html      # 必须 0 FAIL
```

抓取没有配置 GitHub token 时，搜索配额是 10 次/分钟，脚本已做节流与 12 小时缓存；设置环境变量 `GITHUB_TOKEN` 可以提速（脚本不会打印 token）。

## 几条刻意的设计取舍

- **版式固定，内容换新。** 排版规格（15px 正文、墨绿单一强调色、导语灰卡、小标题左绿条、13px 图注、不声明 font-family）经过验收后固定下来；每期换的是结构、叙事、封面构图和配图骨架，避免读者视觉疲劳。
- **配图一律代码画。** HTML/SVG → 无头浏览器渲染 PNG：中文不会变形、风格可控、改文案就是改代码，还能精确控制体积（七张 16:9 合计控制在 3MB 以内）。
- **数据只照抄。** 仓库名、星标、安装命令、功能描述全部来自 GitHub 页面或仓库 README，抓取日期写进稿子，不发明、不四舍五入。
- **自检分两层。** 机器能查的交给 `qa.py`（必须 0 FAIL），机器查不了的（图片有没有被裁、字段是否一致、命令能否对上）走 `references/qa-checklist.md` 的目视清单。

## 仓库结构

```
SKILL.md                      技能入口（什么时候用、硬性规则、工作流）
references/
  editorial-rules.md          内容边界、结构规则、统一字段
  wechat-layout.md            公众号排版规格与粘贴注意事项
  visual-recipes.md           出图配方、体积预算、三个必踩的坑
  qa-checklist.md             发布前自检清单（机器项 + 目视项）
scripts/                      五件工具
examples/sample-article.md    稿件格式示例（非真实数据）
docs/                         README 里的演示图
```

## 许可

MIT

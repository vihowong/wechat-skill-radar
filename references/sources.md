# 来源：五个地方找选题，各自怎么用

这份文件管「去哪找、怎么抓、抓到的东西算不算数」。选题口径见 `topic-selection.md`。

## 〇、先跑一遍雷达

```bash
python _工作文件/trend_radar.py all --days 14 --top 20
```

它把 GitHub、Hacker News、Reddit 三个来源最近两周的热门聚合成 `素材/热点雷达.md`（含每个条目的链接、数字、日期），是每期开工的第一步。X 与网页搜索的线索靠手工记录，见第四、五节。

## 一、GitHub：主来源，数据可核验

三种找法各有用途：

| 找法 | 用途 | 命令 |
| --- | --- | --- |
| 主题标签 | 找某个方向的项目（`topic:mcp-server`、`topic:agent-skills`） | `github_skill_crawler.py search --set skill` |
| 关键词 | 找某个用途的技能（设计、写作、视频……） | `search --set general` / `--set finance` / `--set marketing` / `--set trade` |
| 新项目 | 近似 New & Trending：近 90 天建库、按星标排 | `search --set ai` |

```bash
python _工作文件/github_skill_crawler.py search --set ai --refresh --max-age-days 45
python _工作文件/github_skill_crawler.py search --set skill --allow-projects
python _工作文件/github_skill_crawler.py readme --only owner/repo owner/repo2
```

- 默认只收"技能类"（名字或描述里带 skill / agent / plugin 等信号）；要收更广的 AI 项目加 `--allow-projects`。
- 未登录时搜索配额约 10 次/分钟，一次跑完 16 个分类会有一片 HTTP 403；被限流直接跑 `fetch_missing.py` 补齐。
- 每个仓库的星标、`pushed_at`、许可证、README 都落在 `素材/` 里，写稿时对着抄。
- **星标是快照，不是趋势。** 想知道"正在涨"，隔两天再抓一次，两次结果都追加进 `素材/星标历史.csv`，对比出增速。

## 二、Hacker News：最快的行业风向

```bash
python _工作文件/trend_radar.py hn --days 14 --min-points 100
```

底层是免费的 Algolia 检索接口（`hn.algolia.com/api/v1/search`），可以按时间与分数过滤，不用密钥。

看什么：标题的措辞（大家怎么描述这件事）、评论区在争什么（分歧点就是文章的落点）、Ask HN 里反复出现的问题（那是读者的真实困惑）。
引用时短引用加署名，并写出 HN 讨论帖链接。

## 三、Reddit：真实使用体验

```bash
python _工作文件/trend_radar.py reddit --days 7 --subs LocalLLaMA,MachineLearning,AI_Agents
```

Reddit 的公开 JSON 接口已经封了数据中心 IP，**走 RSS 可用**（`reddit.com/r/<sub>/top/.rss?t=week`），所以只取标题、链接与时间，够用来选题，不够用来引用数字。

常用子版：`LocalLLaMA`、`MachineLearning`、`LLMDevs`、`AI_Agents`、`ChatGPTCoding`、`ClaudeAI`、`OpenAI`、`cursor`、`mcp`、`StableDiffusion`、`artificial`。

看什么：抱怨帖（"它又把文件写坏了"）、对比帖、踩坑帖——这些是文章里"读者能对号入座的场景"的原料。

## 四、X：信号快，但不稳定

X 需要登录且反爬严格，**不做自动抓取**。正确用法是人工浏览，看到值得写的东西就把它记下来：

```bash
python _工作文件/trend_radar.py link https://x.com/someone/status/1234567890 --note "说这个插件把出图时间从 3 分钟压到 20 秒"
```

记录四件事：链接、发布时间、一个数字（转发 / 点赞 / 作者给的实测值）、一句"为什么值得写"。
引用规则：短引用加作者名与平台；截图要打码他人昵称与头像；不要用第三方镜像站抓取。

## 五、网页搜索与其他一手来源

- 用检索确认"最近两周有人讨论它吗"：`site:news.ycombinator.com`、`site:reddit.com`、`site:github.com`。
- 官方博客、更新日志、模型卡（model card）、定价页是一手来源，优先于二手解读。
- 榜单（LMArena、Artificial Analysis、OpenRouter 排名）天天变，引用必须写日期，并说明这是当期快照。
- 论文只在真的读过摘要或结论时引用，不要凭他人转述写。

## 六、线索怎么落盘

| 文件 | 谁写 | 内容 |
| --- | --- | --- |
| `素材/热点雷达.md` | `trend_radar.py all` | 三个来源的当期热门，含链接与数字 |
| `素材/热点雷达.json` | 同上 | 同一份数据，供脚本再处理 |
| `素材/线索.md` | 人（`trend_radar.py link` 追加） | X、网页搜索、私下看到的线索 |
| `素材/星标历史.csv` | `github_skill_crawler.py` | 每次抓取的星标快照，用来看增速 |
| `素材/引用与授权.md` | 人 | 引用的文章 / 帖子 / 图片：来源、作者、链接、许可、用在哪 |

每条线索至少写清：来源、链接、日期、一个数字、一句"为什么值得写"。缺数字的线索不算线索，只是印象。

## 七、可信度分级（写稿时按这个口径落笔）

- **A 一手**：官方公告、仓库 README、自己实测。可以直接写。
- **B 二手**：HN / Reddit / X 上的讨论与复现。写的时候带上来源：「有人在 X 上复现了一遍」。
- **C 传闻**：单一帖子、没有出处的传言。只能用「有人提到」这种口径，不能当事实写，也不要写进标题。

# 公众号排版规格

这套规格已经定稿并验收过，**每期直接沿用**：版式稳定，内容换新。实现见 `scripts/md2wechat.py`。

## 一、正文与标题

| 元素 | 规格 |
| --- | --- |
| 正文 | `font-size: 15px; line-height: 1.75; letter-spacing: 0.02em; color: #1F2937; margin: 0 0 18px; text-align: justify;` |
| 导语 | 外层 `<section style="background-color: #F8FAFC; border-radius: 10px; padding: 16px 18px; margin: 0 0 24px;">`，内文 15px / 行高 1.8 / `#374151` |
| 一级小标题（`##`） | 19px / 700 / `#0F172A`，`border-left: 4px solid #0E7C66; padding-left: 10px;` |
| 技能小标题（`###`） | 16px / 700 / `#0F172A`，纯文字，不加色块与标记 |
| 强调（`**…**`） | 只用墨绿 `#0E7C66`，全篇一个强调色 |
| 列表 | `<ul style="margin: 0 0 18px; padding-left: 1.2em;">`，`li` 15px / 行高 1.75 / `#1F2937` / `margin: 0 0 8px` |
| 小字（图注） | 13px / 行高 1.7 / `#6B7280` / 居中 / `margin: 0 0 22px` |
| 尾部（免责声明 + 平台引导） | 13px / 行高 1.9 / `#6B7280`；免责三行 `margin: 0 0 3px`、引导一行 `margin: 0` |

## 二、图片

```html
<section style="text-align: center; margin: 0 0 8px;">
  <img src="配图/配图1_xxx.png" alt="图注文字"
       style="width: 100%; height: auto; display: block; border-radius: 10px; border: 1px solid #E2E8F0;">
</section>
<p style="font-size: 13px; line-height: 1.7; color: #6B7280; margin: 0 0 22px; text-align: center;">图注：…</p>
```

- 同一期所有正文配图**比例必须一致**（常用 16:9 → 1080×608），单张 16:9 控制在 400KB 左右，七张合计不超过 3MB。
- 封面两张：1276×544（2.35:1）与 543×544（1:1）。方图单独排版，不要裁大图。

## 三、字体族

**正文一律不声明 `font-family`。** 微信端会用自己的默认字体，声明了反而在不同机型上不一致；尾部同理。

副作用：本地浏览器打开预览时，正文会落到浏览器默认字体（中文常见是宋体），看着和手机不一样。解决办法是在**预览外壳 CSS** 里补一套字体——外壳在复制范围之外，不会带进公众号：

```css
/* 只在本地预览生效，复制进公众号时不要带上这段 CSS */
#stage, #stage * { font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif; }
```

## 四、两处容易踩的细节

1. **含命令的行不要两端对齐。** `装它：npx skills add …` 这类段落里全是英文与空格，`text-align: justify` 会把空格拉开成大缝。这类段落单独用一个 `text-align: left` 的样式，其余段落保持两端对齐。
2. **长地址必须能断行。** 正文与列表样式里带上 `overflow-wrap: anywhere; word-break: break-word;`：前者参与最小宽度计算，缺少它时一条长 URL 会把整页在手机上撑宽（`break-word` 单独用不够，它不影响内在尺寸）。

## 五、转 HTML 与粘贴

```bash
python _工作文件/md2wechat.py 发布稿.md 公众号粘贴版.html
```

- 生成的文件里，`<!-- ===== 从这里开始，整段复制进公众号编辑器 ===== -->` 与 `<!-- ===== 复制范围到此结束 ===== -->` 之间才是要复制的内容；外面的 `<style>` 是本地预览外壳。
- 浏览器打开 → 全选复制 → 粘进公众号编辑器，行内样式会带过去。
- 同一份 Markdown 可直接分发到知乎、百家号、今日头条，图片按当期统一比例上传。

## 六、颜色白名单

正文只用这几个值（`scripts/qa.py` 会检查，改版式时同步改白名单）：

`#0E7C66`（强调） · `#0F172A`（标题） · `#1F2937`（正文） · `#374151`（导语） · `#6B7280`（小字） · `#FFFFFF`

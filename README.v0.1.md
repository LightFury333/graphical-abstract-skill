# Graphical Abstract v 0.1

**用于 OpenAI Codex 的 AI 生成技能（AI-generated skill for Codex）。**

根据用户提供的 Word、PDF、PPT、研究图表或数据，制作 **一张内容清晰、排版合理的 scientific graphical abstract 预览图**。默认采用本次工作形成的 EHJ-inspired 紫—酒红—橙渐变视觉体系，也支持任意用户指定配色。

> **本仓库完全由 AI 打造（100% AI-built）。** 技能流程、文档、辅助代码、配色示例和检查工作均由 AI 根据用户需求完成。用户提供目标、审美反馈与发布授权。仓库沿用所有者选定的 MIT 许可证。

## 核心行为

- 每次默认输出一张完整 PNG，内容取自本次提供的文件。
- 先核对研究对象、方法、主要终点、数值、比较方向与结论，再组织视觉内容。
- 保持协调的整体渐变、浅色分区、白色分区标题、黑色正文及与背景相符的渐变图标。
- 核查 PPT 参考图的实际字体；默认使用 Segoe UI 常规字体接近既定参考图观感，有可核实的指定字体时优先跟随。正文、标签、数字与结论以字号和留白建立层次，减少加粗。
- 支持颜色名称、HEX 色值、品牌配色或参考图片，不限于下面四套示例。
- 只换颜色时，保留已确认底稿的文字、字体、布局和图标轮廓。
- 新稿默认横向 18:11、目标 3600 × 2200 PNG；已有定稿保留原比例。默认不添加顶部三段式文字区。
- PPTX、SVG、缩写 Word 和额外版本仅按需交付。

这是 **EHJ 风格启发的工作流，非 EHJ 官方模板或官方工具**。预览经过内容与显示核查后交付；正式投稿以目标期刊当前要求为准。

## 安装与调用

将本仓库的 `graphical-abstract-v0-1` 文件夹复制到 Codex 技能目录：

- Windows：`%USERPROFILE%\.codex\skills\graphical-abstract-v0-1`
- macOS / Linux：`~/.codex/skills/graphical-abstract-v0-1`
- 如设置了 `CODEX_HOME`，使用其下的 `skills` 目录。

调用名称为 `$graphical-abstract-v0-1`，界面显示名称为 **Graphical Abstract v 0.1**。

```text
使用 $graphical-abstract-v0-1，根据附上的 Word 原稿、PDF 建议和 PPT 风格参考，
制作一张英文 graphical abstract 预览图，默认 EHJ 配色。
```

```text
使用 $graphical-abstract-v0-1，把已确认的摘要图改成深蓝到青绿的渐变。
文字、字体、布局和图标位置全部保持不变，只生成一张效果图。
```

```text
使用 $graphical-abstract-v0-1，以 #183153、#277DA8、#52B788 为配色参考，
根据这些实验材料制作一张机制研究 graphical abstract。
```

## 配色示例

以下示例来自本次成果的配色层，已去除全部文字、图标、箭头与研究数据。它们展示颜色和表面处理，不规定研究内容或强制布局。

### 默认：EHJ-inspired 紫—酒红—橙

![EHJ default palette](graphical-abstract-v0-1/assets/palette-examples/ehj-default.png)

### 蓝—青—绿

![Blue teal jade palette](graphical-abstract-v0-1/assets/palette-examples/blue-teal-jade.png)

### 靛蓝—紫

![Indigo violet palette](graphical-abstract-v0-1/assets/palette-examples/indigo-violet.png)

### 酒红—玫瑰—金

![Burgundy rose gold palette](graphical-abstract-v0-1/assets/palette-examples/burgundy-rose-gold.png)

## 文件与运行环境

入口为 [`graphical-abstract-v0-1/SKILL.md`](graphical-abstract-v0-1/SKILL.md)。`references/` 包含视觉指南、配色参数和内容核对方法；配色示例同时提供 SVG 和 PNG。

技能依赖宿主 AI 的文件读取、视觉检查与生成能力。可选的 SVG 重配色辅助程序只需 Python 标准库；PNG 渲染程序需 Node.js 与 Sharp。它们不是独立理解论文或生成科学结论的程序。具体用法见 [工具与输出说明](graphical-abstract-v0-1/references/tools-and-output.md)。

发布范围仅包括通用技能说明、辅助代码和无文字、无图标的配色示例。原稿、原始 PDF/PPT、源数据、完整摘要及其成图、工作记录、个人绝对路径和账户凭据均不属于发布内容；这些材料应保留在独立的本地工作目录中。示例是原创结果的无内容派生图，未分发期刊原图、标识或字体文件。

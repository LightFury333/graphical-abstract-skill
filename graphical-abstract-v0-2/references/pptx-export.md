# 导出可编辑 PowerPoint

`export_editable_pptx.py` 把静态 SVG 转为一页 PowerPoint。文字可以直接改写，线条、置信区间、数据点、标题形状和渐变可在 PowerPoint 中分别选中、移动和改色。SVG 中的 PNG 或 JPEG 插图会成为独立的图片对象。

## 使用方法

在 `graphical-abstract-v0-2` 目录运行。需要 Python 3.9 或以上、python-pptx 1.x 和 Pillow。已验证的环境使用 Python 3.12、python-pptx 1.0.2 及 Microsoft PowerPoint 16。

```sh
python -m pip install "python-pptx>=1,<2" Pillow
python scripts/export_editable_pptx.py examples/transformer-dapt/figure.svg output/figure.pptx
```

默认幻灯片宽 12 英寸，高度按 SVG 的纵横比计算。用 `--width-inches 10` 可改为 10 英寸宽。导出程序会创建输出目录，并重新读取成品检查页数。目标文件已存在时会提示选择新文件名；指定 `--force` 后，只有新文件成功生成并检查通过才会替换旧文件。

## 哪些内容可以编辑

| SVG 内容 | PowerPoint 中的结果 |
| --- | --- |
| 每个带明确坐标的单行 `text` | 单独的原生文本框，保留字号、字体、颜色、粗斜体和水平对齐 |
| 矩形、圆角矩形、圆和椭圆 | 对应的 PowerPoint 原生形状 |
| 线、折线、多边形及支持的贝塞尔路径 | 连接线或可编辑顶点的自由形状 |
| 线性渐变 | 原生渐变，含色标、透明度和方向；覆盖形状局部的 SVG 渐变会换算为整形状的 PowerPoint 色标位置 |
| 内嵌 PNG、JPEG | 可单独移动或替换的图片；图片内部的文字和像素随原图保留 |

图表的点、区间和坐标轴均是独立图形，没有链接的数据表。需要换数据时，修改数据文件，再生成 SVG 和 PPTX。PowerPoint 的选择窗格会显示来源分组或对象名称。未安装 SVG 指定字体的电脑会使用本机替代字体；交付前请确认页面中的字体、基线、数字与颜色。

## 为可靠导出准备 SVG

- 在根节点设置正尺寸的 `viewBox` 或宽高。若同时设置两者，使其比例一致。每行文字使用独立的 `<text x="…" y="…">`。
- 可使用实色、透明度、线性渐变、正的等比缩放和平移。渐变使用 `objectBoundingBox`、显式色标和 `pad` 延展。圆角矩形使用相等的横纵圆角半径。
- 路径支持绝对和相对的 M、L、H、V、C、S、Q、T、Z 指令。将 A 弧段预先转换为三次贝塞尔；将 `tspan` 多行标签拆成有绝对坐标的单行文本；展开 CSS 类、符号引用及旋转或非等比变换。
- 滤镜、剪裁、遮罩、径向渐变、文字路径和外部图片需先整理。复杂插图可作为一个独立素材导出为透明 PNG 后，以 `data:image/png;base64,…` 嵌入 SVG，同时把研究文字与数值保留为原生对象。如需矢量插图，可在支持 SVG 的 PowerPoint 里单独插入该 SVG。程序遇到未覆盖的元素或属性会指出位置，便于修订源图。

验证本地安装可运行 `python scripts/test_editable_pptx.py`。测试覆盖原生文本和线条、自定义路径、渐变色标、内嵌图片、导出失败时保留旧文件，以及对未支持内容的明确提示。


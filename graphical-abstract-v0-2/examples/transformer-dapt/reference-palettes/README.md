# Transformer-DAPT · 8–11 号研究成图

下表使用图册新编号，链接保留原研究文件名。标题栏横向渐变，面板从浅底向带色的对角过渡，底部结论条连起两个分区的色调。研究队列与外部验证面板都以截图给定的浅色为渐变色标。圆点表示缺血事件，方块表示出血事件，横线表示 95% 置信区间；三者使用实色以便读数。

| 编号与风格 | 缺血圆点 | 出血方块 | 两个分区的浅底色标 | 单张文件 |
| --- | --- | --- | --- | --- |
| **8　经典医学期刊风** · 深海蓝 × 砖红 | `#1A365D` | `#C0392B` | `#F0F4F8` · `#FDF2F0` | [高清 PNG](1-navy-brick.png) · [可编辑 SVG](1-navy-brick.svg) |
| **9　NEJM / Lancet 典雅风** · 藏青 × 琥珀金棕 | `#2C3E50` | `#C77C11` | `#F4F6F7` · `#FDF8F0` | [高清 PNG](2-navy-amber.png) · [可编辑 SVG](2-navy-amber.svg) |
| **10　稳重中性风** · 深铁灰 × 靛蓝 | `#2B2D42` | `#4A6FA5` | `#EDF2F4` · `#F1F4F9` | [高清 PNG](4-iron-steel.png) · [可编辑 SVG](4-iron-steel.svg) |
| **11　生命科学紫蓝风** · 深靛青 × 烟熏洋红 | `#343A60` | `#A04668` | `#F1F2F8` · `#FBF0F4` | [高清 PNG](5-indigo-berry.png) · [可编辑 SVG](5-indigo-berry.svg) |

第 8、9 号各给出两种次主色。上表列出用于出血方块的色值，另一个色值分别是 `#B85D43` 和 `#D38B28`，用于强调细节。白字标题使用相应色系的深色。完整映射见[统一配色参数](../../../references/palettes.json)。

每张 PNG 为 3600 × 2200 像素。查看全部配色可打开[1–11 号离线图册](../palette-atlas/index.html)。在[示例目录](../README.md)运行以下命令，可用同一份研究证据重建这四套 SVG 和 PNG。

```sh
python build_figure.py --reference-palettes --format svg png
```

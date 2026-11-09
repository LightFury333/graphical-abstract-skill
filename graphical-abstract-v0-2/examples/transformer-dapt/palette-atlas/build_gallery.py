"""Rebuild the offline index.html and palette guide from references/palettes.json.

Run `python build_gallery.py` from any directory using this script's path.
The SVG previews and PNG overviews are produced by the atlas artwork builder.
"""
from html import escape
import json
from pathlib import Path

ATLAS = Path(__file__).resolve().parent
REFERENCES = ATLAS.parents[2] / "references"
MODES = {"surfaces": "配色示例", "cards": "数字色卡", "schematics": "极简示意图"}


def read_palettes():
    catalog = json.loads((REFERENCES / "palettes.json").read_text(encoding="utf-8"))
    records = []
    for key, palette in catalog["palettes"].items():
        number = palette.get("atlas_number")
        name = palette.get("name_zh")
        if type(number) is not int or not isinstance(name, str) or not name.strip():
            raise ValueError(f"Palette {key} needs an integer atlas_number and Chinese name_zh.")
        records.append((number, name.strip(), key))
    records.sort()
    if [record[0] for record in records] != list(range(1, 12)):
        raise ValueError("Public atlas numbers must be unique and contiguous from 1 to 11.")
    if records[0][2] != catalog["default_palette"] or records[0][2] != "ehj-default":
        raise ValueError("The atlas starts with the default EHJ palette.")
    return records


def make_tile(record, mode):
    number, name, _ = record
    name_html = escape(name)
    src = f"{mode}/{number:02d}.svg"
    label = f"{number} 号 · {name_html} · {MODES[mode]}"
    if mode == "surfaces":
        width, height = 1605, 980
        caption = f'<h3 class="tile-title">{number} · {name_html}</h3>'
        png_link = (f'<a class="source png-source" href="{mode}/{number:02d}.png" target="_blank" '
                    f'rel="noopener" aria-label="用新标签页打开{label}的 PNG">打开 PNG <span aria-hidden="true">↗</span></a>')
    else:
        width, height = 680, 420
        caption = ""
        png_link = ""
    return f'''      <article class="tile" data-number="{number}" data-name="{name_html}">
        <a class="preview" href="{src}" aria-label="放大查看{label}">
          <img src="{src}" width="{width}" height="{height}" alt="{label}" decoding="async">
          <span class="zoom-hint" aria-hidden="true">放大</span>
        </a>
        <div class="tile-meta">{caption}
          <div class="tile-links">
            <a class="source svg-source" href="{src}" target="_blank" rel="noopener" aria-label="用新标签页打开{label}的 SVG">打开 SVG <span aria-hidden="true">↗</span></a>
            {png_link}
          </div>
        </div>
      </article>'''


def build_html(records):
    html = (ATLAS / "gallery.template.html").read_text(encoding="utf-8")
    for mode in MODES:
        marker = "{{" + mode.upper() + "_TILES}}"
        if html.count(marker) != 1:
            raise ValueError(f"Missing or duplicate template marker {marker}.")
        html = html.replace(marker, "\n".join(make_tile(record, mode) for record in records))
    return html.replace("{{COUNT}}", str(len(records)))


def build_guide(records):
    atlas = "../examples/transformer-dapt/palette-atlas"
    lines = [
        "# 图形摘要配色指南",
        "",
        f"[打开离线图册]({atlas}/index.html)，先看配色示例中的标题栏、分区底色和渐变，"
        "再按同一编号切换数字色卡或极简示意图。",
        "",
        f"[配色示例总览（PNG）]({atlas}/surfaces-overview.png) · "
        f"[数字色卡总览（PNG）]({atlas}/cards-overview.png) · "
        f"[极简示意图总览（PNG）]({atlas}/schematics-overview.png)",
        "",
        "制图时可指定图册编号、中文名称或配色 ID。默认组合是可编辑 SVG 和 1 号 EHJ 配色。",
        "",
        "| 编号 | 配色 | 配色 ID | 配色示例 | 数字色卡 | 极简示意图 |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for number, name, key in records:
        name = name.replace("|", "\\|")
        lines.append(
            f"| {number} | {name} | `{key}` | "
            f"[SVG]({atlas}/surfaces/{number:02d}.svg) · [PNG]({atlas}/surfaces/{number:02d}.png) | "
            f"[色卡]({atlas}/cards/{number:02d}.svg) | "
            f"[示意图]({atlas}/schematics/{number:02d}.svg) |"
        )
    lines.extend(["", "各套配色的渐变色标、方向和数据标记颜色见[配色参数](palettes.json)。", ""])
    return "\n".join(lines)


def main():
    records = read_palettes()
    (ATLAS / "index.html").write_text(build_html(records), encoding="utf-8")
    (REFERENCES / "palette-guide.md").write_text(build_guide(records), encoding="utf-8")


if __name__ == "__main__":
    main()


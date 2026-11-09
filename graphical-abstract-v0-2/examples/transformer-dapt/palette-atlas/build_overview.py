"""Draw two original color atlases and assemble their rendered SVGs into PNG contact sheets."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


ATLAS = Path(__file__).resolve().parent
SKILL = ATLAS.parents[2]
CATALOG = SKILL / "references" / "palettes.json"
RENDERER = SKILL / "scripts" / "render_preview.cjs"
SVG = "http://www.w3.org/2000/svg"
CJK = "Microsoft YaHei, Noto Sans CJK SC, PingFang SC, Source Han Sans SC, sans-serif"
DIGITS = "Bahnschrift, Arial, sans-serif"
WIDTH, HEIGHT = 680, 420
PAPER = "#FAF9F6"
INK = "#21252B"
ET.register_namespace("", SVG)


def add(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", {
        key.replace("_", "-"): str(value) for key, value in attrs.items()
    })


def label(parent, x, y, value, size, **attrs):
    add(parent, "text", x=x, y=y, font_size=size, **attrs).text = str(value)


def paint(role):
    return f"url(#{role})"


def svg_page(width, height):
    return ET.Element(f"{{{SVG}}}svg", width=str(width), height=str(height),
                      viewBox=f"0 0 {width} {height}", role="img",
                      attrib={"font-family": CJK, "fill": INK})


def artwork(palette, description):
    svg = svg_page(WIDTH, HEIGHT)
    svg.set("aria-labelledby", "title description")
    code = str(palette["atlas_number"])
    name = palette["name_zh"]
    add(svg, "title", id="title").text = f"{code}  {name}"
    add(svg, "desc", id="description").text = description
    defs = add(svg, "defs")
    for role, values in palette["gradient_roles"].items():
        grad = add(defs, "linearGradient", id=role,
                   **{key: f"{values[key] * 100:g}%" for key in ("x1", "y1", "x2", "y2")})
        for stop in values["stops"]:
            add(grad, "stop", offset=f"{stop['offset'] * 100:g}%", stop_color=stop["color"],
                stop_opacity=stop.get("opacity", 1))
    add(svg, "rect", width=WIDTH, height=HEIGHT, fill=paint("page-wash"))
    return svg, code, name


def numeral_card(palette):
    svg, code, name = artwork(palette, "数字色卡。三层曲面分别展示本组左、中、右标题渐变。")
    add(svg, "rect", width=WIDTH, height=322, fill=paint("left-wash"))
    # Three overlapping samples expose each whole gradient, from edge to edge.
    swatches = [
        ("header-left", "M333 322 C416 233 385 112 482 48 C544 8 616 15 680 -16 L680 322 Z"),
        ("header-middle", "M402 322 C476 254 460 156 538 102 C591 65 639 62 680 49 L680 322 Z"),
        ("header-right", "M479 322 C541 272 559 210 614 164 C637 145 661 133 680 129 L680 322 Z"),
    ]
    for role, contour in swatches:
        add(svg, "path", d=contour, fill=paint(role))
    label(svg, 170, 255, code, 236, font_family=DIGITS, font_weight=600,
          text_anchor="middle", letter_spacing=-8, fill=paint("header-left"))
    add(svg, "path", d="M0 322 H680", stroke=palette["solid_roles"]["panel-rule"],
        stroke_width=1.5, fill="none")
    label(svg, 39, 385, name, 40, fill=palette["solid_roles"]["text"])
    return svg


def arrow(parent, start, end, y, color):
    add(parent, "path", d=f"M{start} {y} H{end} M{end-13} {y-9} L{end} {y} L{end-13} {y+9}",
        fill="none", stroke=color, stroke_width=4, stroke_linejoin="round", stroke_linecap="round")


def icon_group(svg, x, ink):
    return add(svg, "g", transform=f"translate({x} 218)", stroke=ink, stroke_width=5,
               stroke_linejoin="round", stroke_linecap="round", fill="none")


def draw_sample(group):
    # A falling drop and a graduated collection tube.
    add(group, "path", d="M-21 -22 V23 A21 21 0 0 0 21 23 V-22")
    add(group, "path", d="M-18 7 Q-6 2 2 6 Q10 10 18 7 V23 A18 18 0 0 1 -18 23 Z",
        fill=paint("header-left"), stroke="none")
    add(group, "path", d="M-26 -22 H26 M10 -8 H20 M12 3 H20")
    add(group, "path", d="M0 -60 C-2 -53 -10 -47 -10 -40 A10 10 0 0 0 10 -40 C10 -46 2 -54 0 -60 Z",
        fill=paint("badge-purple"), stroke="none")


def draw_test(group):
    # Microscope with an angled optical tube, a stage and a focusing wheel.
    add(group, "path", d="M7 -21 C38 -19 48 7 35 26 C30 33 20 38 10 39",
        stroke_width=9)
    tube = add(group, "g", transform="rotate(34)")
    add(tube, "rect", x=-10, y=-49, width=20, height=44, rx=3,
        fill=paint("header-middle"), stroke_width=4)
    add(tube, "path", d="M-14 -51 H14 M-6 -4 V4 H6 V-4", stroke_width=5)
    add(group, "path", d="M-36 12 H7 M-25 17 H-4 M6 38 L1 44 M-32 45 H36", stroke_width=6)
    add(group, "circle", cx=20, cy=-3, r=9, fill=paint("mid-wash"), stroke_width=4.5)


def draw_observation(group):
    add(group, "path", d="M-51 0 Q-25 -31 0 -31 Q24 -31 51 0 Q25 31 0 31 Q-26 31 -51 0 Z",
        fill=paint("page-wash"))
    add(group, "circle", cx=0, cy=0, r=20, fill=paint("header-right"), stroke_width=3.5)
    add(group, "circle", cx=0, cy=0, r=7, stroke="none", fill=group.get("stroke"))
    add(group, "circle", cx=-6, cy=-7, r=4.5, fill="#FFFFFF", stroke="none")


def schematic(palette):
    svg, code, name = artwork(palette, "极简示意图。采样、检测和观察三个步骤依次用箭头连接。")
    solids = palette["solid_roles"]
    add(svg, "rect", width=WIDTH, height=10, fill=paint("icon-spectrum"))
    label(svg, 71, 79, code, 57, font_family=DIGITS, font_weight=600,
          text_anchor="middle", fill=paint("header-left"))
    add(svg, "path", d="M117 38 V79", stroke=solids["panel-rule"], stroke_width=3)
    label(svg, 141, 76, name, 35, fill=solids["text"])
    add(svg, "path", d="M32 106 H648", stroke=solids["panel-rule"], stroke_width=2)

    steps = [
        (110, "采样", "left-wash", "header-left", draw_sample),
        (340, "检测", "mid-wash", "header-middle", draw_test),
        (570, "观察", "right-wash", "header-right", draw_observation),
    ]
    for x, caption, wash, header, draw_icon in steps:
        add(svg, "rect", x=x-78, y=140, width=156, height=156, rx=40,
            fill=paint(wash), stroke=paint(header), stroke_width=3)
        draw_icon(icon_group(svg, x, solids["text"]))
        label(svg, x, 360, caption, 39, text_anchor="middle", fill=solids["text"])
    arrow(svg, 201, 247, 218, solids["branch-start"])
    arrow(svg, 431, 477, 218, solids["branch-end"])
    return svg


def write_svg(svg, output):
    ET.indent(svg, space="  ")
    ET.ElementTree(svg).write(output, encoding="utf-8", xml_declaration=True)


def rasterize(svg, png, width, sharp_module):
    args = ["node", str(RENDERER), str(svg), str(png), "--width", str(width)]
    if sharp_module:
        args.extend(["--sharp-module", str(sharp_module)])
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def make_gallery(destination, palettes, style, draw_artwork, heading, sharp_module):
    output = destination / style
    output.mkdir(exist_ok=True)
    margin, gap, row_gap, title_height = 48, 24, 24, 116
    sheet_width = margin * 2 + 4 * WIDTH + 3 * gap
    sheet_height = title_height + 3 * HEIGHT + 2 * row_gap + margin
    montage = Image.new("RGB", (sheet_width, sheet_height), PAPER)
    frame = ImageDraw.Draw(montage)
    with tempfile.TemporaryDirectory() as working:
        temp = Path(working)
        masthead = svg_page(sheet_width, title_height)
        add(masthead, "rect", width=sheet_width, height=title_height, fill=PAPER)
        label(masthead, margin, 74, heading, 54)
        add(masthead, "path", d=f"M{margin} 98 H{sheet_width-margin}", fill="none", stroke="#B9B9B1", stroke_width=2)
        write_svg(masthead, temp / "title.svg")
        rasterize(temp / "title.svg", temp / "title.png", sheet_width, sharp_module)
        with Image.open(temp / "title.png") as title_image:
            montage.paste(title_image.convert("RGB"), (0, 0))

        for pos, palette in enumerate(palettes):
            stem = f"{palette['atlas_number']:02d}"
            vector = output / (stem + ".svg")
            write_svg(draw_artwork(palette), vector)
            raster = temp / (stem + ".png")
            rasterize(vector, raster, WIDTH, sharp_module)
            row, column = divmod(pos, 4)
            row_length = min(4, len(palettes) - row * 4)
            left = (sheet_width - row_length * WIDTH - (row_length - 1) * gap) // 2
            x, y = left + column * (WIDTH + gap), title_height + row * (HEIGHT + row_gap)
            with Image.open(raster) as tile:
                if tile.size != (WIDTH, HEIGHT):
                    raise ValueError(f"Unexpected raster dimensions for {vector.name}: {tile.size}")
                montage.paste(tile.convert("RGB"), (x, y))
            frame.rectangle((x-1, y-1, x+WIDTH, y+HEIGHT), outline="#DDDDD8")
    montage.save(destination / f"{style}-overview.png", compress_level=8)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sharp-module", type=Path, help="Path to Sharp if unavailable to the bundled renderer")
    args = cli.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    palettes = sorted(catalog["palettes"].values(), key=lambda p: p["atlas_number"])
    if [p["atlas_number"] for p in palettes] != list(range(1, 12)):
        raise ValueError("The atlas needs one palette per number from 1 through 11.")
    # Finish both designs before publishing either gallery.
    with tempfile.TemporaryDirectory() as working:
        stage = Path(working)
        make_gallery(stage, palettes, "cards", numeral_card, "数字色卡", args.sharp_module)
        make_gallery(stage, palettes, "schematics", schematic, "极简示意图", args.sharp_module)
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                dest = ATLAS / file.relative_to(stage)
                dest.parent.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as published:
                    published.write(file.read_bytes())
                Path(published.name).replace(dest)


if __name__ == "__main__":
    main()

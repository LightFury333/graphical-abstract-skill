"""Build eleven text-free color boards from the original EHJ surface layout."""

import argparse
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from build_overview import (
    ATLAS, CATALOG, DIGITS, PAPER, SKILL, SVG, add, label, rasterize, svg_page, write_svg,
)


ORIGINALS = SKILL / "assets" / "palette-examples"
TEMPLATE = ORIGINALS / "ehj-default.svg"
BOARD_WIDTH, BOARD_HEIGHT = 1605, 980


def make_board(palette_id, palette, filename, sharp_module):
    source_board = ORIGINALS / f"{palette_id}.svg"
    if source_board.is_file():
        filename.write_bytes(source_board.read_bytes())
        filename.with_suffix(".png").write_bytes(source_board.with_suffix(".png").read_bytes())
        return

    tree = ET.parse(TEMPLATE)
    for gradient in tree.iter(f"{{{SVG}}}linearGradient"):
        values = palette["gradient_roles"][gradient.get("id")]
        for axis in ("x1", "y1", "x2", "y2"):
            gradient.set(axis, format(values[axis], "g"))
        for original_stop in list(gradient):
            gradient.remove(original_stop)
        for stop in values["stops"]:
            attrs = {"offset": format(stop["offset"], "g"), "stop-color": stop["color"]}
            if "opacity" in stop:
                attrs["stop-opacity"] = format(stop["opacity"], "g")
            ET.SubElement(gradient, f"{{{SVG}}}stop", attrs)
    # These are the only two literal paint roles outside the original gradient stops.
    for shadow in tree.iter(f"{{{SVG}}}feDropShadow"):
        shadow.set("flood-color", palette["solid_roles"]["header-shadow"])
    for rect in tree.iter(f"{{{SVG}}}rect"):
        if "stroke" in rect.attrib:
            rect.set("stroke", palette["solid_roles"]["border"])
    write_svg(tree.getroot(), filename)
    rasterize(filename, filename.with_suffix(".png"), BOARD_WIDTH, sharp_module)


def overview(target, palettes, stage, scratch, sharp_module):
    width, margin, gap, row_gap = 760, 48, 26, 35
    height = round(width * BOARD_HEIGHT / BOARD_WIDTH)
    header, caption = 122, 64
    sheet_width = 2 * margin + 4 * width + 3 * gap
    sheet_height = header + 3 * (caption + height) + 2 * row_gap + margin
    captions = svg_page(sheet_width, sheet_height)
    add(captions, "rect", width=sheet_width, height=sheet_height, fill=PAPER)
    label(captions, margin, 77, "配色示例", 56)
    add(captions, "path", d=f"M{margin} 99 H{sheet_width-margin}", fill="none",
        stroke="#B9B9B1", stroke_width=2)
    positions = []
    for pos, (_, palette) in enumerate(palettes):
        row, col = divmod(pos, 4)
        count = min(4, len(palettes) - 4 * row)
        row_offset = (sheet_width - count * width - (count - 1) * gap) // 2
        x = row_offset + col * (width + gap)
        top = header + row * (caption + height + row_gap)
        ink = palette["gradient_roles"]["header-left"]["stops"][0]["color"]
        label(captions, x, top + 41, palette["atlas_number"], 42, font_family=DIGITS,
              font_weight=600, fill=ink)
        add(captions, "path", d=f"M{x+62} {top+12} v31", stroke="#C6C6BF", stroke_width=2)
        label(captions, x + 80, top + 41, palette["name_zh"], 36)
        positions.append((x, top + caption))

    write_svg(captions, scratch / "captions.svg")
    rasterize(scratch / "captions.svg", scratch / "captions.png", sheet_width, sharp_module)
    with Image.open(scratch / "captions.png") as background:
        canvas = background.convert("RGB")
    frame = ImageDraw.Draw(canvas)
    for (_, palette), (x, y) in zip(palettes, positions):
        stem = f"{palette['atlas_number']:02d}"
        rendered = stage / "surfaces" / (stem + ".png")
        with Image.open(rendered) as tile:
            if tile.size != (BOARD_WIDTH, BOARD_HEIGHT):
                raise ValueError(f"Unexpected dimensions for board {stem}: {tile.size}")
            canvas.paste(tile.convert("RGB").resize((width, height), Image.Resampling.LANCZOS), (x, y))
        frame.rectangle((x-1, y-1, x+width, y+height), outline="#DADBD6", width=1)
    canvas.save(target, compress_level=8)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sharp-module", type=Path, help="Path to Sharp if unavailable to the bundled renderer")
    args = cli.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["palettes"]
    palettes = sorted(catalog.items(), key=lambda item: item[1]["atlas_number"])
    if [palette["atlas_number"] for _, palette in palettes] != list(range(1, 12)):
        raise ValueError("The surface atlas requires consecutive palette numbers 1–11.")

    with tempfile.TemporaryDirectory() as working:
        scratch = Path(working)
        stage = scratch / "deliverables"
        (stage / "surfaces").mkdir(parents=True)
        for palette_id, palette in palettes:
            stem = f"{palette['atlas_number']:02d}"
            make_board(palette_id, palette, stage / "surfaces" / (stem + ".svg"), args.sharp_module)
        overview(stage / "surfaces-overview.png", palettes, stage, scratch, args.sharp_module)
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                destination = ATLAS / file.relative_to(stage)
                destination.parent.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as published:
                    published.write(file.read_bytes())
                Path(published.name).replace(destination)


if __name__ == "__main__":
    main()

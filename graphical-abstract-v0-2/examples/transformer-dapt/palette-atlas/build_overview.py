"""Build the atlas overview and the comparison sheets from the study renders."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

ATLAS = Path(__file__).resolve().parent
STUDY = ATLAS.parent
CATALOG = STUDY.parents[1] / "references" / "palettes.json"
GROUPS = (
    ("v0.1 原配色", "v01-palettes", (
        ("ehj-default", "", "EHJ 紫—酒红—橙"),
        ("blue-teal-jade", "", "蓝—青—绿"),
        ("indigo-violet", "", "靛蓝—紫"),
        ("burgundy-rose-gold", "", "酒红—玫瑰—金"),
    )),
    ("保留的字母方案", "color-options", (
        ("pine-sage", "B", "松针绿—鼠尾草"),
        ("ink-coral", "C", "墨蓝—珊瑚"),
        ("mulberry-lilac", "D", "桑葚—丁香"),
    )),
    ("保留的编号方案", "reference-palettes", (
        ("navy-brick", "1", "深海蓝 × 砖红"),
        ("navy-amber", "2", "藏青 × 琥珀金棕"),
        ("iron-steel", "4", "深铁灰 × 靛蓝"),
        ("indigo-berry", "5", "深靛青 × 烟熏洋红"),
    )),
)
PAPER = "#FAFAF9"
INK = "#21252A"


def draw_gradient(draw, x, y, width, height, stops):
    for col in range(width):
        t = col / (width - 1)
        for left, right in zip(stops, stops[1:]):
            if left["offset"] <= t <= right["offset"]:
                frac = (t - left["offset"]) / (right["offset"] - left["offset"])
                rgb = tuple(round(a + frac * (b - a)) for a, b in
                            zip(ImageColor.getrgb(left["color"]), ImageColor.getrgb(right["color"])))
                draw.line((x + col, y, x + col, y + height - 1), fill=rgb)
                break


def place_figure(canvas, font, palettes, directory, item, x, y, width):
    draw = ImageDraw.Draw(canvas)
    palette_id, code, name = item
    gradients = palettes[palette_id]["gradient_roles"]
    primary = gradients["header-left"]["stops"][0]["color"]
    if code:
        draw.rounded_rectangle((x, y + 1, x + 44, y + 45), radius=8, fill=primary)
        draw.text((x + 22, y + 23), code, font=font, fill="white", anchor="mm")
    draw.text((x + (59 if code else 0), y + 22), name, font=font, fill=INK, anchor="lm")
    for i, role in enumerate(("header-left", "header-right")):
        draw_gradient(draw, x + width - 102 + 52 * i, y + 17, 48, 13, gradients[role]["stops"])
    stem = f"{code}-{palette_id}" if code else palette_id
    height = width * 11 // 18
    with Image.open(STUDY / directory / (stem + ".png")) as pic:
        if pic.size != (3600, 2200):
            raise ValueError(f"Unexpected preview dimensions for {stem}: {pic.size}")
        thumb = pic.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    y += 56
    canvas.paste(thumb, (x, y))
    draw.rectangle((x - 1, y - 1, x + width, y + height), outline="#D8DBDE", width=1)


def render_overview(palettes, font_path):
    cell, gap, margin = 864, 31, 55
    width = 2 * margin + 4 * cell + 3 * gap
    row_height = 64 + 56 + cell * 11 // 18 + 33
    height = 140 + 3 * row_height + 14
    canvas = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(canvas)
    title, heading, label = [ImageFont.truetype(str(font_path), size) for size in (63, 36, 32)]
    draw.text((margin, 57), "图形摘要配色图册", font=title, fill=INK, anchor="lm")
    draw.text((width - margin, 61), "Transformer-DAPT  /  11 套", font=heading, fill="#58616A", anchor="rm")
    draw.line((margin, 114, width - margin, 114), fill="#ACB1B5", width=2)
    for row, (head, directory, entries) in enumerate(GROUPS):
        y = 140 + row * row_height
        draw.text((margin, y + 19), head, font=heading, fill=INK, anchor="lm")
        start = (width - len(entries) * cell - (len(entries) - 1) * gap) // 2
        for col, item in enumerate(entries):
            place_figure(canvas, label, palettes, directory, item, start + col * (cell + gap), y + 64, cell)
    canvas.save(ATLAS / "overview.png", compress_level=8)


def render_reference_comparison(palettes, font_path):
    cell, gap, margin = 1080, 42, 42
    row_height = 56 + cell * 11 // 18
    canvas = Image.new("RGB", (2 * cell + 2 * margin + gap, 2 * row_height + 2 * margin + gap), PAPER)
    font = ImageFont.truetype(str(font_path), 39)
    _, directory, entries = GROUPS[-1]
    for i, item in enumerate(entries):
        x = margin + (i % 2) * (cell + gap)
        y = margin + (i // 2) * (row_height + gap)
        place_figure(canvas, font, palettes, directory, item, x, y, cell)
    canvas.save(STUDY / directory / "comparison.png", compress_level=8)


def render_cool_pair(palettes, font_path):
    cell, gap, margin = 1440, 46, 40
    height = 56 + cell * 11 // 18
    canvas = Image.new("RGB", (2 * cell + gap + 2 * margin, height + 2 * margin), PAPER)
    font = ImageFont.truetype(str(font_path), 40)
    _, directory, entries = GROUPS[0]
    pair = ("blue-teal-jade", "indigo-violet")
    by_id = {entry[0]: entry for entry in entries}
    for col, palette_id in enumerate(pair):
        place_figure(canvas, font, palettes, directory, by_id[palette_id],
                     margin + col * (cell + gap), margin, cell)
    canvas.save(ATLAS / "blue-teal-and-indigo.png", compress_level=8)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--font", type=Path, help="Path to a Chinese sans-serif TTF, OTF or TTC file")
    args = cli.parse_args()
    font = args.font or Path("C:/Windows/Fonts/msyh.ttc")
    if not font.is_file():
        cli.error("Supply --font with a Chinese font file available on this system.")
    palettes = json.loads(CATALOG.read_text(encoding="utf-8"))["palettes"]
    expected = {item[0] for _, _, entries in GROUPS for item in entries}
    if set(palettes) != expected:
        raise ValueError("The overview and official catalog must contain the same palettes.")
    render_overview(palettes, font)
    render_reference_comparison(palettes, font)
    render_cool_pair(palettes, font)


if __name__ == "__main__":
    main()

"""Export the worked study to SVG, editable PPTX or PNG; defaults to SVG + EHJ."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET


HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
SVG = "http://www.w3.org/2000/svg"
COLOR_OPTIONS = (
    ("B-pine-sage", "pine-sage"),
    ("C-ink-coral", "ink-coral"),
    ("D-mulberry-lilac", "mulberry-lilac"),
)
REFERENCE_PALETTES = (
    ("1-navy-brick", "navy-brick"),
    ("2-navy-amber", "navy-amber"),
    ("4-iron-steel", "iron-steel"),
    ("5-indigo-berry", "indigo-berry"),
)
V01_PALETTES = ("ehj-default", "blue-teal-jade", "indigo-violet", "burgundy-rose-gold")
PALETTE_GROUPS = {
    "v01-palettes": [(key, key) for key in V01_PALETTES],
    "color-options": COLOR_OPTIONS,
    "reference-palettes": REFERENCE_PALETTES,
}
ET.register_namespace("", SVG)


def element(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", {
        key.replace("_", "-"): str(value) for key, value in attrs.items()
    })


def text(parent, x, y, value, size, **attrs):
    element(parent, "text", x=x, y=y, font_size=size, **attrs).text = value


def line(parent, x1, y1, x2, y2, color, width=1):
    element(parent, "line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=color, stroke_width=width)


def add_panel(parent, x, y, width, height, header, color, wash, rule):
    group = element(parent, "g", id=header.lower().replace(" ", "-"))
    element(group, "rect", x=x, y=y, width=width, height=height, rx=19,
            fill=f"url(#{wash})", stroke=rule, stroke_width=1.5)
    # Only the top corners of each section bar are rounded.
    element(group, "path", d=f"M{x + 19},{y} h{width - 38} q19,0 19,19 v48 "
            f"h{-width} v-48 q0,-19 19,-19 z", fill=f"url(#{color})")
    text(group, x + 28, y + 45, header, 34, fill="#FFFFFF")
    return group


def add_gradients(svg, palette):
    defs = element(svg, "defs")
    for name, values in palette["gradient_roles"].items():
        grad = element(defs, "linearGradient", id=name,
                       **{key: f"{values[key] * 100}%" for key in ("x1", "y1", "x2", "y2")})
        for stop in values["stops"]:
            element(grad, "stop", offset=f"{stop['offset'] * 100}%", stop_color=stop["color"],
                    stop_opacity=stop.get("opacity", 1))


def add_population(svg, evidence, rule):
    panel = add_panel(svg, 56, 201, 445, 684, "Eligible cohorts", "header-left", "left-wash", rule)
    study = evidence["study"]
    text(panel, 84, 319, f"Patients aged {study['age_min_years']}–{study['age_max_years']}", 30)
    text(panel, 84, 358, "Drug-eluting stent at PCI", 27)
    text(panel, 84, 392, "and dual antiplatelet therapy", 27)
    line(panel, 84, 420, 473, 420, rule, 2)
    for y, cohort in zip([491, 636], evidence["cohorts"]):
        group = element(panel, "g", id=f"eligible-{cohort['id']}")
        text(group, 84, y, f"{cohort['eligible_n']:,}", 54)
        text(group, 84, y + 37, f"{cohort['name']}  ·  {cohort['start_year']}–{cohort['end_year']}", 28)
        purpose = "Development & internal testing" if cohort["id"] == "mayo" else "External validation"
        text(group, 84, y + 70, purpose, 25)
    line(panel, 84, 730, 473, 730, rule, 2)
    model, prediction = evidence["model"], evidence["prediction"]
    text(panel, 84, 777, f"{model['feature_lookback_years']} years of pre-PCI records", 28)
    text(panel, 84, 814, "and baseline clinical data", 28)
    day = prediction["event_ascertainment_starts_on_post_pci_day"]
    text(panel, 84, 856, f"Events counted from day {day}.", 25)


def add_external(svg, evidence, palette):
    rule = palette["solid_roles"]["panel-rule"]
    accent = palette["data_accents"]
    panel = add_panel(svg, 525, 201, 1219, 684, "External validation", "header-right", "right-wash", rule)
    external_cohort = next(c for c in evidence["cohorts"] if c["id"] == "oneflorida")
    text(panel, 553, 318, f"{external_cohort['name']} test set  ·  {external_cohort['test_n']:,} patients", 33)
    text(panel, 553, 357, evidence["metric"]["label"] + " with 95% confidence intervals", 28)
    text(panel, 553, 430, "Month", 26)
    horizons = evidence["prediction"]["horizons_months"]
    rows = {(r["outcome_id"], r["horizon_months"]): r for r in evidence["results"]
            if r["cohort_id"] == "oneflorida"}
    outcomes = [(o["id"], o["label"]) for o in evidence["outcomes"]]
    if set(rows) != {(key, m) for key, _ in outcomes for m in horizons}:
        raise ValueError("External validation requires a row per endpoint and horizon.")

    # Aligned rows are discrete horizons. Equal spacing does not imply equal elapsed time.
    y_rows = [479 + 61 * i for i in range(len(horizons))]
    solids = palette["solid_roles"]
    element(panel, "rect", x=546, y=y_rows[-1] - 25, width=1177, height=51, rx=8,
            fill=solids.get("row-highlight", solids["highlight"]), opacity=0.34)
    for month, y in zip(horizons, y_rows):
        text(panel, 592, y + 10, str(month), 31, text_anchor="middle")
    line(panel, 553, 445, 1716, 445, rule, 2)
    line(panel, 1171, 407, 1171, 807, rule, 2)
    axes = [("circle", accent["primary"], 664), ("square", accent["comparator"], 1205)]
    for (endpoint, label), (shape, color, left) in zip(outcomes, axes):
        group = element(panel, "g", id=f"plot-{endpoint}")
        text(group, left + 5, 427, label, 34)
        position = lambda value: left + (value - 0.65) / 0.30 * 247
        for tick in [0.70, 0.80, 0.90]:
            x = position(tick)
            line(group, x, 452, x, 817, rule, 1.8)
            text(group, x, 851, f"{tick:.2f}", 24, text_anchor="middle")
        for month, y in zip(horizons, y_rows):
            row = rows[endpoint, month]
            lo, hi, estimate = row["ci_lower"], row["ci_upper"], row["estimate"]
            if not 0.65 <= lo <= estimate <= hi <= 0.95:
                raise ValueError(f"{endpoint}, {month} months: interval outside plot limits")
            mark = element(group, "g", id=f"{endpoint}-m{month}", data_source=row["source_id"])
            line(mark, position(lo), y, position(hi), y, color, 4)
            for limit in [lo, hi]:
                line(mark, position(limit), y - 7, position(limit), y + 7, color, 3)
            if shape == "circle":
                element(mark, "circle", cx=position(estimate), cy=y, r=7.5, fill=color)
            else:
                element(mark, "rect", x=position(estimate) - 6.8, y=y - 6.8, width=13.6,
                        height=13.6, fill=color)
            text(mark, left + 264, y + 9, f"{estimate:.2f} ({lo:.2f}–{hi:.2f})", 27)
    return rows


def figure(evidence, palette):
    svg = ET.Element(f"{{{SVG}}}svg", width="1800", height="1100", viewBox="0 0 1800 1100",
                     attrib={"role": "img", "aria-labelledby": "title desc",
                             "font-family": "Segoe UI, Arial, sans-serif",
                             "fill": palette["solid_roles"].get("text", palette["data_accents"]["comparator"])})
    title = "Predicting ischemic and bleeding events after PCI"
    element(svg, "title", id="title").text = title
    element(svg, "desc", id="desc").text = (
        "Transformer-DAPT development and external validation cohorts, with time-dependent "
        "concordance indices and 95% confidence intervals for six prediction horizons.")
    add_gradients(svg, palette)
    element(svg, "rect", width=1800, height=1100, fill="url(#page-wash)")
    text(svg, 56, 94, title, 61)
    model = evidence["model"]["name"]
    text(svg, 58, 150, f"{model} uses baseline records to estimate risk at six time points in the first year.", 31)
    rule = palette["solid_roles"]["panel-rule"]
    add_population(svg, evidence, rule)
    external = add_external(svg, evidence, palette)
    summary = element(svg, "g", id="twelve-month-finding")
    element(summary, "rect", x=56, y=914, width=1688, height=99, rx=16, fill="url(#conclusion-wash)")
    element(summary, "rect", x=56, y=928, width=7, height=70, rx=3.5, fill=palette["solid_roles"]["highlight"])
    month = evidence["prediction"]["ends_at_month"]
    ischemia, bleeding = (external[key, month]["estimate"] for key in ("ischemic", "bleeding"))
    text(summary, 88, 977, f"At {month} months, external concordance was {ischemia:.2f} for ischemic events and {bleeding:.2f} for bleeding.", 36)
    source = evidence["article"]
    text(svg, 58, 1069, "PCI, percutaneous coronary intervention.", 24)
    text(svg, 1741, 1069, "Abdelhameed et al.  ·  Fig. 4a & Table 3  ·  doi: " + source["doi"], 24, text_anchor="end")
    return ET.ElementTree(svg)


def export_formats(svg, formats, sharp_module):
    outputs = []
    for fmt in formats:
        output = svg.with_suffix("." + fmt)
        if fmt == "png":
            command = ["node", str(SKILL / "scripts" / "render_preview.cjs"), str(svg), str(output)]
            if sharp_module:
                command.extend(["--sharp-module", sharp_module])
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        elif fmt == "pptx":
            command = [sys.executable, str(SKILL / "scripts" / "export_editable_pptx.py"), str(svg), str(output)]
            subprocess.run(command, check=True)
        outputs.append(output)
    return outputs


def resolve_palette(choice, catalog):
    """Resolve a public atlas selection; historical filenames never supply numbers."""
    aliases = {"ehj": catalog["default_palette"]}
    for palette_id, palette in catalog["palettes"].items():
        aliases[palette_id] = palette_id
        aliases[str(palette["atlas_number"])] = palette_id
        aliases[palette["name_zh"].casefold()] = palette_id
    for stem, palette_id in COLOR_OPTIONS:
        aliases[stem.partition("-")[0].lower()] = palette_id

    token = (choice or catalog["default_palette"]).strip().casefold()
    number = token.removesuffix("号").strip()
    if 1 <= len(number) <= 2 and number.isascii() and number.isdecimal():
        token = str(int(number))
    return aliases.get(token)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    modes = cli.add_mutually_exclusive_group()
    modes.add_argument("--v01-palettes", action="store_const", dest="palette_group", const="v01-palettes",
                       help="Build the four original v0.1 palettes")
    modes.add_argument("--color-options", action="store_const", dest="palette_group", const="color-options",
                       help="Build pine-sage, ink-coral and mulberry-lilac with their existing filenames")
    modes.add_argument("--reference-palettes", action="store_const", dest="palette_group", const="reference-palettes",
                       help="Build navy-brick, navy-amber, iron-steel and indigo-berry with their existing filenames")
    modes.add_argument("--palette",
                       help="Atlas number 1–11, English palette ID, Chinese palette name, or EHJ (default)")
    cli.add_argument("--format", nargs="+", choices=("svg", "pptx", "png"), default=["svg"],
                     help="One or more requested output formats (default: svg)")
    cli.add_argument("--output-dir", type=Path, help="Override the default output directory")
    cli.add_argument("--sharp-module", help="Path to Sharp if unavailable to the bundled renderer")
    args = cli.parse_args()
    evidence = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
    catalog = json.loads((SKILL / "references" / "palettes.json").read_text(encoding="utf-8"))
    if args.palette_group:
        output_dir = args.output_dir or HERE / args.palette_group
        variants = PALETTE_GROUPS[args.palette_group]
    else:
        palette_id = resolve_palette(args.palette, catalog)
        if palette_id is None:
            cli.error("Unknown palette. Choose an atlas number from 1 to 11 or an English ID: "
                      + ", ".join(catalog["palettes"]))
        output_dir = args.output_dir or (HERE / "rebuild" if args.palette else HERE)
        variants = (("figure", palette_id),)
    palettes = catalog["palettes"]
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as staging:
        files = []
        for basename, palette_id in variants:
            svg = Path(staging) / f"{basename}.svg"
            figure(evidence, palettes[palette_id]).write(svg, encoding="utf-8", xml_declaration=True)
            files.extend(export_formats(svg, dict.fromkeys(args.format), args.sharp_module))
        for file in files:
            # Publish with the output directory's permissions on Windows.
            with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as published:
                with file.open("rb") as source:
                    shutil.copyfileobj(source, published)
            Path(published.name).replace(output_dir / file.name)
            print(f"Wrote {output_dir / file.name}")


if __name__ == "__main__":
    main()

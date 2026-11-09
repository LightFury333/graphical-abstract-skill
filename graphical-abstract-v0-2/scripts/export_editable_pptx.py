#!/usr/bin/env python3
"""Export a static graphical-abstract SVG to one editable PowerPoint slide."""

import argparse
import base64
from functools import lru_cache
from io import BytesIO
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageColor, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt


NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
STYLE = set(
    "fill stroke color stroke-width fill-opacity stroke-opacity opacity "
    "stroke-linecap stroke-linejoin fill-rule text-anchor font-family font-size "
    "font-weight font-style display visibility".split()
)
ATTRS = {
    "svg": {"viewBox", "width", "height", "version", "role", "preserveAspectRatio"},
    "g": set(),
    "rect": {"x", "y", "width", "height", "rx", "ry"},
    "circle": {"cx", "cy", "r"},
    "ellipse": {"cx", "cy", "rx", "ry"},
    "line": {"x1", "y1", "x2", "y2"},
    "path": {"d"},
    "polygon": {"points"},
    "polyline": {"points"},
    "text": {"x", "y", "dx", "dy"},
    "image": {"x", "y", "width", "height", "href", "preserveAspectRatio"},
}
DEFAULTS = {
    "fill": "#000000",
    "stroke": "none",
    "stroke-width": "1",
    "color": "#000000",
    "font-family": "Arial",
    "font-size": "16",
    "text-anchor": "start",
}
DRAW = 1000  # local freeform units per viewBox unit


def xml(tag, parent=None, **attrs):
    node = OxmlElement(tag)
    for key, value in attrs.items():
        node.set(key, str(value))
    if parent is not None:
        parent.append(node)
    return node


def local(name):
    return name.rsplit("}", 1)[-1]


def length(value):
    value = str(value).strip()
    match = re.fullmatch(f"({NUMBER})(px|pt|mm|cm|in)?", value)
    if not match:
        raise ValueError(f"Unsupported SVG length {value!r}; use a number or absolute length.")
    return (
        float(match[1])
        * {None: 1, "px": 1, "pt": 96 / 72, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}[
            match[2]
        ]
    )


def fraction(value):
    v = str(value).strip()
    return float(v[:-1]) / 100 if v.endswith("%") else float(v)


def color(value):
    try:
        rgb = ImageColor.getrgb(value.strip())
    except ValueError as exc:
        raise ValueError(f"Unsupported SVG color {value!r}. Use RGB or hex.") from exc
    if len(rgb) != 3:
        raise ValueError("Use fill-opacity or stroke-opacity for alpha.")
    return "".join(f"{n:02X}" for n in rgb)


def style(node):
    decls = {}
    for part in node.get("style", "").split(";"):
        if not part.strip():
            continue
        key, sep, value = part.partition(":")
        if not sep:
            raise ValueError("Malformed inline style.")
        decls[key.strip()] = value.strip()
    return decls


def xy_tokens(value):
    tokens = re.findall(f"[A-Za-z]|{NUMBER}", value)
    if re.sub(rf"[A-Za-z]|{NUMBER}|[\s,]", "", value):
        raise ValueError(f"Unrecognized path or points characters in {value[:60]!r}.")
    return tokens


def transform(parent, value):
    scale, ox, oy = parent
    if not value:
        return parent
    for chunk in re.finditer(r"\s*(translate|scale)\s*\(([^)]*)\)\s*,?\s*|.", value):
        kind, args = chunk.groups()
        if not kind:
            raise ValueError(
                "Unsupported transform. Flatten rotation, skew, matrix, or nonuniform scaling."
            )
        nums = [length(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if not 1 <= len(nums) <= 2:
            raise ValueError(f"Invalid {kind} transform.")
        if kind == "translate":
            ox += nums[0] * scale
            oy += (nums[1] if len(nums) == 2 else 0) * scale
        else:
            if nums[0] <= 0 or (len(nums) == 2 and nums[0] != nums[1]):
                raise ValueError("Only positive uniform scales are supported.")
            scale *= nums[0]
    return scale, ox, oy


def path_commands(value):
    """Expand repeated and relative commands to absolute DrawingML points."""
    tokens = xy_tokens(value)
    result, command = [], None
    x = y = sx = sy = 0.0
    index = 0
    previous, ctrl = "", (0, 0)
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
        if not command:
            raise ValueError("Invalid SVG path command.")
        op = command.upper()
        if not result and op != "M":
            raise ValueError("SVG path must begin with M.")
        if op == "Z":
            result.append(("close", []))
            x, y = sx, sy
            command, previous = None, op
            continue
        counts = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "T": 2, "C": 6, "S": 4}
        if op not in counts:
            raise ValueError(
                f"Path command {op!r} is unsupported; convert elliptical arcs to cubic Béziers."
            )
        end = index + counts[op]
        if end > len(tokens) or any(t.isalpha() for t in tokens[index:end]):
            raise ValueError(f"Incomplete {op} path command.")
        values = [float(t) for t in tokens[index:end]]
        index = end
        relative = command.islower()
        if op == "H":
            pts = [(values[0] + (x if relative else 0), y)]
        elif op == "V":
            pts = [(x, values[0] + (y if relative else 0))]
        else:
            pts = [
                (values[i] + (x if relative else 0), values[i + 1] + (y if relative else 0))
                for i in range(0, len(values), 2)
            ]
        if op in ("T", "S"):
            related = ("T", "Q") if op == "T" else ("S", "C")
            pts.insert(0, (2 * x - ctrl[0], 2 * y - ctrl[1]) if previous in related else (x, y))
        draw = {
            "M": "moveTo",
            "L": "lnTo",
            "H": "lnTo",
            "V": "lnTo",
            "Q": "quadBezTo",
            "T": "quadBezTo",
            "C": "cubicBezTo",
            "S": "cubicBezTo",
        }[op]
        result.append((draw, pts))
        x, y = pts[-1]
        if len(pts) > 1:
            ctrl = pts[-2]
        if op == "M":
            sx, sy = x, y
            command = "l" if relative else "L"
        previous = op
    return result


def rgb_node(parent, rgb, opacity):
    node = xml("a:srgbClr", parent, val=rgb)
    if opacity != 1:
        xml("a:alpha", node, val=round(max(0, min(1, opacity)) * 100000))
    return node


def gradient_fill(grad, w, h, opacity):
    """Map the SVG bounding-box projection to DrawingML's physical angle and full extents."""
    if grad.get("gradientUnits", "objectBoundingBox") != "objectBoundingBox":
        raise ValueError("Use objectBoundingBox for linear gradients.")
    if (
        set(grad.attrib) - {"id", "x1", "x2", "y1", "y2", "gradientUnits", "spreadMethod"}
        or grad.get("spreadMethod", "pad") != "pad"
    ):
        raise ValueError("Expand gradient inheritance/transforms and use pad spread.")
    x1, y1, x2, y2 = (
        fraction(grad.get(k, v))
        for k, v in (("x1", "0"), ("y1", "0"), ("x2", "1"), ("y2", "0"))
    )
    dx, dy = x2 - x1, y2 - y1
    norm = dx * dx + dy * dy
    if not norm or w <= 0 or h <= 0:
        raise ValueError("A linear gradient needs a measurable bounding box and direction.")
    stops = []
    for node in grad:
        if local(node.tag) != "stop":
            raise ValueError("Use explicit linear-gradient stops.")
        props = {**node.attrib, **style(node)}
        if set(props) - {"id", "offset", "stop-color", "stop-opacity", "style"}:
            raise ValueError("Unsupported gradient-stop style.")
        position = max(0, min(1, fraction(props.get("offset", "0"))))
        if stops:
            position = max(position, stops[-1][0])
        stops.append(
            (
                position,
                color(props.get("stop-color", "black")),
                fraction(props.get("stop-opacity", 1)) * opacity,
            )
        )
    if not stops:
        raise ValueError("Gradient has no stops.")
    corners = [
        ((x - x1) * dx + (y - y1) * dy) / norm for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))
    ]
    low, high = min(corners), max(corners)

    def at(t):
        if t <= stops[0][0]:
            return stops[0][1:]
        for a, b in zip(stops, stops[1:]):
            if t < b[0]:
                f = (t - a[0]) / (b[0] - a[0])
                channels = [
                    round(int(a[1][i : i + 2], 16) * (1 - f) + int(b[1][i : i + 2], 16) * f)
                    for i in (0, 2, 4)
                ]
                return "".join(f"{v:02X}" for v in channels), a[2] * (1 - f) + b[2] * f
        return stops[-1][1:]

    fill = xml("a:gradFill", rotWithShape="1")
    gl = xml("a:gsLst", fill)
    samples = (
        [(low, *at(low))] + [s for s in stops if low <= s[0] <= high] + [(high, *at(high))]
    )
    for t, rgb, alpha in samples:
        rgb_node(xml("a:gs", gl, pos=round((t - low) / (high - low) * 100000)), rgb, alpha)
    degrees = math.degrees(math.atan2(dy / h, dx / w)) % 360
    xml("a:lin", fill, ang=round(degrees * 60000) % 21600000, scaled="0")
    return fill


def paint(value, alpha, props, gradients, w, h):
    if value == "none":
        return xml("a:noFill")
    match = re.fullmatch(r"url\(\s*#([^)\s]+)\s*\)", value)
    if match:
        if match[1] not in gradients:
            raise ValueError(f"Missing or unsupported gradient #{match[1]}.")
        return gradient_fill(gradients[match[1]], w, h, alpha)
    fill = xml("a:solidFill")
    rgb_node(fill, color(props["color"] if value == "currentColor" else value), alpha)
    return fill


@lru_cache(maxsize=128)
def font_metrics(family, bold, italic):
    """Return high-resolution text metrics without embedding a font file."""
    names = {
        "segoe ui": ["segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"],
        "arial": ["arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"],
        "calibri": ["calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"],
    }
    candidates = [family]
    if family.lower() in names:
        candidates.insert(0, names[family.lower()][int(bold) + 2 * int(italic)])
    if shutil.which("fc-match"):
        pattern = family + (":style=Bold" if bold else "")
        if italic:
            pattern += ":slant=italic"
        proc = subprocess.run(
            ["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True
        )
        if proc.returncode == 0 and proc.stdout:
            candidates.append(proc.stdout)
    for name in candidates:
        try:
            return ImageFont.truetype(name, 256)
        except OSError:
            continue
    return None


def path_bounds(commands):
    points = []
    start = last = (0.0, 0.0)
    for op, pts in commands:
        if op == "moveTo":
            start = pts[0]
        if op == "close":
            last = start
            continue
        points.append(pts[-1])
        if op in ("quadBezTo", "cubicBezTo"):
            curve = [last] + pts
            for axis in (0, 1):
                v = [p[axis] for p in curve]
                if len(v) == 3:
                    a, b, c = 0, v[0] - 2 * v[1] + v[2], v[1] - v[0]
                else:
                    a, b, c = (
                        -v[0] + 3 * v[1] - 3 * v[2] + v[3],
                        2 * (v[0] - 2 * v[1] + v[2]),
                        v[1] - v[0],
                    )
                if abs(a) < 1e-12:
                    roots = [] if abs(b) < 1e-12 else [-c / b]
                else:
                    d = b * b - 4 * a * c
                    roots = (
                        []
                        if d < 0
                        else [(-b - math.sqrt(d)) / (2 * a), (-b + math.sqrt(d)) / (2 * a)]
                    )
                for t in roots:
                    if 0 < t < 1:
                        levels = curve
                        while len(levels) > 1:
                            levels = [
                                tuple((1 - t) * x + t * y for x, y in zip(p, q))
                                for p, q in zip(levels, levels[1:])
                            ]
                        points.append(levels[0])
        last = pts[-1]
    if not points:
        raise ValueError("Empty SVG path.")
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


class InvalidElement(ValueError):
    """Identify the first SVG element that could not be represented."""


class Figure:
    def __init__(self, root, slide_width):
        if local(root.tag) != "svg":
            raise ValueError("The input root must be svg.")
        viewbox = root.get("viewBox")
        if viewbox:
            parts = [float(s) for s in re.split(r"[\s,]+", viewbox.strip())]
            if len(parts) != 4:
                raise ValueError("viewBox must contain x, y, width and height.")
            self.x0, self.y0, w, h = parts
            if min(w, h) <= 0:
                raise ValueError("viewBox dimensions must be positive.")
            if "width" in root.attrib and "height" in root.attrib:
                vw, vh = root.get("width"), root.get("height")
                if not (vw.endswith("%") or vh.endswith("%")) and not math.isclose(
                    length(vw) / length(vh), w / h, rel_tol=0.002
                ):
                    raise ValueError(
                        "Set viewport and viewBox to the same aspect ratio before export."
                    )
        else:
            self.x0 = self.y0 = 0
            w, h = length(root.get("width", "0")), length(root.get("height", "0"))
        if min(w, h) <= 0 or not 1 <= slide_width <= 56 or not 1 <= slide_width * h / w <= 56:
            raise ValueError(
                "The viewBox must be positive; both slide dimensions must be 1–56 inches."
            )
        self.prs = Presentation()
        self.prs.slide_width = Inches(slide_width)
        self.prs.slide_height = Inches(slide_width * h / w)
        self.scale = self.prs.slide_width / w
        self.slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self.gradients = {}
        seen = set()
        for node in root.iter():
            if node.get("id"):
                key = node.get("id")
                if key in seen:
                    raise ValueError(f"Duplicate SVG id: {key}")
                seen.add(key)
                if local(node.tag) == "linearGradient":
                    self.gradients[key] = node
            if local(node.tag) in {"style", "script"}:
                raise ValueError(
                    "Use explicit inline paints; CSS style blocks and scripts are unsupported."
                )
        self.warnings = set()
        self.visit(root, DEFAULTS, (1.0, -self.x0, -self.y0), "")
        if not self.slide.shapes:
            raise ValueError("No visible objects were found.")

    def u(self, value):
        return round(value * self.scale)

    def visit(self, node, parent, trans, group):
        tag = local(node.tag)
        if tag in {"title", "desc", "defs", "metadata"}:
            return
        label = node.get("id", group or tag)
        try:
            if tag not in ATTRS:
                raise ValueError(
                    f"Unsupported <{tag}>; simplify it to native shapes or an explicit PNG/JPEG asset."
                )
            decls = style(node)
            permitted = STYLE | ATTRS[tag] | {"id", "style", "transform"}
            attrs = {
                local(k) for k in node.attrib if not local(k).startswith(("data-", "aria-"))
            }
            invalid = (attrs - permitted) | (decls.keys() - STYLE)
            if invalid:
                raise ValueError(
                    "Unsupported attribute/style: "
                    + ", ".join(sorted(invalid))
                    + ". Expand it first."
                )
            props = {**parent, **{k: v for k, v in node.attrib.items() if k in STYLE}, **decls}
            for prop in STYLE:
                if props.get(prop) == "inherit":
                    props[prop] = parent.get(prop, DEFAULTS.get(prop, ""))
            if props.get("display") == "none":
                return
            transform_here = transform(trans, node.get("transform"))
            if tag in ("svg", "g"):
                if tag == "svg" and group:
                    raise ValueError("Nested SVG viewports must be flattened.")
                if fraction(props.get("opacity", 1)) != 1:
                    raise ValueError(
                        "Group opacity on overlapping objects must be flattened before export."
                    )
                for child in node:
                    self.visit(child, props, transform_here, node.get("id", group or "Figure"))
                return
            if props.get("visibility") in ("hidden", "collapse"):
                return
            if tag != "text":
                for child in node:
                    if local(child.tag) not in {"title", "desc", "metadata"}:
                        raise ValueError(f"Unsupported child <{local(child.tag)}> inside a shape.")
            shape = self.draw(node, tag, props, transform_here)
            if shape is not None:
                caption = (node.text or "").strip()[:70] if tag == "text" else ""
                shape.name = f"{label} · {caption or tag}"
        except InvalidElement:
            raise
        except (ValueError, KeyError) as exc:
            raise InvalidElement(f"<{tag}> ({label}): {exc}") from exc

    def draw(self, node, tag, p, tr):
        scale, ox, oy = tr
        val = lambda k: length(node.get(k, 0))
        x = lambda k: val(k) * scale + ox
        y = lambda k: val(k) * scale + oy
        shapes = self.slide.shapes
        if tag == "text":
            return self.text(node, p, tr)
        if tag == "image":
            return self.picture(node, p, tr)
        if tag == "line":
            x1, y1, x2, y2 = x("x1"), y("y1"), x("x2"), y("y2")
            shape = shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT, self.u(x1), self.u(y1), self.u(x2), self.u(y2)
            )
            self.style_shape(shape, p, scale, abs(x2 - x1), abs(y2 - y1), line_only=True)
            return shape
        if tag in ("path", "polyline", "polygon"):
            if tag == "path":
                cmds = path_commands(node.get("d", ""))
            else:
                coords = [float(t) for t in xy_tokens(node.get("points", ""))]
                if len(coords) < 4 or len(coords) % 2:
                    raise ValueError("Provide x,y pairs for polyline/polygon.")
                cmds = [
                    ("moveTo" if i == 0 else "lnTo", [(coords[i], coords[i + 1])])
                    for i in range(0, len(coords), 2)
                ]
                if tag == "polygon":
                    cmds.append(("close", []))
            if not cmds:
                return None
            cmds = [
                (op, [(xi * scale + ox, yi * scale + oy) for xi, yi in pts]) for op, pts in cmds
            ]
            left, top, w, h = path_bounds(cmds)
            shape = shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                self.u(left),
                self.u(top),
                max(1, self.u(w)),
                max(1, self.u(h)),
            )
            geom = xml("a:custGeom")
            for sub in ("avLst", "gdLst", "ahLst", "cxnLst"):
                xml("a:" + sub, geom)
            xml("a:rect", geom, l="l", t="t", r="r", b="b")
            path = xml(
                "a:path",
                xml("a:pathLst", geom),
                w=max(1, round(w * DRAW)),
                h=max(1, round(h * DRAW)),
            )
            for op, pts in cmds:
                seg = xml("a:" + op, path)
                for px, py in pts:
                    xml("a:pt", seg, x=round((px - left) * DRAW), y=round((py - top) * DRAW))
            sp = shape._element.spPr
            sp.replace(sp.find(qn("a:prstGeom")), geom)
        else:
            if tag == "rect":
                left, top, w, h = x("x"), y("y"), val("width") * scale, val("height") * scale
                rx = length(node.get("rx", node.get("ry", "0"))) * scale
                ry = length(node.get("ry", node.get("rx", "0"))) * scale
                if rx != ry:
                    raise ValueError(
                        "Use equal rounded-corner radii or convert the rectangle to a path."
                    )
                kind = MSO_SHAPE.ROUNDED_RECTANGLE if rx else MSO_SHAPE.RECTANGLE
            else:
                rx = val("r" if tag == "circle" else "rx") * scale
                ry = val("r" if tag == "circle" else "ry") * scale
                left, top, w, h = x("cx") - rx, y("cy") - ry, rx * 2, ry * 2
                kind = MSO_SHAPE.OVAL
            if min(w, h) < 0:
                raise ValueError("Negative shape dimensions.")
            if not w or not h:
                return None
            shape = shapes.add_shape(kind, self.u(left), self.u(top), self.u(w), self.u(h))
            if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
                shape.adjustments[0] = min(0.5, rx / min(w, h))
        self.style_shape(shape, p, scale, w, h)
        return shape

    def style_shape(self, shape, p, scale, w, h, line_only=False):
        if p.get("fill-rule", "nonzero") != "nonzero":
            raise ValueError("Convert even-odd compound paths to nonzero paths.")
        sp = shape._element.spPr
        for child in list(sp):
            if local(child.tag) in {"noFill", "solidFill", "gradFill", "ln"}:
                sp.remove(child)
        opacity = fraction(p.get("opacity", 1))
        if not line_only:
            sp.append(
                paint(
                    p["fill"],
                    opacity * fraction(p.get("fill-opacity", 1)),
                    p,
                    self.gradients,
                    w,
                    h,
                )
            )
        width = length(p["stroke-width"]) * scale
        cap = {"butt": "flat", "round": "rnd", "square": "sq"}[p.get("stroke-linecap", "butt")]
        ln = xml("a:ln", sp, w=max(0, self.u(width)), cap=cap)
        stroke = p["stroke"] if width else "none"
        ln.append(
            paint(
                stroke, opacity * fraction(p.get("stroke-opacity", 1)), p, self.gradients, w, h
            )
        )
        join = p.get("stroke-linejoin", "miter")
        if join not in ("round", "bevel", "miter"):
            raise ValueError(f"Unsupported line join {join}.")
        xml("a:" + join, ln)
        style_node = shape._element.find(qn("p:style"))
        if style_node is not None:
            shape._element.remove(style_node)
        # Drawing shapes should not acquire empty editable text frames.
        tx = shape._element.find(qn("p:txBody"))
        if tx is not None:
            shape._element.remove(tx)

    def text(self, node, p, tr):
        if len(node):
            raise ValueError(
                "Use one explicit <text x='…' y='…'> per line; flatten tspans/textPath."
            )
        if p["stroke"] != "none" or p["fill"].startswith("url("):
            raise ValueError("Editable text requires a solid fill and no outline.")
        if p["fill"] == "none":
            return None
        s = re.sub(r"[\t\r\n ]+", " ", node.text or "").strip(" ")
        if not s:
            return None
        mult, ox, oy = tr
        x = (length(node.get("x", 0)) + length(node.get("dx", 0))) * mult + ox
        y = (length(node.get("y", 0)) + length(node.get("dy", 0))) * mult + oy
        size = length(p["font-size"]) * mult
        if size <= 0:
            raise ValueError("Text size must be positive.")
        family = p["font-family"].split(",")[0].strip(" '\"")
        family = {
            "sans-serif": "Arial",
            "serif": "Times New Roman",
            "monospace": "Courier New",
        }.get(family, family)
        weight = p.get("font-weight", "400")
        bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 600)
        italic = p.get("font-style", "normal") in ("italic", "oblique")
        metric = font_metrics(family, bold, italic)
        if metric is None:
            self.warnings.add(
                f"Font metrics unavailable for {family}; verify rendering on the target machine."
            )
        width = (
            metric.getlength(s) / 256
            if metric
            else sum(0.98 if ord(c) > 255 else 0.60 for c in s)
        ) * size + size * 0.18
        anchor = p.get("text-anchor", "start")
        align = {"start": PP_ALIGN.LEFT, "middle": PP_ALIGN.CENTER, "end": PP_ALIGN.RIGHT}[
            anchor
        ]
        left = x - {"start": 0, "middle": width / 2, "end": width}[anchor]
        # DrawingML top-anchored text uses the font ascent for its first baseline.
        ascent = metric.getmetrics()[0] / 256 if metric else 1.04
        # Calibrated against PowerPoint 16 at three Segoe UI font sizes.
        baseline_adjustment = 0.108 if family.casefold() == "segoe ui" else 0
        top = y - (ascent - baseline_adjustment) * size
        tb = self.slide.shapes.add_textbox(
            self.u(left), self.u(top), self.u(width), self.u(size * 1.55)
        )
        frame = tb.text_frame
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.word_wrap = False
        frame.vertical_anchor = MSO_ANCHOR.TOP
        frame.auto_size = None
        paragraph = frame.paragraphs[0]
        paragraph.alignment = align
        paragraph.space_before = paragraph.space_after = Pt(0)
        run = paragraph.add_run()
        run.text = s
        run.font.name = family
        run.font.size = Pt(size * self.scale / 12700)
        run.font.bold = bold
        run.font.italic = italic
        rp = run._r.get_or_add_rPr()
        rgb = xml("a:solidFill")
        alpha = fraction(p.get("opacity", 1)) * fraction(p.get("fill-opacity", 1))
        rgb_node(rgb, color(p["color"] if p["fill"] == "currentColor" else p["fill"]), alpha)
        rp.insert(0, rgb)
        for suffix in ("ea", "cs"):
            xml("a:" + suffix, rp, typeface=family)
        return tb

    def picture(self, node, p, tr):
        if fraction(p.get("opacity", 1)) != 1:
            raise ValueError("Bake image opacity into the image before export.")
        href = node.get("href", node.get("{http://www.w3.org/1999/xlink}href", ""))
        match = re.fullmatch(r"data:image/(?:png|jpeg);base64,(.*)", href, flags=re.S)
        if not match:
            raise ValueError(
                "Embed a PNG/JPEG as a base64 data URI; external images and SVG pictures are unsupported."
            )
        blob = base64.b64decode(re.sub(r"\s+", "", match[1]), validate=True)
        mult, ox, oy = tr
        x, y = length(node.get("x", 0)) * mult + ox, length(node.get("y", 0)) * mult + oy
        w, h = length(node.get("width", 0)) * mult, length(node.get("height", 0)) * mult
        if min(w, h) <= 0:
            raise ValueError("An image needs a positive width and height.")
        mode = node.get("preserveAspectRatio", "xMidYMid meet")
        if mode in ("xMidYMid", "xMidYMid meet"):
            with Image.open(BytesIO(blob)) as image:
                iw, ih = image.size
            factor = min(w / iw, h / ih)
            x, y = x + (w - iw * factor) / 2, y + (h - ih * factor) / 2
            w, h = iw * factor, ih * factor
        elif mode != "none":
            raise ValueError("Use preserveAspectRatio='xMidYMid meet' or 'none' for images.")
        return self.slide.shapes.add_picture(
            BytesIO(blob), self.u(x), self.u(y), self.u(w), self.u(h)
        )


def export_svg(source, destination, force=False, slide_width=12.0):
    source, destination = Path(source), Path(destination)
    if (
        source.suffix.lower() != ".svg"
        or destination.suffix.lower() != ".pptx"
        or source.resolve() == destination.resolve()
    ):
        raise ValueError("Use separate input .svg and output .pptx paths.")
    if destination.exists() and not force:
        raise FileExistsError(f"Output exists: {destination}; use --force to replace it.")
    data = source.read_bytes()
    if b"<!doctype" in data.lower() or b"<!entity" in data.lower():
        raise ValueError("SVG entity and DOCTYPE declarations are unsupported.")
    figure = Figure(ET.fromstring(data), slide_width)
    figure.prs.core_properties.title = source.stem
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A sibling inherits normal directory access and can be published atomically.
    staged = destination.parent / (".ga-export-" + secrets.token_hex(16) + ".pptx")
    stream = staged.open("xb")
    try:
        with stream:
            figure.prs.save(stream)
        if len(Presentation(staged).slides) != 1:
            raise ValueError("The saved deck did not validate as a single slide.")
        if force:
            os.replace(staged, destination)
        elif os.name == "nt":
            os.rename(staged, destination)  # Windows refuses an existing destination.
        else:
            os.link(staged, destination)
    finally:
        staged.unlink(missing_ok=True)
    return len(figure.slide.shapes), sorted(figure.warnings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--force", action="store_true", help="Replace the output after successful validation."
    )
    parser.add_argument(
        "--width-inches", type=float, default=12.0, help="Slide width in inches (default 12)."
    )
    args = parser.parse_args()
    try:
        count, warnings = export_svg(args.input, args.output, args.force, args.width_inches)
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.exit(2, f"Export failed: {exc}\n")
    print(f"Saved one slide with {count} objects to {args.output}.")
    for warning in warnings:
        print(f"Note: {warning}")


if __name__ == "__main__":
    main()

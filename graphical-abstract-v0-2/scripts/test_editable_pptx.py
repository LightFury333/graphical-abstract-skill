"""Regression checks for the portable SVG → editable PowerPoint exporter."""

import base64
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
from pptx import Presentation

from export_editable_pptx import export_svg, path_bounds, path_commands


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="180" height="110"
  viewBox="0 0 180 110" font-family="Arial" font-size="11">
  <defs><linearGradient id="header" x1="0" y1="0" x2="100%" y2="0">
    <stop offset="0" stop-color="#173858"/><stop offset=".52" stop-color="#275777"/>
    <stop offset="1" stop-color="#317A75"/></linearGradient></defs>
  <g id="results" transform="translate(4 3)">
    <rect x="2" y="2" width="168" height="21" rx="3" fill="url(#header)"/>
    <text x="6" y="17" fill="white">Model A · 95% CI</text>
    <line x1="16" y1="47" x2="62" y2="47" stroke="#275777" stroke-width="2"/>
    <circle cx="33" cy="47" r="3" fill="#275777"/>
    <path d="M80 45 h19 q3 0 3 3 v8 h-22 z" fill="#317A75"/>
    <text x="87" y="83" text-anchor="end">0.74 (0.73–0.76)</text>
  </g></svg>"""


class NativePptxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.svg = self.root / "figure.svg"
        self.pptx = self.root / "figure.pptx"
        self.svg.write_text(SVG, encoding="utf-8")

    def package(self):
        with zipfile.ZipFile(self.pptx) as deck:
            return ET.fromstring(deck.read("ppt/slides/slide1.xml")), deck.namelist()

    def test_native_shapes_colors_text_and_gradients(self):
        before = self.svg.read_bytes()
        count, _ = export_svg(self.svg, self.pptx)
        self.assertEqual(count, 6)
        deck = Presentation(self.pptx)
        self.assertEqual(len(deck.slides), 1)
        self.assertAlmostEqual(deck.slide_width / deck.slide_height, 18 / 11, places=5)
        root, parts = self.package()
        self.assertFalse(any(name.startswith("ppt/media/") for name in parts))
        self.assertEqual(
            [t.text for t in root.findall(".//a:t", NS)],
            ["Model A · 95% CI", "0.74 (0.73–0.76)"],
        )
        self.assertEqual(len(root.findall(".//p:cxnSp", NS)), 1)
        self.assertEqual(len(root.findall(".//a:custGeom", NS)), 1)
        self.assertIsNotNone(root.find(".//a:quadBezTo", NS))
        stops = root.findall(".//a:gradFill/a:gsLst/a:gs", NS)
        self.assertIn(("52000", "275777"), [(x.get("pos"), x[0].get("val")) for x in stops])
        self.assertEqual(before, self.svg.read_bytes())

    def test_existing_output_survives_errors_and_explicit_replace(self):
        self.pptx.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            export_svg(self.svg, self.pptx)
        self.assertEqual(self.pptx.read_bytes(), b"original")
        self.svg.write_text(
            SVG.replace('transform="translate(4 3)"', 'filter="url(#glow)"'), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "filter"):
            export_svg(self.svg, self.pptx, force=True)
        self.assertEqual(self.pptx.read_bytes(), b"original")
        self.svg.write_text(SVG, encoding="utf-8")
        export_svg(self.svg, self.pptx, force=True)
        self.assertEqual(len(Presentation(self.pptx).slides), 1)
        self.assertFalse(list(self.root.glob(".ga-export-*.pptx")))

    def test_embedded_image_is_one_picture(self):
        img = BytesIO()
        Image.new("RGB", (2, 1), "green").save(img, format="PNG")
        url = "data:image/png;base64," + base64.b64encode(img.getvalue()).decode("ascii")
        self.svg.write_text(
            SVG.replace(
                "</svg>", f'<image x="4" y="90" width="30" height="10" href="{url}"/></svg>'
            ),
            encoding="utf-8",
        )
        count, _ = export_svg(self.svg, self.pptx)
        self.assertEqual(count, 7)
        root, parts = self.package()
        self.assertEqual(len(root.findall(".//p:pic", NS)), 1)
        self.assertEqual(len([p for p in parts if p.startswith("ppt/media/")]), 1)

    def test_paths_limits_and_curve_extrema(self):
        commands = path_commands("M0 0 Q50 100 100 0")
        self.assertEqual(path_bounds(commands), (0.0, 0.0, 100.0, 50.0))
        with self.assertRaisesRegex(ValueError, "elliptical arcs"):
            path_commands("M 0 0 A 2 2 0 0 0 4 4")

    def test_unsimplified_content_fails_with_context(self):
        for fragment, expected in [
            ('<use href="#header"/>', "Unsupported <use>"),
            ('<text x="0" y="10"><tspan>Nested</tspan></text>', "tspans"),
            (
                '<image x="0" y="0" width="30" height="20" href="https://example.com/plot.png"/>',
                "data URI",
            ),
        ]:
            with self.subTest(fragment=fragment):
                self.svg.write_text(
                    SVG.replace("</svg>", fragment + "</svg>"), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, expected):
                    export_svg(self.svg, self.pptx)
                self.assertFalse(self.pptx.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

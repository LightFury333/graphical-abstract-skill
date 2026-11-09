#!/usr/bin/env python3
"""Regression checks; all fixtures and outputs live in a temporary directory.

python test_helpers.py
SHARP_MODULE=/path/to/sharp NODE_BINARY=/path/to/node python test_helpers.py
Renderer checks are skipped if Node or Sharp cannot be located.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="180" height="110" viewBox="0 0 180 110" font-family="Arial" font-size="8">
<defs><linearGradient id="g"><stop offset="0" stop-color="#7247A6"/><stop offset="1" style="stop-color: #ff861c; stop-opacity: 0.8"/></linearGradient></defs>
<rect x="0" y="0" width="180" height="110" fill="url(#g)"/>
<path d="M 0 1 L 10 2" stroke="#7247a6" fill="none"/>
<text x="4" y="30" fill="#000000" font-weight="700">Synthetic Score R 0.731; #7247A6<tspan x="4" dy="12">Synthetic HR 1.42 (1.05–1.92)</tspan></text>
<text x="4" y="66" fill="#FFFFFF">Synthetic Score S 0.704</text>
<metadata type="application/json">{"text":"#7247A6","font_size":8,"borders":{"left":{"color":"#7247A6"}},"color":"#000000"}</metadata>
</svg>'''


class RecolorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="graphical-abstract-helper-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.svg"
        self.output = self.root / "output.svg"
        self.mapping = self.root / "mapping.json"
        self.source.write_text(SVG, encoding="utf-8")

    def call(self, mapping=None):
        self.mapping.write_text(json.dumps(mapping or {"#7247A6": "#155E75", "#FF861C": "#179B83"}), encoding="utf-8")
        return subprocess.run([sys.executable, str(HERE / "recolor_svg.py"), str(self.source), str(self.output), "--mapping", str(self.mapping)], capture_output=True, text=True, encoding="utf-8")

    def test_colors_only_source_and_text_preserved(self):
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(digest, hashlib.sha256(self.source.read_bytes()).hexdigest())
        report = json.loads(result.stdout)
        self.assertEqual(report["paint_replacements"], {"#7247A6": 2, "#FF861C": 1})
        self.assertEqual(report["invariants"]["geometry"], "unchanged")
        before, after = ET.parse(self.source).getroot(), ET.parse(self.output).getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        self.assertEqual([ET.tostring(n) for n in before.findall("s:text", ns)], [ET.tostring(n) for n in after.findall("s:text", ns)])
        self.assertEqual(before.find("s:path", ns).get("d"), after.find("s:path", ns).get("d"))
        metadata = json.loads(after.find("s:metadata", ns).text)
        self.assertEqual(metadata["text"], "#7247A6")
        self.assertEqual(metadata["borders"]["left"]["color"], "#155E75")
        self.assertEqual(metadata["color"], "#000000")

    def test_unknown_mapping_fails_without_output(self):
        result = self.call({"#123456": "#ABCDEF"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)
        self.assertFalse(self.output.exists())

    def test_black_and_white_cannot_be_remapped(self):
        for color in ("#000000", "#FFFFFF"):
            with self.subTest(color=color):
                result = self.call({color: "#123456"})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Protected", result.stderr)
                self.assertFalse(self.output.exists())

    def test_inherited_text_color_is_protected(self):
        inherited = SVG.replace('<text x="4" y="30" fill="#000000"', '<g fill="#7247A6"><text x="4" y="30"')
        inherited = inherited.replace('</tspan></text>', '</tspan></text></g>')
        self.source.write_text(inherited, encoding="utf-8")
        result = self.call()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("visible text paint", result.stderr)

    def test_gradient_text_is_protected(self):
        self.source.write_text(SVG.replace('fill="#000000"', 'fill="url(#g)"'), encoding="utf-8")
        result = self.call()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("visible text paint", result.stderr)

    def test_metadata_text_color_is_protected(self):
        self.source.write_text(SVG.replace('"color":"#000000"', '"color":"#7247A6"'), encoding="utf-8")
        result = self.call()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("text color in JSON metadata", result.stderr)

    def test_overwrite_refused(self):
        self.output.write_text("keep", encoding="utf-8")
        result = self.call()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep")

    def test_stylesheet_refused(self):
        self.source.write_text(SVG.replace("<defs>", "<style>text {fill:red}</style><defs>"), encoding="utf-8")
        result = self.call()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stylesheet", result.stderr)

    def test_invalid_hex_refused(self):
        result = self.call({"#7247A6": "#fff"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("six-digit hex", result.stderr)


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = os.environ.get("NODE_BINARY") or shutil.which("node")
        cls.sharp_module = os.environ.get("SHARP_MODULE")
        if not cls.node:
            raise unittest.SkipTest("Node unavailable")
        module = str(Path(cls.sharp_module).resolve()) if cls.sharp_module else "sharp"
        check = subprocess.run([cls.node, "-e", f"require({json.dumps(module)})"], cwd=HERE, capture_output=True)
        if check.returncode:
            raise unittest.SkipTest("Sharp unavailable; set SHARP_MODULE to test rendering")

    def test_render_dimensions_density_source_unchanged_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="graphical-abstract-render-test-") as temp:
            source, output = Path(temp) / "input.svg", Path(temp) / "output.png"
            source.write_text(SVG, encoding="utf-8")
            before = source.read_bytes()
            args = [self.node, str(HERE / "render_preview.cjs"), str(source), str(output), "--width", "360", "--density", "300"]
            if self.sharp_module:
                args += ["--sharp-module", self.sharp_module]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual((report["width"], report["height"], report["density_ppi"]), (360, 220, 300))
            data = output.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (360, 220))
            self.assertEqual(source.read_bytes(), before)
            overwrite = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(overwrite.returncode, 0)
            self.assertEqual(output.read_bytes(), data)
            square = Path(temp) / "square.png"
            args[3] = str(square)
            args += ["--height", "360"]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(struct.unpack(">II", square.read_bytes()[16:24]), (360, 360))


if __name__ == "__main__":
    unittest.main(verbosity=2)

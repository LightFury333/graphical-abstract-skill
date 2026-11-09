"""Offline end-to-end checks for selecting Transformer-DAPT palette numbers and IDs."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SKILL = Path(__file__).resolve().parents[1]
BUILDER = SKILL / "examples" / "transformer-dapt" / "build_figure.py"
CATALOG = SKILL / "references" / "palettes.json"
SVG = "{http://www.w3.org/2000/svg}"
ATLAS = (
    ("ehj-default", "EHJ 紫—酒红—橙"),
    ("blue-teal-jade", "蓝—青—绿"),
    ("indigo-violet", "靛蓝—紫"),
    ("burgundy-rose-gold", "酒红—玫瑰—金"),
    ("pine-sage", "松针绿—鼠尾草"),
    ("ink-coral", "墨蓝—珊瑚"),
    ("mulberry-lilac", "桑葚—丁香"),
    ("navy-brick", "深海蓝 × 砖红"),
    ("navy-amber", "藏青 × 琥珀金棕"),
    ("iron-steel", "深铁灰 × 靛蓝"),
    ("indigo-berry", "深靛青 × 烟熏洋红"),
)


class AtlasSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["palettes"]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_builder(self, dest, *options):
        return subprocess.run(
            [sys.executable, "-B", str(BUILDER), "--output-dir", str(dest), *options],
            cwd=self.root, capture_output=True, text=True, errors="replace",
        )

    def export_one(self, name, *options):
        dest = self.root / name
        built = self.run_builder(dest, *options)
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual([p.name for p in dest.iterdir()], ["figure.svg"])
        return (dest / "figure.svg").read_bytes()

    def check_palette(self, output, palette_id):
        root = ET.fromstring(output)
        gradients = root.findall(f"{SVG}defs/{SVG}linearGradient")
        actual = {g.get("id"): [stop.get("stop-color") for stop in g] for g in gradients}
        expected = {key: [stop["color"] for stop in g["stops"]]
                    for key, g in self.catalog[palette_id]["gradient_roles"].items()}
        self.assertEqual(actual, expected)

    def test_all_public_numbers_and_english_ids(self):
        self.assertEqual(list(self.catalog), [palette_id for palette_id, _ in ATLAS])
        for number, (palette_id, chinese_name) in enumerate(ATLAS, 1):
            with self.subTest(number=number, palette_id=palette_id):
                palette = self.catalog[palette_id]
                self.assertIs(type(palette["atlas_number"]), int)
                self.assertEqual(palette["atlas_number"], number)
                self.assertEqual(palette["name_zh"], chinese_name)
                self.assertNotIn("option", palette)
                selected = self.export_one(str(number), "--palette", str(number))
                by_id = self.export_one(palette_id, "--palette", palette_id)
                self.assertEqual(selected, by_id)
                self.check_palette(selected, palette_id)

    def test_default_labels_and_compatibility(self):
        self.check_palette(self.export_one("default"), "ehj-default")
        cases = (("EHJ", "ehj-default"), ("01", "ehj-default"), ("11号", "indigo-berry"),
                 ("深海蓝 × 砖红", "navy-brick"), ("B", "pine-sage"),
                 ("C", "ink-coral"), ("D", "mulberry-lilac"))
        for index, (selector, expected) in enumerate(cases):
            with self.subTest(selector=selector):
                out = self.export_one(f"alias-{index}", "--palette", selector)
                self.check_palette(out, expected)
        for bad in ("0", "12", "A"):
            dest = self.root / ("invalid-" + bad)
            result = self.run_builder(dest, "--palette", bad)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(dest.exists())

    def test_historical_batch_keeps_existing_filenames(self):
        dest = self.root / "reference"
        result = self.run_builder(dest, "--reference-palettes")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {"1-navy-brick.svg": "navy-brick", "2-navy-amber.svg": "navy-amber",
                    "4-iron-steel.svg": "iron-steel", "5-indigo-berry.svg": "indigo-berry"}
        self.assertEqual({p.name for p in dest.iterdir()}, set(expected))
        for name, palette_id in expected.items():
            self.check_palette((dest / name).read_bytes(), palette_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)

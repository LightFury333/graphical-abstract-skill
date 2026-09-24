# Tools and output

These helpers operate on an already authored SVG. They do not read a paper, choose scientific results, invent icons, or compose a full abstract. Host-native tools may be used instead. Keep working sources and evidence local unless the user asks to share them.

## Render a vector preview

Requirements: Node.js and Sharp. Use the host's bundled dependency when available, or a normal project installation of `sharp`. Run from a directory where the helper can resolve the module, or pass its directory explicitly. Example paths below are relative to the skill directory.

```sh
node scripts/render_preview.cjs figure.svg preview.png --width 3600 --density 300
node scripts/render_preview.cjs figure.svg preview.png --width 3600 --height 2200 --sharp-module /path/to/sharp
```

Omitting height preserves the source aspect ratio. An explicit mismatched width/height adds transparent margins instead of stretching. For a new 18:11 composition, author that ratio first so 3600 × 2200 needs no margin. `--density` sets print-resolution metadata, not recovered raster detail. The SVG is rasterized at final output resolution; embedded bitmaps retain their original detail. The renderer refuses to overwrite an existing output.

Inspect the exported PNG, not only the SVG source. Verify fonts in the actual rendering environment; neither helper embeds font files. Keep the preview's copy readable at intended physical size.

## Exact color-only SVG revisions

Requirements: Python 3.9+ with its standard library. Use an explicit JSON map of any chosen old/new six-digit RGB values:

```json
{
  "#7247A6": "#155E75",
  "#FF861C": "#179B83"
}
```

```sh
python scripts/recolor_svg.py approved.svg recolored.svg --mapping colors.json
```

The map is not restricted to the bundled palettes. For a complete palette replacement, map all intended non-black/white paint values, including gradient stops, accents, rules, and shadows; a partial map intentionally leaves unmapped colors intact. Choose new header colors with sufficient contrast for unchanged white text. Read palette roles from [palettes.json](palettes.json) when deriving a coordinated scheme.

The helper changes paint attributes, supported inline paint styles, and recognized color fields in JSON metadata. It verifies that the geometry, text, and typography are unchanged. Black and white are protected; changes that would affect any visible text color are rejected. Unknown source colors, invalid values, ambiguous text reuse, stylesheets, and dynamic SVG features fail rather than being guessed. If the user explicitly requests typography changes, edit the native source separately instead of bypassing this color-only helper.

Both input and output paths must differ, and existing outputs are preserved. For a new revision, use another filename. It is still necessary to render and inspect the result. If the SVG carries another export system's integrity hashes or native-object projections, refresh them through that system before optional PPTX export; this helper does not certify a third-party slide package.

## Optional formats

Retain the editable working source for predictable future revisions. Deliver SVG or PPTX only when requested. An editable PPTX should contain editable text and shapes where feasible; embedding a full-slide screenshot does not make it editable. Validate by opening/exporting with an actual presentation renderer when available, and disclose any renderer limitation. Do not add document/slide dependencies to an ordinary one-PNG task.

An abbreviation Word summary is separate work: inspect the complete manuscript including tables, legends, images, and references; distinguish professional terms from journal abbreviations, units, and symbols; render its pages and inspect pagination before delivery.

## Regression checks for the helpers

```sh
python scripts/test_helpers.py
```

Set the `NODE_BINARY` and `SHARP_MODULE` environment variables when the runtime/module is not normally discoverable. Renderer tests are skipped if those dependencies are unavailable; check the reported skips instead of claiming they ran. The tests use synthetic SVGs in a temporary directory, checking content/geometry preservation, paint mapping protection, rejected invalid inputs, source immutability, and PNG dimensions. They do not establish clinical correctness or replace visual review of a real figure.

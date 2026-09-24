# The established visual system

The target visual family is shown in `assets/palette-examples/`: pale continuous color fields, rich gradient section bars, rounded panels, simple gradient-compatible scientific pictograms, and black/white sans-serif text. These are original color-only derivatives of the approved task result, not official journal artwork.

## Color and surface

Default to `ehj-default` in [palettes.json](palettes.json): purple → wine/rose → warm orange. Its exact stops and reference image own the default surface balance. Do not replace it with unrelated saturated blocks.

- Carry a coordinated left-to-right progression across the figure. Panels and badges may use shorter segments or a gentle diagonal of the same progression.
- Use pale tinted backgrounds and generous light space, reserving stronger saturation for headers, icons, arrows, and separators.
- Keep body text and result numbers black. Use white text for all gradient section-bar headings, including labels such as "Main finding". Check contrast at the weakest point beneath the text; if a bar is too light, deepen its local gradient while retaining the palette hues. Do not silently change a requested white heading to black. Preserve an explicitly approved source in a color-only request; surface any unresolved contrast problem.
- Give pictograms gradient fills or white glyphs on gradient badges. Unframed icons use a multi-stop fill. Avoid unrelated flat-color icon circles.
- Keep borders thin and pale; subtle downward header shadows are appropriate. Avoid heavy shadows, bevels, glare, and decorative 3D treatment.
- Takeaway/footer surfaces share the overall gradient logic. Use red/green for clinical results only when the encoding is meaningful and explained.

The three other catalog palettes are examples, not restrictions. For arbitrary colors, choose two or more anchors, derive intermediate hues, and create pale tints. A starting point is 85–95% white for panels and 94–98% white for the page field. Preserve hue relationships instead of assigning unrelated group colors. For a color-only edit, explicitly map every colored rule, arrow, shadow, icon, and panel.

## Typography

Inspect the supplied PPT's actual figure typography before choosing a font. For native figure text, resolve run, paragraph, layout/master, and theme inheritance. When the figure is an embedded image, the slide's caption or theme font does not identify the font inside that image; compare the visible letterforms and state any approximation without claiming exact recovery.

For the established EHJ-inspired reference appearance, default to Segoe UI Regular when available. It is a visual approximation of the humanist sans-serif lettering in the supplied raster examples, not a verified publisher font. Do not reuse the older Calibri/Calibri Light pairing merely because it appears in a derived editable file. A verified font from a user-designated reference or an explicit font request takes precedence. If unavailable, use the closest installed regular humanist sans-serif and inspect the rendered substitution. Do not distribute proprietary fonts with the skill.

Use regular weight (400) for body text, section headings, labels, numerical results, and the takeaway by default. A larger title or key number usually needs no bold. If the user or reference requires emphasis, keep it selective rather than making every label and conclusion bold. Build hierarchy with size, spacing, and placement. On an 1800 × 1100 working canvas, starting sizes are approximately title 50–58, section 38–44, body/result 30–36, and footnote 22–26 px. These are starting points, not targets for squeezing in dense copy. Inspect at intended publication size as well as full-screen.

Use editable text where feasible. Keep a logical paragraph together with intentional line breaks. Align numeric columns and retain decimal precision. Footnotes decode abbreviations needed to read the figure; they need not reproduce the entire manuscript glossary.

## Layout

A useful starting structure for cohort research is a concise centered title; two or three rounded regions with gradient headers; population → method → results; a short takeaway band; and a light abbreviation footer. Allocate the largest region to the most demanding evidence. Add a limitation band only when the content justifies it.

This is a visual vocabulary, not a fixed study template. A mechanism may need a central biological scene, an experiment intervention → measurement → finding, and a treatment comparison parallel groups. Preserve visual balance while letting the information choose its arrangement. Never inherit the original study's cohorts or numbers.

Use comfortable padding, consistent corner radii, and icons of comparable visual weight close to their labels. Arrows express real stages or relationships. Icons should not displace the main finding. A table is appropriate when cell intersections carry a comparison, not as a substitute for deciding the story.

## Exact revisions

For “only change colors,” retain every text string, font attribute, line break, coordinate, silhouette, viewBox, and object order from the approved editable source. Change paint values and matching data-style metadata only. Verify non-color structure before rendering. For raster-only inputs, inspect text/geometry drift and do not claim deterministic preservation.

New figures default to 18:11. Approved sources keep their ratio even when it only approximates 18:11. Render vectors at final pixel resolution instead of enlarging screenshots; disclose any necessary raster upsampling.

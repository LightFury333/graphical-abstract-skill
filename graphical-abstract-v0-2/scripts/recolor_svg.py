#!/usr/bin/env python3
"""Recolor an SVG without changing its text, typography, or geometry.

Usage: python recolor_svg.py input.svg output.svg --mapping colors.json
The mapping is an object such as {"#7247A6": "#155E75"}. Only exact
six-digit hex paint values are changed. Black and white stay protected.
The source file is never overwritten; output must not already exist.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
URL_REF = re.compile(r"url\(\s*['\"]?#([^\s)'\"]+)['\"]?\s*\)")
PAINT = {"fill", "stroke", "color", "stop-color", "flood-color", "lighting-color"}
EFFECTS = {"filter", "clip-path", "mask", "marker-start", "marker-mid", "marker-end"}
TEXT_TAGS = {"text", "tspan", "textPath", "tref"}
FORBIDDEN_TAGS = {"style", "script", "foreignObject", "animate", "animateColor", "animateTransform", "set"}
META_COLOR_KEYS = {"fill", "stroke", "stop-color", "stopColor", "flood-color", "floodColor", "lighting-color", "lightingColor", "background", "background_color", "backgroundColor", "border_color", "borderColor", "color", "text_color", "textColor", "font_color", "fontColor"}
META_GRAPHIC_CONTEXT = {"borders", "border", "line", "outline", "fill", "stroke", "shadow", "background", "stops"}


class InputError(ValueError):
    pass


def local(name: str) -> str:
    return name.rsplit("}", 1)[-1] if isinstance(name, str) else "#comment"


def style_parts(value: str) -> list[tuple[str, str]]:
    result = []
    for part in value.split(";"):
        if not part.strip():
            continue
        if ":" not in part:
            raise InputError("Malformed inline style; convert it to explicit SVG attributes first.")
        key, val = part.split(":", 1)
        if "!important" in val:
            raise InputError("Inline !important styles are unsupported; use explicit SVG paint attributes.")
        result.append((key.strip(), val.strip()))
    return result


def paints(element: ET.Element) -> dict[str, str]:
    result = {local(k): v for k, v in element.attrib.items() if local(k) in PAINT | EFFECTS}
    if "style" in element.attrib:
        result.update({k: v for k, v in style_parts(element.attrib["style"]) if k in PAINT | EFFECTS})
    return result


def key_if_mapped(value: str, mapping: dict[str, str]) -> str | None:
    candidate = value.strip().upper()
    return candidate if candidate in mapping else None


def load_mapping(path: Path) -> dict[str, str]:
    def unique_pairs(pairs):
        result = {}
        for key, val in pairs:
            normalized = key.upper()
            if normalized in result:
                raise InputError(f"Duplicate mapping key: {key}")
            result[normalized] = val
        return result
    raw = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
    if not isinstance(raw, dict) or not raw:
        raise InputError("Mapping must be a nonempty JSON object of #RRGGBB: #RRGGBB pairs.")
    result = {}
    for old, new in raw.items():
        if not HEX.fullmatch(old) or not isinstance(new, str) or not HEX.fullmatch(new):
            raise InputError(f"Mapping must use exact six-digit hex colors: {old!r}: {new!r}")
        if old in {"#000000", "#FFFFFF"}:
            raise InputError(f"Protected black/white color cannot be mapped: {old}")
        if old == new.upper():
            raise InputError(f"Mapping has no effect: {old}")
        result[old] = new.upper()
    return result


def metadata_json(element: ET.Element):
    if local(element.tag) != "metadata" or not element.text or list(element):
        return None
    value = element.text.strip()
    if element.get("type") == "application/json" or value.startswith(("{", "[")):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise InputError(f"Malformed JSON metadata: {exc}") from exc
    return None


def recolor_metadata(value, mapping, path=()):
    if isinstance(value, dict):
        return {k: recolor_metadata(v, mapping, path + (k,)) for k, v in value.items()}
    if isinstance(value, list):
        return [recolor_metadata(v, mapping, path + (str(i),)) for i, v in enumerate(value)]
    if isinstance(value, str) and path and path[-1] in META_COLOR_KEYS:
        key = key_if_mapped(value, mapping)
        if key:
            leaf = path[-1]
            if leaf in {"text_color", "textColor", "font_color", "fontColor"} or (leaf == "color" and not any(p in META_GRAPHIC_CONTEXT for p in path[:-1])):
                raise InputError("Mapping would change text color in JSON metadata: " + ".".join(path))
            return mapping[key]
    return value


def ensure_text_paint_unchanged(root, mapping):
    by_id = {e.get("id"): e for e in root.iter() if e.get("id")}

    def resource_uses_mapping(value, seen=None):
        seen = set() if seen is None else seen
        if key_if_mapped(value, mapping):
            return True
        for ref_id in URL_REF.findall(value):
            if ref_id in seen:
                continue
            seen.add(ref_id)
            resource = by_id.get(ref_id)
            if resource is None:
                raise InputError(f"Unresolved local paint/effect reference: #{ref_id}")
            for node in resource.iter():
                for val in paints(node).values():
                    if resource_uses_mapping(val, seen):
                        return True
                for attr, val in node.attrib.items():
                    if local(attr) == "href" and val.startswith("#"):
                        if resource_uses_mapping(f"url({val})", seen):
                            return True
        return False

    def walk(node, inherited, ancestor_effects):
        values = paints(node)
        effective = dict(inherited)
        for prop in ("fill", "stroke", "color"):
            if prop in values and values[prop] != "inherit":
                effective[prop] = values[prop]
        effects = ancestor_effects + [values[k] for k in EFFECTS if k in values and values[k] != "none"]
        if local(node.tag) in TEXT_TAGS:
            for prop in ("fill", "stroke"):
                paint = effective.get(prop, "#000000" if prop == "fill" else "none")
                if paint == "currentColor":
                    paint = effective.get("color", "#000000")
                if resource_uses_mapping(paint):
                    raise InputError("Mapping would change visible text paint; keep all text black or white first.")
            if any(resource_uses_mapping(effect) for effect in effects):
                raise InputError("Mapping would change an effect used by visible text.")
        for child in node:
            walk(child, effective, effects)

    walk(root, {}, [])


def invariants(before, after, mapping):
    left = list(before.iter())
    right = list(after.iter())
    if len(left) != len(right):
        raise InputError("Invariant failure: SVG element count changed.")
    text_count = 0
    for a, b in zip(left, right):
        if a.tag != b.tag or a.tail != b.tail or a.attrib.keys() != b.attrib.keys():
            raise InputError("Invariant failure: SVG structure changed.")
        ma = metadata_json(a)
        if ma is None:
            if a.text != b.text:
                raise InputError("Invariant failure: literal text changed.")
        elif recolor_metadata(ma, mapping) != metadata_json(b):
            raise InputError("Invariant failure: non-color JSON metadata changed.")
        if local(a.tag) in TEXT_TAGS:
            text_count += 1
        for key, val in a.attrib.items():
            expected = val
            if local(key) in PAINT:
                mapped = key_if_mapped(val, mapping)
                if mapped:
                    expected = mapping[mapped]
            elif key == "style":
                expected_parts = [(k, mapping.get(v.upper(), v) if k in PAINT else v) for k, v in style_parts(val)]
                if expected_parts != style_parts(b.attrib[key]):
                    raise InputError("Invariant failure: non-paint inline style changed.")
                continue
            if b.attrib[key] != expected:
                raise InputError(f"Invariant failure: attribute changed outside permitted colors: {key}")
    return {"structure": "unchanged", "geometry": "unchanged", "literal_text": "unchanged", "font_attributes": "unchanged", "visible_text_paint": "unchanged", "text_elements_checked": text_count}


def recolor(source: Path, target: Path, mapping_path: Path):
    if source.resolve() == target.resolve():
        raise InputError("Input and output must be different files.")
    if target.exists():
        raise InputError("Output already exists; choose a new output path.")
    mapping = load_mapping(mapping_path)
    data = source.read_bytes()
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise InputError("DOCTYPE/entity declarations are unsupported.")
    if re.search(br"<\?xml-stylesheet\b", data, re.I):
        raise InputError("External XML stylesheets are unsupported; use explicit SVG paint attributes.")
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(data, parser=parser)
    if local(root.tag) != "svg":
        raise InputError("Input is not an SVG document.")
    id_nodes = {}
    for node in root.iter():
        if node.get("id"):
            if node.get("id") in id_nodes:
                raise InputError("Duplicate SVG id makes paint references ambiguous: " + node.get("id"))
            id_nodes[node.get("id")] = node
        if local(node.tag) in FORBIDDEN_TAGS or local(node.tag).startswith("animate"):
            raise InputError(f"Unsupported dynamic/stylesheet element: {local(node.tag)}. Use static SVG with inline paint attributes.")
    # A reused text subtree can acquire paint from its <use> instance. Refuse it
    # rather than claiming that inherited text paint was proved unchanged.
    for node in root.iter():
        if local(node.tag) == "use":
            href = next((v for k, v in node.attrib.items() if local(k) == "href"), "")
            referenced = id_nodes.get(href[1:]) if href.startswith("#") else None
            if referenced is None or any(local(n.tag) in TEXT_TAGS | {"use"} for n in referenced.iter()):
                raise InputError("Text-bearing, nested, or unresolved <use> references must be expanded before recoloring.")
    ensure_text_paint_unchanged(root, mapping)
    original = copy.deepcopy(root)
    counts = {key: 0 for key in mapping}
    for node in root.iter():
        for attr, value in list(node.attrib.items()):
            if local(attr) in PAINT:
                mapped = key_if_mapped(value, mapping)
                if mapped:
                    node.set(attr, mapping[mapped])
                    counts[mapped] += 1
            elif attr == "style":
                parts = style_parts(value)
                changed = False
                new_parts = []
                for key, val in parts:
                    mapped = key_if_mapped(val, mapping) if key in PAINT else None
                    if mapped:
                        val = mapping[mapped]
                        counts[mapped] += 1
                        changed = True
                    new_parts.append((key, val))
                if changed:
                    node.set(attr, "; ".join(f"{k}: {v}" for k, v in new_parts))
        meta = metadata_json(node)
        if meta is not None:
            changed_meta = recolor_metadata(meta, mapping)
            if changed_meta != meta:
                node.text = json.dumps(changed_meta, ensure_ascii=False, separators=(",", ":"))
    missing = [key for key, count in counts.items() if not count]
    if missing:
        raise InputError("Mapping colors not found in supported SVG paint attributes/styles: " + ", ".join(missing))
    checks = invariants(original, root, mapping)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    output = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(output)
    return {"input": str(source), "output": str(target), "input_sha256": hashlib.sha256(data).hexdigest(), "output_sha256": hashlib.sha256(output).hexdigest(), "paint_replacements": counts, "invariants": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(recolor(args.input, args.output, args.mapping), indent=2, ensure_ascii=False))
    except (InputError, OSError, ET.ParseError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()

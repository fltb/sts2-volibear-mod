#!/usr/bin/env python3
"""Validate delivered UI files without changing art, manifests, HTML, or fonts.

This checks technical integrity and font character coverage. It neither renders
the UI nor awards a visual or game-integration approval.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

import PIL
from PIL import Image
import fontTools
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
REPORT = ROOT / "reports/technical_validation.json"
APPROVED_SOURCE_SHA256 = "870b2ad6670b3adf7b319710b883f8e3b6319a7715ac68fb5628cbe6c64e3e5d"
FONT_SPECS = [
    ("fonts/volibear_ui_v5.woff", "fonts/provenance.json", "fonts/characters.txt",
     "subset_sha256", "characters"),
    ("fonts/production_caption.otf", "fonts/production_caption_provenance.json",
     "fonts/production_caption_characters.txt", "output_sha256", "character_count"),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def inside(base, relative):
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), f"Path escapes expected root: {relative}")
    require(path.is_file(), f"Missing input: {relative}")
    return path


def atomic_report(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".technical_validation.", suffix=".json", dir=REPORT.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        json.loads(Path(temporary).read_text(encoding="utf-8"))
        os.replace(temporary, REPORT)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate(report):
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_js = ROOT / "manifest.js"
    script = manifest_js.read_text(encoding="utf-8")
    assignment = re.fullmatch(r"\s*window\.VOLIBEAR_UI\s*=\s*(.*?)\s*;\s*", script, re.DOTALL)
    require(assignment is not None, "manifest.js is not the expected single UI data assignment")
    require(json.loads(assignment.group(1)) == manifest, "manifest.js data differs from manifest.json")
    report["manifest"] = {
        "json_sha256": sha(manifest_path), "javascript_sha256": sha(manifest_js),
        "javascript_data_equals_json": True,
    }

    source = inside(REPO, manifest["source_file"])
    source_sha = sha(source)
    require(source_sha == manifest["source_sha256"] == APPROVED_SOURCE_SHA256,
            "Approved character source identity differs")
    report["approved_source"] = {
        "file": manifest["source_file"], "sha256": source_sha,
        "matches_manifest_and_fixed_approved_source": True,
    }

    assets = manifest["assets"]
    require(len(assets) == 14, "Expected exactly 14 manifest PNG assets")
    require(len({row["id"] for row in assets}) == 14, "Duplicate asset IDs")
    require(len({row["file"] for row in assets}) == 14, "Duplicate asset file paths")
    actual_pngs = {p.relative_to(ROOT).as_posix() for p in (ROOT / "images").rglob("*.png")}
    require(actual_pngs == {row["file"] for row in assets}, "Manifest PNG inventory differs from images/")
    for row in assets:
        path = inside(ROOT, row["file"])
        digest = sha(path)
        require(digest == row["sha256"], f"PNG SHA mismatch: {row['file']}")
        with Image.open(path) as image:
            require(image.format == "PNG", f"File is not a PNG: {row['file']}")
            image.verify()
        with Image.open(path) as image:
            image.load()
            require(list(image.size) == row["size"], f"PNG size mismatch: {row['file']}")
            require(image.mode == row["mode"], f"PNG mode mismatch: {row['file']}")
            report["png_assets"].append({
                "id": row["id"], "file": row["file"], "sha256": digest,
                "size": list(image.size), "mode": image.mode,
                "full_decode": True, "matches_manifest": True,
            })

    svg_path = ROOT / "source/energy_emblem.svg"
    svg = ET.parse(svg_path).getroot()
    require(svg.tag == "{http://www.w3.org/2000/svg}svg", "Energy emblem root is not an SVG element")
    view_box = [float(value) for value in svg.attrib["viewBox"].split()]
    require(len(view_box) == 4 and view_box[2] > 0 and view_box[3] > 0, "Invalid SVG viewBox")
    report["energy_svg"] = {
        "file": "source/energy_emblem.svg", "sha256": sha(svg_path),
        "xml_parse_passed": True, "root_tag": svg.tag, "view_box": view_box,
        "path_count": len(svg.findall(".//{http://www.w3.org/2000/svg}path")),
        "visual_approval_awarded": False,
    }

    for filename, provenance_name, characters_name, hash_key, count_key in FONT_SPECS:
        path = inside(ROOT, filename)
        provenance_path = inside(ROOT, provenance_name)
        characters_path = inside(ROOT, characters_name)
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        text = characters_path.read_text(encoding="utf-8")
        codepoints = {ord(character) for character in text}
        digest = sha(path)
        require(digest == provenance[hash_key], f"Font output SHA differs from provenance: {filename}")
        require(len(codepoints) == provenance[count_key], f"Font character count differs from provenance: {filename}")
        if "output_bytes" in provenance:
            require(path.stat().st_size == provenance["output_bytes"], f"Font byte size differs from provenance: {filename}")
        # These characters format the character-list text and need no glyph.
        ignored_layout = codepoints & {0x0009, 0x000A, 0x000D}
        required = codepoints - ignored_layout
        with TTFont(path, lazy=False, checkChecksums=2) as font:
            font.ensureDecompiled()
            cmap = font.getBestCmap()
            require(cmap is not None, f"Font has no Unicode cmap: {filename}")
            missing = sorted(cp for cp in required if cp not in cmap or cmap[cp] == ".notdef")
            glyph_order = set(font.getGlyphOrder())
            require(all(cmap[cp] in glyph_order for cp in required if cp in cmap),
                    f"Font cmap names an absent glyph: {filename}")
            require(not missing, f"Font lacks requested characters: {filename}: " + ", ".join(f"U+{cp:04X}" for cp in missing))
            report["fonts"].append({
                "file": filename, "sha256": digest, "bytes": path.stat().st_size,
                "provenance_file": provenance_name, "provenance_sha256": sha(provenance_path),
                "provenance_output_hash_field": hash_key, "output_matches_provenance": True,
                "source_url_declared": provenance.get("source_url", provenance.get("source")),
                "source_sha256_declared": provenance["source_sha256"],
                "upstream_source_font_rehashed": False,
                "characters_file": characters_name, "characters_file_sha256": sha(characters_path),
                "declared_character_count": provenance[count_key],
                "actual_unique_character_count": len(codepoints),
                "required_glyph_character_count": len(required),
                "covered_character_count": len(required), "missing_codepoints": [],
                "ignored_layout_codepoints": [f"U+{cp:04X}" for cp in sorted(ignored_layout)],
                "fonttools_full_decompile_passed": True,
                "parsed_table_tags": sorted(str(tag) for tag in font.reader.keys()),
                "glyph_count": len(glyph_order), "units_per_em": font["head"].unitsPerEm,
            })
    report.update(passed=True, png_count=len(report["png_assets"]), font_count=len(report["fonts"]))


def main():
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": False, "validator_sha256": sha(Path(__file__)),
        "scope": "Delivered UI technical integrity only: 14 PNGs, approved source identity, JSON/JS data equality, SVG XML parse, and two actual fontTools font parses with declared character coverage.",
        "libraries": {"pillow": PIL.__version__, "fonttools": fontTools.__version__},
        "png_assets": [], "fonts": [],
        "limitations": "No visual judgment, browser rendering, or target-game integration approval. The independent visual review remains separate. Original upstream font hashes are provenance declarations; this validator hashes the two delivered font outputs.",
    }
    try:
        validate(report)
    except Exception as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        atomic_report(report)
        print(json.dumps({"passed": False, "failure": report["failure"]}), file=sys.stderr)
        return 1
    atomic_report(report)
    print(json.dumps({"passed": True, "png_count": report["png_count"],
                      "font_count": report["font_count"], "report": str(REPORT.relative_to(REPO))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare web-sized comparison images for the PPT preference page."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


SOURCE_ROOT = Path("/home/wangfeifei/projects/preference")
OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "ppt-preference-comparison" / "assets"

CASES = {
    "case_001": {"title": "DDI Studies: Data Sets and Data Files", "slides": 12},
    "case_002": {"title": "Curate Your Story", "slides": 31},
    "case_003": {"title": "AI Is Not the Problem", "slides": 45},
    "case_004": {
        "title": "Applied Modeling of Hydrological Systems in Central Asia",
        "slides": 21,
    },
    "case_005": {"title": "Importance and Scope of Critical Thinking", "slides": 7},
    "case_006": {"title": "Turkic Syntax I: Simple Sentences", "slides": 8},
    "case_007": {"title": "OMERO Tags", "slides": 25},
    "case_008": {"title": "Introduction to Statistics", "slides": 16},
    "case_009": {"title": "Research Data Management", "slides": 27},
}


def save_jpeg(source: Path, destination: Path, max_width: int = 2200) -> None:
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, "JPEG", quality=86, optimize=True, progressive=True)


def main() -> None:
    manifest = []
    for case_id, metadata in CASES.items():
        case_dir = SOURCE_ROOT / "cases" / case_id
        destination = OUTPUT_ROOT / case_id
        destination.mkdir(parents=True, exist_ok=True)

        references = sorted((case_dir / "references" / "images").glob("*.png"))
        if len(references) != 3:
            raise RuntimeError(f"{case_id}: expected 3 references, found {len(references)}")

        reference_entries = []
        for index, source in enumerate(references, 1):
            target = destination / f"reference_{index}.jpg"
            save_jpeg(source, target)
            label = source.stem.split("__", 2)[-1].replace("_", " ")
            reference_entries.append(
                {"label": label, "image": f"assets/{case_id}/{target.name}"}
            )

        gold_source = SOURCE_ROOT / "gold" / case_id / "target.png"
        generated_candidates = sorted((case_dir / "output").glob("*_overview.png"))
        if len(generated_candidates) != 1:
            raise RuntimeError(
                f"{case_id}: expected one generated overview, found {len(generated_candidates)}"
            )

        gold_target = destination / "ground_truth.jpg"
        generated_target = destination / "generated.jpg"
        save_jpeg(gold_source, gold_target)
        save_jpeg(generated_candidates[0], generated_target)

        manifest.append(
            {
                "id": case_id,
                **metadata,
                "references": reference_entries,
                "ground_truth": f"assets/{case_id}/{gold_target.name}",
                "generated": f"assets/{case_id}/{generated_target.name}",
            }
        )

    (OUTPUT_ROOT.parent / "manifest.json").write_text(
        json.dumps({"cases": manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

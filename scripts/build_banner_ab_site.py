#!/usr/bin/env python3
"""Build the static Batch 003 plan-only vs plan-plus-rubric gallery."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


SITE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path("/home/wangfeifei/projects/a_mpqc/codex_ab_results/batch_003")
PROMPT_ROOT = Path("/home/wangfeifei/projects/a_mpqc/banner_logos_and_prompts")
OUTPUT_ROOT = SITE_ROOT / "banner-plan-criteria-comparison"

BRANDS = {
    "001_ethicai": "Ethic AI",
    "002_svwgroup": "SVW Group",
    "003_harvest": "Harvest Prime Farms",
    "004_automate": "AutoMate",
    "005_cabool": "Cabool Dental",
    "006_togalim": "Togalimi Luxury Real Estate",
    "007_ethniplate": "EthniPlate",
    "008_bavarianbrew": "BavarianBrew",
    "009_essence&earth": "Essence & Earth",
    "010_megaplexar": "Megaplex AR",
}


def save_webp(source: Path, target: Path, *, quality: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.save(target, "WEBP", quality=quality, method=6)


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> None:
    cases = []
    total_criteria = 0
    reviewed_cases = 0
    for index, folder_name in enumerate(BRANDS, start=1):
        plan_only = SOURCE_ROOT / "plan_only" / folder_name
        plan_criteria = SOURCE_ROOT / "plan_plus_criteria" / folder_name
        case_id = f"case_{index:03d}"
        asset_dir = OUTPUT_ROOT / "assets" / case_id
        paths = {
            "logo": asset_dir / "logo.webp",
            "plan_only": asset_dir / "plan_only.webp",
            "plan_plus_criteria": asset_dir / "plan_plus_criteria.webp",
        }
        save_webp(plan_only / "logo.png", paths["logo"], quality=92)
        save_webp(plan_only / "banner.png", paths["plan_only"], quality=90)
        save_webp(plan_criteria / "banner.png", paths["plan_plus_criteria"], quality=90)

        criteria_data = read_json(plan_criteria / "criteria.json") or {"criteria": []}
        review = read_json(plan_criteria / "criteria_review.json")
        validation = read_json(plan_criteria / "validation_report.json")
        criteria = criteria_data.get("criteria", [])
        total_criteria += len(criteria)
        if review or validation:
            reviewed_cases += 1
        prompt_path = PROMPT_ROOT / f"{folder_name}_prompt.txt"
        prompt = prompt_path.read_text(encoding="utf-8").strip().strip('"')
        cases.append(
            {
                "id": case_id,
                "source_id": folder_name,
                "brand": BRANDS[folder_name],
                "prompt": prompt,
                "criteria": criteria,
                "criteria_count": len(criteria),
                "has_review": bool(review or validation),
                "images": {
                    key: path.relative_to(OUTPUT_ROOT).as_posix()
                    for key, path in paths.items()
                },
            }
        )

    manifest = {
        "title": "Banner Plan vs Rubric",
        "eyebrow": "Batch 003 · Editable PowerPoint Banner A/B",
        "description": "同一品牌 brief 与 logo 下，对比 Plan only 和 Plan + Rubric 两种生成流程。点击图片可查看大图，并可展开每个 case 的 rubric。",
        "summary": {
            "cases": len(cases),
            "banners": len(cases) * 2,
            "criteria": total_criteria,
            "reviewed_cases": reviewed_cases,
        },
        "cases": cases,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Built {len(cases)} cases, {len(cases) * 2} banners, "
        f"and {total_criteria} criteria in {OUTPUT_ROOT}"
    )


if __name__ == "__main__":
    build()

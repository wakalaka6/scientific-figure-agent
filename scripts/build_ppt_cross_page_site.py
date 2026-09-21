#!/usr/bin/env python3
"""Build static assets and manifest for the PPT cross-page benchmark site."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pymupdf
from PIL import Image


SITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SITE_ROOT.parent
EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "ppt_cross_page"
DATASET_ROOT = EXPERIMENT_ROOT / "figure_text_testdata"
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
OUTPUT_ROOT = SITE_ROOT / "ppt-cross-page-benchmark"
HTML_TEMPLATE = OUTPUT_ROOT / "index.html"

sys.path.insert(0, str(EXPERIMENT_ROOT))
from build_slide_comparisons import PROMPT_ZH  # noqa: E402


FACT_ZH = {
    "case_001": "化粪池使用年限分布",
    "case_002": "项目基准情景 IRR",
    "case_003": "问卷评分分布",
    "case_004": "太阳能项目基准 IRR",
    "case_005": "5 km 缓冲情景下的电网占比",
    "case_006": "2030 年可再生能源占比预测",
    "case_007": "尚无可行替代方案的 PFAS 工业应用",
    "case_008": "芬兰高校出版物语言分布",
    "case_009": "新德里选择瑜伽的受访者数量",
    "case_010": "DPT 3 / Polio 4 与麻疹免疫人数",
}

TEXT_TO_FIGURE_PROMPT_ZH = {
    "case_001": "在第2页摘要中，将“少于三年”的化粪池占比从17.06%改为35.00%，并将“不清楚使用年限”从22.66%改为4.72%；同步更新整份文稿中的相关图表和文字，其他使用年限组别保持不变。",
    "case_002": "在第6页Basecase摘要中，将IRR从19.72%改为30.00%；同步更新整份文稿中的相关内容，NPV和其他情景保持不变。",
    "case_003": "在第12页问卷评分总结中，将“good enough”从12.50%改为30.00%，将“good”从42.09%改为24.59%；同步更新相关图表和文字，其他评分类别保持不变。",
    "case_004": "在第7页Main insights与Conclusion中，将基准情景IRR从20.3%改为30.0%；同步更新相关内容，19%的减产情景IRR及其他数值保持不变。",
    "case_005": "在第8页结论中，将5 km情景的电网占比从89%改为70%，对应分配改为电网/微电网/独立光伏=70%/15%/15%；同步更新相关内容，10 km情景的94%保持不变。",
    "case_006": "在第9页结论中，将2030年可再生能源占比预测从34.2%改为40.0%；同步更新相关图表和文字，25%目标线与其他年份保持不变。",
    "case_007": "在第16页必要用途讨论中，将“尚无法替代”的工业应用数量从25改为50；同步更新相关图表和文字，其他用途类别保持不变。",
    "case_008": "在第20页政策讨论中，将出版语言分布从英语64%、芬兰语25%改为英语45%、芬兰语44%；同步更新相关图表和文字，其他小语种类别保持不变。",
    "case_009": "在第9页结论中，将新德里选择瑜伽的受访者数量从78改为40；同步更新相关图表和文字，其他城市和实践项目保持不变。",
    "case_010": "在第2页研究目标中，将应接种DPT 3/Polio 4与麻疹的人数分别从24和12改为36和0；同步更新相关图表和文字，总样本量与其他免疫阶段保持不变。",
}

PROFILES = {
    "figure-to-text": {
        "eyebrow": "Task 1 · Figure → Text",
        "title": "修改 Figure，模型自动同步 Text",
        "description": "用户修改一页中的 Figure / Chart；模型需要识别该视觉对象表达的事实，并自动更新其他页面中引用该事实的文字。每个目标页按 Source、Ground Truth、Predict 三列展示。",
        "manifest_description": "用户修改 Figure / Chart，模型自动同步其他页面中的关联 Text。",
    },
    "text-to-figure": {
        "eyebrow": "Task 2 · Text → Figure + Text",
        "title": "修改 Text，模型自动同步 Figure 和 Text",
        "description": "用户修改一页中的文字事实；模型需要自动更新相关 Figure / Chart，并同步其他页面中引用该事实的文字。每个目标页按 Source、Ground Truth、Predict 三列展示。",
        "manifest_description": "用户修改 Text，模型自动同步相关 Figure / Chart 和其他页面中的关联 Text。",
    },
}


def save_webp(page: pymupdf.Page, clip: pymupdf.Rect, output: Path) -> None:
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.55, 1.55), clip=clip, alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "WEBP", quality=88, method=6)


def comparison_clips(page: pymupdf.Page) -> dict[str, pymupdf.Rect]:
    outer_margin = 12.0
    gap = 12.0
    panel_width = (page.rect.width - outer_margin * 2 - gap * 2) / 3
    return {
        key: pymupdf.Rect(
            outer_margin + index * (panel_width + gap),
            24,
            outer_margin + index * (panel_width + gap) + panel_width,
            page.rect.height,
        )
        for index, key in enumerate(("source", "ground_truth", "predict"))
    }


def slide_change_summary(gt: dict, slide_number: int) -> list[str]:
    summaries: list[str] = []
    for item in gt["figure_changes"]:
        if int(item["slide"]) != slide_number:
            continue
        label = item.get("category") or item.get("series_name") or "Figure"
        summaries.append(
            f"图表 · {label}: {item['before_display']} → {item['after_display']}"
        )
    for item in gt["text_reference_changes"]:
        if int(item["slide"]) != slide_number:
            continue
        values = "；".join(f"{before} → {after}" for before, after in item["replacements"])
        summaries.append(f"文本 · {values}")
    return summaries


def build(dataset_root: Path, runs_root: Path, output_root: Path, profile_name: str) -> None:
    profile = PROFILES[profile_name]
    dataset_manifest = json.loads(
        (dataset_root / "manifest.json").read_text(encoding="utf-8")
    )
    evaluation = json.loads((runs_root / "evaluation.json").read_text(encoding="utf-8"))
    semantic_review = json.loads(
        (runs_root / "semantic_review.json").read_text(encoding="utf-8")
    )
    evaluation_by_case = {item["case_id"]: item for item in evaluation["cases"]}
    semantic_by_case = {
        item["case_id"]: item for item in semantic_review["cases"]
    }
    dataset_by_case = {item["case_id"]: item for item in dataset_manifest["cases"]}
    cases = []

    for index in range(1, 11):
        case_id = f"case_{index:03d}"
        gt = json.loads(
            (dataset_root / "ground_truth" / case_id / "gt.json").read_text(
                encoding="utf-8"
            )
        )
        case_meta = dataset_by_case[case_id]
        case_eval = evaluation_by_case[case_id]
        case_semantic = semantic_by_case[case_id]
        target_slides = [int(value) for value in gt["should_change_slides"]]
        wrong_by_slide: dict[int, int] = {}
        for slide, _shape_id, _kind in case_eval["content_wrong_elements"]:
            wrong_by_slide[int(slide)] = wrong_by_slide.get(int(slide), 0) + 1
        semantic_notes_by_slide: dict[int, list[str]] = {}
        for item in case_semantic["accepted_non_exact"]:
            semantic_notes_by_slide.setdefault(int(item["slide"]), []).append(
                item["reason"]
            )

        comparison_path = runs_root / case_id / "comparison.pdf"
        slides = []
        with pymupdf.open(comparison_path) as comparison:
            if len(comparison) != len(target_slides) + 1:
                raise ValueError(
                    f"{case_id}: expected one banner plus {len(target_slides)} slides"
                )
            for page_offset, slide_number in enumerate(target_slides, start=1):
                page = comparison[page_offset]
                clips = comparison_clips(page)
                images = {}
                for column, clip in clips.items():
                    relative = Path("assets") / case_id / f"slide_{slide_number:03d}_{column}.webp"
                    save_webp(page, clip, output_root / relative)
                    images[column] = relative.as_posix()
                slides.append(
                    {
                        "slide": slide_number,
                        "images": images,
                        "changes": slide_change_summary(gt, slide_number),
                        "exact_status": "non_exact" if wrong_by_slide.get(slide_number) else "exact",
                        "semantic_status": "correct",
                        "non_exact_elements": wrong_by_slide.get(slide_number, 0),
                        "semantic_notes": semantic_notes_by_slide.get(slide_number, []),
                    }
                )

        cases.append(
            {
                "id": case_id,
                "title": FACT_ZH[case_id],
                "fact_en": gt["fact"],
                "prompt_zh": (
                    TEXT_TO_FIGURE_PROMPT_ZH[case_id]
                    if profile_name == "text-to-figure"
                    else PROMPT_ZH[case_id]
                ),
                "prompt_en": gt["instruction"],
                "target_slides": target_slides,
                "slide_count": int(case_meta["slide_count"]),
                "dependency_origin": case_meta["dependency_origin"],
                "metrics": {
                    "recall": case_eval["element_recall"],
                    "precision": case_eval["element_precision"],
                    "content_accuracy": case_eval["content_accuracy"],
                    "semantic_accuracy": case_semantic["semantic_accuracy"],
                    "expected_elements": case_eval["expected_elements"],
                    "content_correct_elements": case_eval["content_correct_elements"],
                },
                "status": "exact" if case_eval["content_accuracy"] == 1 else "paraphrased",
                "semantic_status": "correct",
                "slides": slides,
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    if output_root.resolve() != OUTPUT_ROOT.resolve():
        shutil.copyfile(HTML_TEMPLATE, output_root / "index.html")
    aggregate_pdf = runs_root / "comparisons" / "all_cases.pdf"
    shutil.copyfile(aggregate_pdf, output_root / "all_cases.pdf")
    manifest = {
        "eyebrow": profile["eyebrow"],
        "title": profile["title"],
        "description": profile["description"],
        "manifest_description": profile["manifest_description"],
        "direction": profile_name,
        "model": "GPT-6 Astra / Codex",
        "summary": {
            "cases": len(cases),
            "target_slides": sum(len(item["slides"]) for item in cases),
            "expected_elements": evaluation["aggregate"]["expected_elements"],
            "recall": evaluation["aggregate"]["element_recall"],
            "precision": evaluation["aggregate"]["element_precision"],
            "content_accuracy": evaluation["aggregate"]["content_accuracy"],
            "semantic_accuracy": semantic_review["aggregate"]["semantic_accuracy"],
        },
        "cases": cases,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Built {len(cases)} cases in {output_root}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET_ROOT)
    parser.add_argument("--runs", type=Path, default=RUNS_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="figure-to-text")
    args = parser.parse_args()
    build(args.dataset, args.runs, args.output, args.profile)

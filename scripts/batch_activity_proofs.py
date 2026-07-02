from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Rectangle
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject


SCRIPT_DIR = Path(__file__).resolve().parent
OCR_SCRIPT = SCRIPT_DIR / "ocr_find_target.ps1"
PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
DEFAULT_OUTPUT = "处理后_活动证明整理"


def normalize_text(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text or "")


def safe_filename(name: str, fallback: str = "未命名活动") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:90] or fallback


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in range(2, 1000):
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Cannot create unique path for {path}")


def run_ocr(image_path: Path, target: str = "") -> dict:
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(OCR_SCRIPT),
        "-ImagePath",
        str(image_path),
        "-Target",
        target,
    ]
    result = subprocess.run(cmd, capture_output=True, check=True)
    stdout = result.stdout.decode("utf-8-sig", errors="replace")
    return json.loads(stdout)


def line_boxes_from_text_layer(page: pdfplumber.page.Page, targets: list[str]) -> list[tuple[float, float, float, float, str]]:
    words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False, use_text_flow=True) or []
    boxes: list[tuple[float, float, float, float, str]] = []
    for target in targets:
        target_norm = normalize_text(target)
        for word in words:
            if target_norm and target_norm in normalize_text(word.get("text", "")):
                center_y = (float(word["top"]) + float(word["bottom"])) / 2
                same_line = [
                    w
                    for w in words
                    if abs(((float(w["top"]) + float(w["bottom"])) / 2) - center_y) <= 5
                ]
                if same_line:
                    boxes.append(
                        (
                            min(float(w["x0"]) for w in same_line),
                            min(float(w["top"]) for w in same_line),
                            max(float(w["x1"]) for w in same_line),
                            max(float(w["bottom"]) for w in same_line),
                            target,
                        )
                    )
    return merge_boxes(boxes)


def merge_boxes(boxes: list[tuple[float, float, float, float, str]]) -> list[tuple[float, float, float, float, str]]:
    merged: list[tuple[float, float, float, float, str]] = []
    for box in sorted(boxes, key=lambda b: (b[1], b[0])):
        if not merged:
            merged.append(box)
            continue
        last = merged[-1]
        same_row = abs(((last[1] + last[3]) / 2) - ((box[1] + box[3]) / 2)) <= 5
        if same_row:
            labels = ",".join(sorted(set(last[4].split(",") + box[4].split(","))))
            merged[-1] = (min(last[0], box[0]), min(last[1], box[1]), max(last[2], box[2]), max(last[3], box[3]), labels)
        else:
            merged.append(box)
    return merged


def render_pdf_page(pdf: pdfium.PdfDocument, page_index: int, scale: float, out_path: Path) -> Image.Image:
    image = pdf[page_index].render(scale=scale).to_pil().convert("RGB")
    image.save(out_path)
    return image


def ocr_pdf(path: Path, targets: list[str], scale: float) -> tuple[dict[int, list[tuple[float, float, float, float, str]]], dict[int, str]]:
    hits_by_page: dict[int, list[tuple[float, float, float, float, str]]] = {}
    text_by_page: dict[int, str] = {}
    pdf = pdfium.PdfDocument(str(path))
    with tempfile.TemporaryDirectory(prefix="activity_proof_ocr_") as tmp:
        tmp_path = Path(tmp)
        for idx in range(len(pdf)):
            image_path = tmp_path / f"page_{idx + 1:04d}.png"
            render_pdf_page(pdf, idx, scale, image_path)
            page_boxes: list[tuple[float, float, float, float, str]] = []
            for target in targets:
                target_norm = normalize_text(target)
                if not target_norm:
                    continue
                page_payload = run_ocr(image_path, target)
                text_by_page[idx] = max(text_by_page.get(idx, ""), page_payload.get("Text", ""), key=len)
                for line in page_payload.get("Hits", []):
                    page_boxes.append(
                        (
                            float(line["X"]) / scale,
                            float(line["Y"]) / scale,
                            float(line["X"] + line["Width"]) / scale,
                            float(line["Y"] + line["Height"]) / scale,
                            target,
                        )
                    )
            if page_boxes:
                hits_by_page[idx] = merge_boxes(page_boxes)
    pdf.close()
    return dict(hits_by_page), text_by_page


def extract_pdf_text_layer(path: Path) -> tuple[dict[int, str], dict[int, list[tuple[float, float, float, float, str]]]]:
    text_by_page: dict[int, str] = {}
    hits_by_page: dict[int, list[tuple[float, float, float, float, str]]] = {}
    return text_by_page, hits_by_page


def parse_manual_hints(values: list[str]) -> dict[str, dict[int, list[tuple[float, float, float, float, str]]]]:
    hints: dict[str, dict[int, list[tuple[float, float, float, float, str]]]] = defaultdict(lambda: defaultdict(list))
    for value in values:
        # file.pdf:11 or file.pdf:11:300-325 in PDF top-origin coordinates.
        parts = value.rsplit(":", 2)
        if len(parts) < 2:
            continue
        filename = parts[0]
        page_index = int(parts[1]) - 1
        if len(parts) == 3 and "-" in parts[2]:
            top, bottom = [float(x) for x in parts[2].split("-", 1)]
        else:
            top, bottom = 300.0, 325.0
        hints[filename][page_index].append((20.0, top, 580.0, bottom, "manual"))
    return hints


def extract_metadata(source_name: str, text: str) -> dict[str, str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    joined = "\n".join(lines)
    activity_name = ""
    activity_time = ""
    organizer = ""
    intro = ""

    quote_match = re.search(r"[“\"《]?([^“”\"《》\n]{2,40}?活动[^“”\"《》\n]{0,30})[”\"》]?", joined)
    if quote_match:
        activity_name = quote_match.group(1).strip(" “”\"《》")
    if not activity_name:
        for line in lines[:12]:
            if any(key in line for key in ["活动", "证明", "名单"]):
                activity_name = line.strip(" “”\"《》")
                break
    if not activity_name:
        activity_name = Path(source_name).stem

    time_patterns = [
        r"(?:活动时间|时间)[:：]?\s*([0-9]{4}年[^。\n]{2,40})",
        r"([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日\s*[-—至到]\s*[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)",
        r"([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)",
    ]
    for pattern in time_patterns:
        match = re.search(pattern, joined)
        if match:
            activity_time = match.group(1).strip()
            break

    for line in lines:
        if any(key in line for key in ["举办单位", "主办", "承办", "组织单位"]):
            organizer = re.sub(r"^(举办单位|主办单位|承办单位|组织单位|主办|承办)[:：]?", "", line).strip()
            break
    if not organizer:
        for line in reversed(lines[-8:]):
            if any(key in line for key in ["委员会", "学院", "团委", "学生会"]):
                organizer = line
                break

    for line in lines:
        if any(key in line for key in ["参加", "参与", "特此证明", "以下人员", "名单"]):
            intro = line[:160]
            break
    if not intro:
        if any("名单" in line for line in lines[:10]) or "名单" in source_name:
            intro = "该文件为活动参与人员名单，命中人员已在输出文件中标注。"
        elif len(lines) > 1:
            candidate = "；".join(lines[:3])[:160]
            if re.search(r"(活动|证明|参加|参与|名单|学院|单位)", candidate):
                intro = candidate
            else:
                intro = "该文件为活动证明材料，命中人员已在输出文件中标注。"

    return {
        "活动名": safe_filename(activity_name),
        "活动时间": activity_time,
        "活动举办单位": organizer,
        "活动简介": intro,
    }


def annotate_pdf(
    source: Path,
    output_dir: Path,
    targets: list[str],
    manual_hints: dict[int, list[tuple[float, float, float, float, str]]],
    render_scale: float,
) -> dict[str, str]:
    with pdfplumber.open(source) as plumber_pdf:
        page_count = len(plumber_pdf.pages)
        text_by_page = {i: page.extract_text() or "" for i, page in enumerate(plumber_pdf.pages)}
        hits_by_page: dict[int, list[tuple[float, float, float, float, str]]] = {}
        for i, page in enumerate(plumber_pdf.pages):
            boxes = line_boxes_from_text_layer(page, targets)
            if boxes:
                hits_by_page[i] = boxes

        ocr_hits, ocr_text = ocr_pdf(source, targets, render_scale)
        for i, text in ocr_text.items():
            if text and len(text) > len(text_by_page.get(i, "")):
                text_by_page[i] = text
        for i, boxes in ocr_hits.items():
            hits_by_page.setdefault(i, []).extend(boxes)
            hits_by_page[i] = merge_boxes(hits_by_page[i])
        for i, boxes in manual_hints.items():
            hits_by_page.setdefault(i, []).extend(boxes)
            hits_by_page[i] = merge_boxes(hits_by_page[i])

        all_text = "\n".join(text_by_page.get(i, "") for i in sorted(text_by_page))
        metadata = extract_metadata(source.name, all_text)
        selected = sorted({0, page_count - 1, *hits_by_page.keys()})
        expected_selected = len({0, page_count - 1, *hits_by_page.keys()})

        reader = PdfReader(str(source))
        writer = PdfWriter()
        output_index_by_source: dict[int, int] = {}
        for source_idx in selected:
            output_index_by_source[source_idx] = len(writer.pages)
            writer.add_page(reader.pages[source_idx])

        for source_idx, boxes in hits_by_page.items():
            output_idx = output_index_by_source[source_idx]
            page = plumber_pdf.pages[source_idx]
            height = float(page.height)
            width = float(page.width)
            for _x0, top, _x1, bottom, _label in boxes:
                rect = (18, height - bottom - 4, width - 18, height - top + 4)
                annotation = Rectangle(rect=rect)
                annotation[NameObject("/C")] = ArrayObject([FloatObject(1), FloatObject(0), FloatObject(0)])
                annotation[NameObject("/BS")] = DictionaryObject({NameObject("/W"): NumberObject(2), NameObject("/S"): NameObject("/S")})
                writer.add_annotation(page_number=output_idx, annotation=annotation)

        if len(selected) != expected_selected or len(writer.pages) != expected_selected:
            raise RuntimeError(
                f"PDF trim validation failed for {source.name}: "
                f"selected={len(selected)}, writer_pages={len(writer.pages)}, expected={expected_selected}"
            )

    out_path = unique_path(output_dir / f"{metadata['活动名']}.pdf")
    with out_path.open("wb") as f:
        writer.write(f)

    matched_labels = sorted({box[4] for boxes in hits_by_page.values() for box in boxes})
    return {
        **metadata,
        "源文件": source.name,
        "输出文件": out_path.name,
        "类型": "PDF",
        "原页数": str(page_count),
        "输出页数": str(len(selected)),
        "命中页": ";".join(str(i + 1) for i in sorted(hits_by_page)) or "未找到",
        "命中依据": ";".join(matched_labels),
        "备注": "" if hits_by_page else "需人工核对",
    }


def annotate_image(source: Path, output_dir: Path, targets: list[str]) -> dict[str, str]:
    image = Image.open(source).convert("RGB")
    payload = run_ocr(source)
    text = payload.get("Text", "")
    lines = payload.get("Lines", [])
    hits = []
    for target in targets:
        target_norm = normalize_text(target)
        for line in lines:
            if target_norm and target_norm in normalize_text(line.get("Text", "")):
                hits.append((line, target))

    if hits:
        draw = ImageDraw.Draw(image)
        width, height = image.size
        for line, _target in hits:
            y0 = max(0, int(float(line["Y"])) - 7)
            y1 = min(height, int(float(line["Y"] + line["Height"])) + 7)
            draw.rectangle((4, y0, width - 4, y1), outline=(255, 0, 0), width=5)

    metadata = extract_metadata(source.name, text)
    out_path = unique_path(output_dir / f"{metadata['活动名']}{source.suffix.lower()}")
    image.save(out_path)
    return {
        **metadata,
        "源文件": source.name,
        "输出文件": out_path.name,
        "类型": "图片",
        "原页数": "",
        "输出页数": "",
        "命中页": "图片命中" if hits else "未找到",
        "命中依据": ";".join(sorted({target for _line, target in hits})),
        "备注": "" if hits else "需人工核对",
    }


def write_summary(rows: list[dict[str, str]], output_dir: Path) -> None:
    fields = ["活动名", "活动时间", "活动举办单位", "活动简介", "源文件", "输出文件", "类型", "原页数", "输出页数", "命中页", "命中依据", "备注"]
    csv_path = output_dir / "活动证明汇总.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    md_path = output_dir / "活动证明汇总.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("| " + " | ".join(["---"] * len(fields)) + " |\n")
        for row in rows:
            f.write("| " + " | ".join((row.get(field, "") or "").replace("|", "／").replace("\n", " ") for field in fields) + " |\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch organize activity proof PDFs/images by participant name or student ID.")
    parser.add_argument("--input", required=True, help="Folder containing source PDFs/images.")
    parser.add_argument("--output", default=None, help=f"Output folder. Default: <input>/{DEFAULT_OUTPUT}")
    parser.add_argument("--name", default="", help="Participant name, e.g. 徐阳.")
    parser.add_argument("--student-id", default="", help="Student ID, e.g. 2023013482.")
    parser.add_argument("--render-scale", type=float, default=2.0, help="PDF render scale for OCR. Increase to 3 for blurry scans.")
    parser.add_argument("--manual-hit", action="append", default=[], help="Manual hint: filename.pdf:page or filename.pdf:page:top-bottom.")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve() if args.output else input_dir / DEFAULT_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = [value for value in [args.name, args.student_id] if value]
    if not targets:
        raise SystemExit("Provide --name and/or --student-id.")

    manual_hints = parse_manual_hints(args.manual_hit)
    rows: list[dict[str, str]] = []
    files = sorted([p for p in input_dir.iterdir() if p.is_file()], key=lambda p: p.name)
    for path in files:
        suffix = path.suffix.lower()
        if suffix in PDF_EXTS:
            rows.append(annotate_pdf(path, output_dir, targets, manual_hints.get(path.name, {}), args.render_scale))
        elif suffix in IMAGE_EXTS:
            rows.append(annotate_image(path, output_dir, targets))

    write_summary(rows, output_dir)
    print(f"Processed {len(rows)} files")
    print(output_dir)


if __name__ == "__main__":
    main()

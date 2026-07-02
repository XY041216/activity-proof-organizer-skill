---
name: activity-proof-organizer
description: Batch organize activity proof PDFs and images by participant name and/or student ID. Use when Codex needs to process folders of certificates, attendance lists, activity proof PDFs, scanned PDFs, or images; keep only cover/ending/matching pages; draw red boxes around matching rows; rename outputs by internal activity names; and generate a summary file with activity name, activity time, organizer, and activity introduction.
---

# Activity Proof Organizer

## Overview

Use this skill to batch process activity proof folders. The standard workflow identifies a participant by name and/or student ID, marks the matching row in red, trims PDFs to the first page, matching page(s), and last page, renames outputs using the activity name found inside the file, and writes a summary table.

Prefer the bundled script for real work:

```powershell
python <skill>/scripts/batch_activity_proofs.py --input <folder> --name <姓名> --student-id <学号>
```

If only one identifier is known, pass only `--name` or only `--student-id`.

## Workflow

1. Inspect the folder and confirm source types: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`.
2. Run `scripts/batch_activity_proofs.py` with the user-provided name and/or student ID.
3. Keep originals unchanged. Write results to a new output folder, default `处理后_活动证明整理`.
4. For each PDF, retain only:
   - first page,
   - every page containing the participant name or student ID,
   - last page.
   A page counts as matched only when the script has at least one non-empty
   target hit/box on that page. Never treat an empty OCR result, an empty list
   in `hits_by_page`, or unrelated PDF annotations as a matched page.
5. For each image, keep the image and draw a red rectangle around the matching row when found.
6. Rename processed files using the internal activity name. Use a safe, de-duplicated filename. Do not rely only on the source filename unless content extraction fails.
7. Generate `活动证明汇总.csv` and `活动证明汇总.md` with:
   - activity name,
   - activity time,
   - organizer,
   - activity introduction,
   - source filename,
   - output filename,
   - matched identifier and pages/status.
8. Verify the log: no unexpected `未找到`. If OCR misses a known participant, rerun with both name and student ID or use `--manual-hit file.pdf:page`.

## Script Notes

The script combines:

- `pdfplumber` for text-layer extraction and coordinates.
- `pypdf` for writing trimmed PDFs and square annotations.
- `pypdfium2` for rendering scanned PDFs to images.
- Windows OCR via `scripts/ocr_find_target.ps1` for Chinese scanned documents and images.
- `Pillow` for image red boxes.

When Windows OCR is unavailable, the script still handles text-layer PDFs, but scanned PDFs/images may need another OCR path or manual page hints.

## Matching Rules

Use all provided identifiers. Treat a page as matched when any identifier appears:

- exact full name, e.g. `徐阳`;
- student ID, e.g. `2023013482`;
- for Chinese two-character names, same-line separated characters may be a match;
- for difficult scans, manual page hints may be used with `--manual-hit`.

For rows, draw the red box across the visible row, not just around the name or ID. If only the ID is found, mark the whole ID row.

## Summary Extraction

Use the internal text/OCR content, especially the first page, to infer metadata. Prefer these patterns:

- activity name: title lines containing `活动`, `证明`, `名单`, or quoted activity names;
- activity time: lines containing `活动时间`, `时间`, date ranges, or dates such as `2026年3月16日-2026年4月12日`;
- organizer: lines containing `举办单位`, `主办`, `承办`, `组织单位`, `委员会`, `学院`, `团委`;
- activity introduction: concise sentence from proof text, usually near `参加`, `参与`, `特此证明`, `以下人员`.

If a field cannot be confidently extracted, leave it blank and record `需人工核对` in notes rather than inventing content.

## Validation

After processing, check:

- every expected source file has an output file;
- every output PDF page count equals `first + hit pages + last` after de-duplication;
- every hit page listed in the summary has at least one non-empty hit box before
  trimming; if no target hit is found, keep only first/last and mark the row for
  manual review or rerun with `--manual-hit`;
- every matched output PDF has at least one red square annotation;
- images with matches visibly contain a red row rectangle;
- summary filenames match output filenames;
- activity names in output filenames are filesystem-safe and not generic unless extraction failed.

## References

Read `references/extraction-patterns.md` when metadata extraction is poor, OCR output is noisy, or the document format differs from the usual Chinese activity proof/list style.

# Extraction Patterns

Use this reference when activity metadata extraction is noisy or incomplete.

## Activity Name

Prefer names inside Chinese quotes or book-title brackets:

- `“2026年春训”活动人员名单` -> `2026年春训`
- `“冬至暖朝夕，善意藏日常”活动证明` -> `冬至暖朝夕，善意藏日常活动证明`

If the first page has a title containing `活动证明`, `活动人员名单`, or `参与人员名单`, use that title after removing generic prefixes such as `证明` only when a more specific activity title is nearby.

Do not use organizer names, stamps, or footer committee names as the activity name.

## Activity Time

Look for:

- `活动时间：2026年3月16日-2026年4月12日`
- `时间：2026年3月18日`
- proof prose containing `于2026年5月31日...`

Keep date ranges verbatim. If multiple dates appear, prefer the one nearest `活动时间` or the proof sentence.

## Organizer

Prefer explicit labels:

- `举办单位：...`
- `主办单位：...`
- `承办单位：...`
- `组织单位：...`

If no label exists, use likely footer/signature lines ending with:

- `委员会`
- `学院团委`
- `学生会`
- `学院`

Do not infer an organizer from a stamp alone unless no better text exists.

## Activity Introduction

Use one concise source-grounded sentence. Good candidates contain:

- `参加`
- `参与`
- `特此证明`
- `以下人员`
- `名单`

For a pure list page, summarize conservatively, e.g. `该文件为活动参与人员名单，命中人员已在输出文件中标注。`

## OCR Trouble Cases

Common Chinese OCR issues:

- names may be split into separated characters, e.g. `徐 阳`;
- stamps may hide characters;
- student IDs are often more reliable than names;
- long table rows may be split into separate OCR lines.

When a known participant is missed:

1. rerun with both `--name` and `--student-id`;
2. increase `--render-scale 3`;
3. inspect candidate pages and add `--manual-hit "file.pdf:page"` or `--manual-hit "file.pdf:page:top-bottom"`.

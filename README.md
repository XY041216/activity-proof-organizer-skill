# Activity Proof Organizer

一个面向 Codex 的活动证明批量整理 Skill。它可以按姓名和/或学号定位 PDF、扫描件与图片中的参与记录，标出命中行，精简证明页，并自动生成活动汇总表。

## 主要功能

- 按姓名、学号或两者共同检索参与记录。
- 同时支持文本型 PDF、扫描型 PDF 和常见图片格式。
- PDF 仅保留首页、全部命中页和尾页，并自动去重。
- 使用红色方框标记姓名或学号所在的整行。
- 根据文件内部内容提取活动名称并重命名输出文件。
- 汇总活动名称、活动时间、举办单位和活动简介。
- 保留原始文件，所有处理结果写入独立目录。
- 支持人工指定疑难扫描件的命中页和标记区域。

## 支持格式

| 类型 | 格式 |
| --- | --- |
| 文档 | `.pdf` |
| 图片 | `.png`、`.jpg`、`.jpeg`、`.bmp`、`.tif`、`.tiff` |

## 环境要求

- Windows 10 或 Windows 11
- Python 3.10+
- PowerShell 5.1+
- Windows 中文 OCR 语言包

安装 Python 依赖：

```powershell
python -m pip install pdfplumber pypdf pypdfium2 Pillow
```

扫描型 PDF 和图片通过 Windows OCR 识别。若系统未安装中文 OCR 语言包，文本型 PDF 仍可处理，但扫描件可能需要安装语言包或使用人工命中参数。

## 安装 Skill

将仓库克隆到 Codex 的 Skills 目录：

```powershell
git clone https://github.com/XY041216/activity-proof-organizer-skill.git `
  "$env:USERPROFILE\.codex\skills\activity-proof-organizer"
```

重新启动 Codex 后，可以直接描述任务，例如：

> 整理这个文件夹中的活动证明，查找“姓名”或“学号”，保留 PDF 首页、命中页和尾页，用红框标出命中行，并生成活动汇总。

## 命令行用法

也可以直接运行仓库内的处理脚本：

```powershell
python .\scripts\batch_activity_proofs.py `
  --input "D:\活动证明" `
  --name "姓名" `
  --student-id "学号"
```

只知道一个标识时，仅传入对应参数即可：

```powershell
python .\scripts\batch_activity_proofs.py --input "D:\活动证明" --student-id "学号"
```

### 常用参数

| 参数 | 说明 |
| --- | --- |
| `--input` | 待处理文件夹，必填 |
| `--output` | 输出文件夹；默认在输入目录中创建 `处理后_活动证明整理` |
| `--name` | 参与者姓名 |
| `--student-id` | 参与者学号 |
| `--render-scale` | OCR 渲染倍率，默认 `2.0`；模糊扫描件可提高到 `3` |
| `--manual-hit` | 人工指定命中页，可重复使用 |

姓名与学号至少提供一项。同时提供时，只要其中任意一项命中即可定位记录。

## 疑难扫描件

OCR 未能识别已知记录时，可以人工指定命中页：

```powershell
python .\scripts\batch_activity_proofs.py `
  --input "D:\活动证明" `
  --name "姓名" `
  --student-id "学号" `
  --manual-hit "示例活动.pdf:11"
```

也可以指定 PDF 页面中从顶部计算的纵向范围：

```text
--manual-hit "示例活动.pdf:11:300-325"
```

## 输出内容

处理完成后，输出目录通常包含：

```text
处理后_活动证明整理/
├── 活动名称一.pdf
├── 活动名称二.png
├── 活动证明汇总.csv
└── 活动证明汇总.md
```

汇总文件记录：

- 活动名称
- 活动时间
- 活动举办单位
- 活动简介
- 源文件与输出文件名
- 原始页数与输出页数
- 命中页、命中依据和人工核对备注

若元数据无法可靠提取，Skill 会保留可用信息并标记为需要人工核对，不会凭空补写内容。

## 处理原则

1. 原始文件始终保持不变。
2. PDF 保留首页、全部命中页和尾页。
3. 命中页中的姓名或学号所在整行使用红框标出。
4. 图片保留完整画面，仅增加红框标记。
5. 输出文件优先使用文件内部识别出的活动名称命名。
6. 同名活动自动使用递增编号，避免覆盖已有结果。

## 项目结构

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── extraction-patterns.md
└── scripts/
    ├── batch_activity_proofs.py
    └── ocr_find_target.ps1
```

详细的 Skill 工作流见 [`SKILL.md`](SKILL.md)。

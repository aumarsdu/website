# 河狸陪留学三库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Openision 已采集的专业、案例和筛选字典数据转化为河狸陪可使用的专业库、院校库和案例库。

**Architecture:** 在现有 `openision-crawler` Python 工程内新增 `openision_crawler.libraries` 模块，采用纯离线转换方式读取 `data/normalized/*.jsonl` 和 `data/raw/filters/*.json`，输出稳定的 JSONL、SQLite 表和数据质量报告。专业库与案例库来自源记录清洗，院校库由专业和案例聚合生成。

**Tech Stack:** Python 3 标准库、现有 `unittest` 测试框架、JSONL、SQLite、现有 CLI 入口。

---

## 文件结构

新增或修改以下文件：

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/__init__.py`
  - 负责导出三库构建模块。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/io.py`
  - 负责 JSONL 读取、稳定写入、目录创建和敏感字段扫描。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/models.py`
  - 负责三库输出字段的数据结构和 `to_dict()` 序列化。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/normalizers.py`
  - 负责国家、学费、GPA、年份、院校标签、文本字段标准化。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/programs.py`
  - 负责从专业源记录生成 `program_library.jsonl`。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/cases.py`
  - 负责从案例源记录生成 `admission_case_library.jsonl`。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/schools.py`
  - 负责从专业库和案例库聚合生成 `school_library.jsonl`。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/quality.py`
  - 负责生成三库质量报告。
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/build.py`
  - 负责协调三库构建流程。
- Modify: `liuxue/openision-crawler/src/openision_crawler/cli.py`
  - 增加 `build-libraries` 命令。
- Modify: `liuxue/openision-crawler/src/openision_crawler/storage.py`
  - 增加三库 SQLite 表创建和写入方法。
- Create: `liuxue/openision-crawler/tests/test_libraries_io.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_normalizers.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_models.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_programs.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_cases.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_schools.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_quality.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_build.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_cli.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_storage.py`
- Modify: `liuxue/openision-crawler/README.md`
  - 增加三库生成命令、输出位置和合规说明。

输出文件：

- `liuxue/openision-crawler/data/libraries/program_library.jsonl`
- `liuxue/openision-crawler/data/libraries/school_library.jsonl`
- `liuxue/openision-crawler/data/libraries/admission_case_library.jsonl`
- `liuxue/openision-crawler/data/reports/library_quality_report.json`
- `liuxue/openision-crawler/data/reports/library_quality_report.md`

## 模块拆分总览

每个任务都控制在一次对话可完成代码的范围内。执行时按顺序推进，前一个任务的测试通过后再进入下一个任务。

### Task 1: 三库 IO 工具

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/__init__.py`
- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/io.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_io.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
import tempfile
import unittest

from openision_crawler.libraries.io import read_jsonl, write_jsonl, contains_sensitive_key


class LibraryIoTests(unittest.TestCase):
    def test_write_jsonl_creates_parent_and_sorts_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.jsonl"
            write_jsonl(path, [{"b": 2, "a": 1}])
            self.assertEqual(path.read_text(encoding="utf-8"), '{"a":1,"b":2}\n')

    def test_read_jsonl_skips_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "in.jsonl"
            path.write_text('{"id":"1"}\n\n{"id":"2"}\n', encoding="utf-8")
            self.assertEqual(read_jsonl(path), [{"id": "1"}, {"id": "2"}])

    def test_contains_sensitive_key_detects_nested_keys(self) -> None:
        row = {"headers": {"FCAuthorization": "secret"}}
        self.assertTrue(contains_sensitive_key(row))
        self.assertFalse(contains_sensitive_key({"id": "1", "name": "ok"}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_io -v
```

Expected: FAIL，提示 `openision_crawler.libraries` 或 `read_jsonl` 不存在。

- [ ] **Step 3: 实现最小 IO 模块**

```python
# src/openision_crawler/libraries/__init__.py
"""Derived libraries for Helipei study-abroad products."""
```

```python
# src/openision_crawler/libraries/io.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SENSITIVE_KEY_PARTS = (
    "authorization",
    "fcauthorization",
    "cookie",
    "token",
    "secret",
    "signature",
    "ossaccesskeyid",
    "security-token",
    "password",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                return True
            if contains_sensitive_key(child):
                return True
    if isinstance(value, list):
        return any(contains_sensitive_key(item) for item in value)
    return False
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_io -v
```

Expected: PASS，3 个测试通过。

### Task 2: 标准化工具

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/normalizers.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_normalizers.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from openision_crawler.libraries.normalizers import (
    normalize_admission_year,
    normalize_fee,
    normalize_school_tag,
    parse_float,
    text_or_none,
)


class LibraryNormalizerTests(unittest.TestCase):
    def test_text_or_none_strips_blank(self) -> None:
        self.assertIsNone(text_or_none("  "))
        self.assertEqual(text_or_none(" 英国 "), "英国")

    def test_parse_float_handles_text(self) -> None:
        self.assertEqual(parse_float("87.5"), 87.5)
        self.assertIsNone(parse_float(""))
        self.assertIsNone(parse_float(None))

    def test_normalize_fee_marks_zero_as_unknown(self) -> None:
        self.assertEqual(normalize_fee(0, "£24,000"), (None, False, "£24,000"))
        self.assertEqual(normalize_fee(24000, "£24,000"), (24000.0, True, "£24,000"))

    def test_normalize_admission_year_rejects_invalid(self) -> None:
        self.assertEqual(normalize_admission_year("2025"), (2025, True))
        self.assertEqual(normalize_admission_year("0000"), (None, False))
        self.assertEqual(normalize_admission_year(""), (None, False))

    def test_normalize_school_tag(self) -> None:
        self.assertEqual(normalize_school_tag(" 985院校 "), "985院校")
        self.assertEqual(normalize_school_tag(""), "未知背景")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_normalizers -v
```

Expected: FAIL，提示 `normalizers` 模块不存在。

- [ ] **Step 3: 实现标准化函数**

```python
from __future__ import annotations

from typing import Any


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_fee(raw_fee: Any, tuition_cn: Any) -> tuple[float | None, bool, str | None]:
    amount = parse_float(raw_fee)
    display = text_or_none(tuition_cn)
    if amount is None or amount <= 0:
        return None, False, display
    return amount, True, display


def normalize_admission_year(value: Any) -> tuple[int | None, bool]:
    if value is None:
        return None, False
    text = str(value).strip()
    if not text or text == "0000":
        return None, False
    try:
        year = int(text)
    except ValueError:
        return None, False
    if 2010 <= year <= 2030:
        return year, True
    return None, False


def normalize_school_tag(value: Any) -> str:
    return text_or_none(value) or "未知背景"
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_normalizers -v
```

Expected: PASS，5 个测试通过。

### Task 3: 三库输出模型

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/models.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_models.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from openision_crawler.libraries.models import AdmissionCase, Program, School


class LibraryModelTests(unittest.TestCase):
    def test_program_to_dict(self) -> None:
        row = Program(program_id="m1", school_id="s1", school_name_cn="学校", major_name_cn="专业").to_dict()
        self.assertEqual(row["program_id"], "m1")
        self.assertEqual(row["case_count"], 0)

    def test_case_to_dict(self) -> None:
        row = AdmissionCase(case_id="c1", program_id="m1", target_school_id="s1").to_dict()
        self.assertEqual(row["case_id"], "c1")
        self.assertFalse(row["english_score_known"])

    def test_school_to_dict(self) -> None:
        row = School(school_id="s1", school_name_cn="学校").to_dict()
        self.assertEqual(row["school_id"], "s1")
        self.assertEqual(row["program_count"], 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_models -v
```

Expected: FAIL，提示 `models` 模块不存在。

- [ ] **Step 3: 实现 dataclass 模型**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Program:
    program_id: str
    school_id: str
    school_name_cn: str | None = None
    school_name_en: str | None = None
    country: str | None = None
    major_name_cn: str | None = None
    major_name_en: str | None = None
    major_direction: str | None = None
    degree_type: str | None = None
    duration_cn: str | None = None
    tuition_cn: str | None = None
    fee_amount: float | None = None
    fee_known: bool = False
    application_requirements_cn: str | None = None
    special_requirements: str | None = None
    language_requirements_detail: Any = None
    application_time: Any = None
    official_url_internal: str | None = None
    case_count: int = 0
    similar_case_count: int = 0
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdmissionCase:
    case_id: str
    program_id: str
    target_school_id: str
    target_school_name_cn: str | None = None
    target_school_name_en: str | None = None
    related_major_name_cn: str | None = None
    related_school_name_cn: str | None = None
    source_school_name: str | None = None
    school_tag_normalized: str = "未知背景"
    major_direction: str | None = None
    china_gpa: float | None = None
    gpa_raw: str | None = None
    english_score: str | None = None
    english_score_known: bool = False
    admission_year: int | None = None
    admission_year_valid: bool = False
    experience_summary: str | None = None
    background_tags: list[str] = field(default_factory=list)
    source_url_internal: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class School:
    school_id: str
    school_name_cn: str | None = None
    school_name_en: str | None = None
    country: str | None = None
    qs_rank: int | None = None
    logo_url_internal: str | None = None
    program_count: int = 0
    case_count: int = 0
    major_directions: list[str] = field(default_factory=list)
    top_programs: list[dict[str, Any]] = field(default_factory=list)
    admitted_gpa_distribution: dict[str, Any] = field(default_factory=dict)
    admission_year_range: dict[str, int | None] = field(default_factory=dict)
    source_record_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_models -v
```

Expected: PASS，3 个测试通过。

### Task 4: 专业库构建模块

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/programs.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_programs.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from openision_crawler.libraries.programs import build_programs


class ProgramBuilderTests(unittest.TestCase):
    def test_build_program_uses_nested_school_country_and_fee_known(self) -> None:
        rows = [
            {
                "id": "m1",
                "school": {"id": "s1", "name": "学校", "name_en": "School", "country": "英国", "qs_rank": 12},
                "major_name_cn": "计算机科学",
                "major_name_en": "Computer Science",
                "major_direction": "计算机",
                "fees": 0,
                "tuition_cn": "待确认",
                "similar_case_count": 2,
            }
        ]
        programs = build_programs(rows, {"m1": 3})
        self.assertEqual(len(programs), 1)
        row = programs[0].to_dict()
        self.assertEqual(row["country"], "英国")
        self.assertFalse(row["fee_known"])
        self.assertEqual(row["case_count"], 3)
        self.assertEqual(row["similar_case_count"], 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_programs -v
```

Expected: FAIL，提示 `programs` 模块不存在。

- [ ] **Step 3: 实现专业库构建**

```python
from __future__ import annotations

from typing import Any

from openision_crawler.libraries.models import Program
from openision_crawler.libraries.normalizers import normalize_fee, text_or_none


def build_programs(source_rows: list[dict[str, Any]], case_counts: dict[str, int]) -> list[Program]:
    programs: list[Program] = []
    for row in source_rows:
        school = row.get("school") or {}
        program_id = str(row.get("id") or "").strip()
        school_id = str(school.get("id") or row.get("school_id") or "").strip()
        if not program_id or not school_id:
            continue
        fee_amount, fee_known, tuition_cn = normalize_fee(row.get("fees"), row.get("tuition_cn"))
        programs.append(
            Program(
                program_id=program_id,
                school_id=school_id,
                school_name_cn=text_or_none(school.get("name") or row.get("school_name")),
                school_name_en=text_or_none(school.get("name_en") or row.get("school_name_en")),
                country=text_or_none(school.get("country")),
                major_name_cn=text_or_none(row.get("major_name_cn")),
                major_name_en=text_or_none(row.get("major_name_en")),
                major_direction=text_or_none(row.get("major_direction")),
                degree_type=text_or_none(row.get("degree_type")),
                duration_cn=text_or_none(row.get("duration_cn")),
                tuition_cn=tuition_cn,
                fee_amount=fee_amount,
                fee_known=fee_known,
                application_requirements_cn=text_or_none(row.get("application_requirements_cn")),
                special_requirements=text_or_none(row.get("special_requirements")),
                language_requirements_detail=row.get("language_requirements_detail"),
                application_time=row.get("application_time"),
                official_url_internal=text_or_none(row.get("official_url")),
                case_count=case_counts.get(program_id, 0),
                similar_case_count=int(row.get("similar_case_count") or 0),
                updated_at=text_or_none(row.get("updated_at")),
            )
        )
    return sorted(programs, key=lambda item: item.program_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_programs -v
```

Expected: PASS，1 个测试通过。

### Task 5: 案例库构建模块

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/cases.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_cases.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from openision_crawler.libraries.cases import build_cases, count_cases_by_program


class CaseBuilderTests(unittest.TestCase):
    def test_build_case_normalizes_year_gpa_and_unknown_school_tag(self) -> None:
        rows = [
            {
                "id": "c1",
                "major_id": "m1",
                "target_school_id": "s1",
                "target_school_name": "学校",
                "school_name": "本科",
                "school_tag": "",
                "china_gpa": "87.5",
                "admission_year": "0000",
                "english_score": "",
                "exp_info": "科研一段",
            }
        ]
        cases = build_cases(rows)
        row = cases[0].to_dict()
        self.assertEqual(row["school_tag_normalized"], "未知背景")
        self.assertEqual(row["china_gpa"], 87.5)
        self.assertFalse(row["admission_year_valid"])
        self.assertFalse(row["english_score_known"])

    def test_count_cases_by_program(self) -> None:
        self.assertEqual(count_cases_by_program([{"major_id": "m1"}, {"major_id": "m1"}]), {"m1": 2})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_cases -v
```

Expected: FAIL，提示 `cases` 模块不存在。

- [ ] **Step 3: 实现案例库构建**

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from openision_crawler.libraries.models import AdmissionCase
from openision_crawler.libraries.normalizers import (
    normalize_admission_year,
    normalize_school_tag,
    parse_float,
    text_or_none,
)


def count_cases_by_program(source_rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in source_rows:
        program_id = text_or_none(row.get("major_id"))
        if program_id:
            counter[program_id] += 1
    return dict(counter)


def build_cases(source_rows: list[dict[str, Any]]) -> list[AdmissionCase]:
    cases: list[AdmissionCase] = []
    for row in source_rows:
        case_id = text_or_none(row.get("id"))
        program_id = text_or_none(row.get("major_id"))
        school_id = text_or_none(row.get("target_school_id"))
        if not case_id or not program_id or not school_id:
            continue
        year, year_valid = normalize_admission_year(row.get("admission_year"))
        english_score = text_or_none(row.get("english_score"))
        cases.append(
            AdmissionCase(
                case_id=case_id,
                program_id=program_id,
                target_school_id=school_id,
                target_school_name_cn=text_or_none(row.get("target_school_name")),
                target_school_name_en=text_or_none(row.get("target_school_name_en")),
                related_major_name_cn=text_or_none(row.get("related_major_name_cn")),
                related_school_name_cn=text_or_none(row.get("related_school_name_cn")),
                source_school_name=text_or_none(row.get("school_name")),
                school_tag_normalized=normalize_school_tag(row.get("school_tag")),
                major_direction=text_or_none(row.get("major_direction")),
                china_gpa=parse_float(row.get("china_gpa") or row.get("gpa")),
                gpa_raw=text_or_none(row.get("gpa")),
                english_score=english_score,
                english_score_known=english_score is not None,
                admission_year=year,
                admission_year_valid=year_valid,
                experience_summary=text_or_none(row.get("exp_info")),
                background_tags=[],
                source_url_internal=text_or_none(row.get("url") or row.get("source_url")),
            )
        )
    return sorted(cases, key=lambda item: item.case_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_cases -v
```

Expected: PASS，2 个测试通过。

### Task 6: 院校库聚合模块

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/schools.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_schools.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from openision_crawler.libraries.models import AdmissionCase, Program
from openision_crawler.libraries.schools import build_schools


class SchoolBuilderTests(unittest.TestCase):
    def test_build_school_aggregates_programs_and_cases(self) -> None:
        programs = [
            Program(program_id="m1", school_id="s1", school_name_cn="学校", country="英国", major_direction="计算机"),
            Program(program_id="m2", school_id="s1", school_name_cn="学校", country="英国", major_direction="金融"),
        ]
        cases = [
            AdmissionCase(case_id="c1", program_id="m1", target_school_id="s1", china_gpa=87.0, admission_year=2025, admission_year_valid=True),
            AdmissionCase(case_id="c2", program_id="m2", target_school_id="s1", china_gpa=90.0, admission_year=2024, admission_year_valid=True),
        ]
        schools = build_schools(programs, cases)
        row = schools[0].to_dict()
        self.assertEqual(row["program_count"], 2)
        self.assertEqual(row["case_count"], 2)
        self.assertEqual(row["major_directions"], ["计算机", "金融"])
        self.assertEqual(row["admission_year_range"], {"min": 2024, "max": 2025})
        self.assertEqual(row["admitted_gpa_distribution"]["avg"], 88.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_schools -v
```

Expected: FAIL，提示 `schools` 模块不存在。

- [ ] **Step 3: 实现院校聚合**

```python
from __future__ import annotations

from collections import defaultdict

from openision_crawler.libraries.models import AdmissionCase, Program, School


def _gpa_distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2),
    }


def build_schools(programs: list[Program], cases: list[AdmissionCase]) -> list[School]:
    programs_by_school: dict[str, list[Program]] = defaultdict(list)
    cases_by_school: dict[str, list[AdmissionCase]] = defaultdict(list)

    for program in programs:
        programs_by_school[program.school_id].append(program)
    for case in cases:
        cases_by_school[case.target_school_id].append(case)

    schools: list[School] = []
    for school_id in sorted(set(programs_by_school) | set(cases_by_school)):
        school_programs = programs_by_school.get(school_id, [])
        school_cases = cases_by_school.get(school_id, [])
        first = school_programs[0] if school_programs else None
        directions = sorted({item.major_direction for item in school_programs if item.major_direction})
        years = [item.admission_year for item in school_cases if item.admission_year_valid and item.admission_year]
        gpas = [item.china_gpa for item in school_cases if item.china_gpa is not None]
        schools.append(
            School(
                school_id=school_id,
                school_name_cn=first.school_name_cn if first else None,
                school_name_en=first.school_name_en if first else None,
                country=first.country if first else None,
                program_count=len(school_programs),
                case_count=len(school_cases),
                major_directions=directions,
                top_programs=[
                    {"program_id": item.program_id, "major_name_cn": item.major_name_cn}
                    for item in school_programs[:10]
                ],
                admitted_gpa_distribution=_gpa_distribution(gpas),
                admission_year_range={"min": min(years) if years else None, "max": max(years) if years else None},
                source_record_count=len(school_programs) + len(school_cases),
            )
        )
    return schools
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_schools -v
```

Expected: PASS，1 个测试通过。

### Task 7: 数据质量报告模块

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/quality.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_quality.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from openision_crawler.libraries.models import AdmissionCase, Program, School
from openision_crawler.libraries.quality import build_quality_report


class QualityReportTests(unittest.TestCase):
    def test_quality_report_counts_join_failures_and_unknowns(self) -> None:
        programs = [Program(program_id="m1", school_id="s1", fee_known=False)]
        cases = [AdmissionCase(case_id="c1", program_id="m1", target_school_id="s1", admission_year_valid=False)]
        schools = [School(school_id="s1")]
        report = build_quality_report(programs, cases, schools)
        self.assertEqual(report["counts"]["programs"], 1)
        self.assertEqual(report["counts"]["cases"], 1)
        self.assertEqual(report["counts"]["schools"], 1)
        self.assertEqual(report["joins"]["case_program_join_failures"], 0)
        self.assertEqual(report["quality"]["unknown_fee_programs"], 1)
        self.assertEqual(report["quality"]["invalid_year_cases"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_quality -v
```

Expected: FAIL，提示 `quality` 模块不存在。

- [ ] **Step 3: 实现报告函数**

```python
from __future__ import annotations

from typing import Any

from openision_crawler.libraries.models import AdmissionCase, Program, School


def build_quality_report(programs: list[Program], cases: list[AdmissionCase], schools: list[School]) -> dict[str, Any]:
    program_ids = {item.program_id for item in programs}
    school_ids = {item.school_id for item in schools}
    return {
        "counts": {
            "programs": len(programs),
            "cases": len(cases),
            "schools": len(schools),
        },
        "joins": {
            "case_program_join_failures": sum(1 for item in cases if item.program_id not in program_ids),
            "case_school_join_failures": sum(1 for item in cases if item.target_school_id not in school_ids),
        },
        "quality": {
            "unknown_fee_programs": sum(1 for item in programs if not item.fee_known),
            "invalid_year_cases": sum(1 for item in cases if not item.admission_year_valid),
            "unknown_english_score_cases": sum(1 for item in cases if not item.english_score_known),
            "unknown_school_tag_cases": sum(1 for item in cases if item.school_tag_normalized == "未知背景"),
        },
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_quality -v
```

Expected: PASS，1 个测试通过。

### Task 8: 三库构建协调器

**Files:**

- Create: `liuxue/openision-crawler/src/openision_crawler/libraries/build.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_build.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
import tempfile
import unittest

from openision_crawler.libraries.build import build_libraries
from openision_crawler.libraries.io import write_jsonl


class LibraryBuildTests(unittest.TestCase):
    def test_build_libraries_writes_three_jsonl_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "data" / "normalized" / "majors_list.jsonl",
                [{"id": "m1", "school": {"id": "s1", "name": "学校", "country": "英国"}, "major_name_cn": "专业"}],
            )
            write_jsonl(
                root / "data" / "normalized" / "cases_list.jsonl",
                [{"id": "c1", "major_id": "m1", "target_school_id": "s1", "target_school_name": "学校"}],
            )
            report = build_libraries(root)
            self.assertEqual(report["counts"]["programs"], 1)
            self.assertTrue((root / "data" / "libraries" / "program_library.jsonl").exists())
            self.assertTrue((root / "data" / "libraries" / "school_library.jsonl").exists())
            self.assertTrue((root / "data" / "libraries" / "admission_case_library.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_build -v
```

Expected: FAIL，提示 `build` 模块不存在。

- [ ] **Step 3: 实现构建协调器**

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openision_crawler.libraries.cases import build_cases, count_cases_by_program
from openision_crawler.libraries.io import contains_sensitive_key, read_jsonl, write_jsonl
from openision_crawler.libraries.programs import build_programs
from openision_crawler.libraries.quality import build_quality_report
from openision_crawler.libraries.schools import build_schools


def build_libraries(project_root: Path) -> dict[str, Any]:
    majors_path = project_root / "data" / "normalized" / "majors_list.jsonl"
    cases_path = project_root / "data" / "normalized" / "cases_list.jsonl"
    output_dir = project_root / "data" / "libraries"
    report_dir = project_root / "data" / "reports"

    major_rows = read_jsonl(majors_path)
    case_rows = read_jsonl(cases_path)
    cases = build_cases(case_rows)
    programs = build_programs(major_rows, count_cases_by_program(case_rows))
    schools = build_schools(programs, cases)

    program_rows = [item.to_dict() for item in programs]
    case_output_rows = [item.to_dict() for item in cases]
    school_rows = [item.to_dict() for item in schools]
    sensitive_count = sum(
        1
        for row in [*program_rows, *case_output_rows, *school_rows]
        if contains_sensitive_key(row)
    )

    write_jsonl(output_dir / "program_library.jsonl", program_rows)
    write_jsonl(output_dir / "admission_case_library.jsonl", case_output_rows)
    write_jsonl(output_dir / "school_library.jsonl", school_rows)

    report = build_quality_report(programs, cases, schools)
    report["security"] = {"sensitive_key_rows": sensitive_count}
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "library_quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return report
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_build -v
```

Expected: PASS，1 个测试通过。

### Task 9: CLI 命令

**Files:**

- Modify: `liuxue/openision-crawler/src/openision_crawler/cli.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_cli.py`

- [ ] **Step 1: 读取现有 CLI 结构**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
sed -n '1,260p' src/openision_crawler/cli.py
```

Expected: 看到现有 argparse 子命令定义和 `main()` 函数。

- [ ] **Step 2: 写失败测试**

```python
import unittest

from openision_crawler.cli import build_parser


class LibraryCliTests(unittest.TestCase):
    def test_build_libraries_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["build-libraries"])
        self.assertEqual(args.command, "build-libraries")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_cli -v
```

Expected: FAIL，提示 `build-libraries` 不是可识别命令。

- [ ] **Step 4: 修改 CLI**

在 `build_parser()` 中新增子命令：

```python
build_libraries_parser = subparsers.add_parser(
    "build-libraries",
    help="Build Helipei program, school, and admission case libraries from normalized crawl data.",
)
build_libraries_parser.add_argument(
    "--project-root",
    default=".",
    help="Path to openision-crawler project root. Defaults to current directory.",
)
```

在 `main()` 的命令分发中新增：

```python
if args.command == "build-libraries":
    from pathlib import Path

    from openision_crawler.libraries.build import build_libraries

    report = build_libraries(Path(args.project_root).resolve())
    print(f"Built libraries: {report['counts']}")
    return 0
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_cli -v
```

Expected: PASS，1 个测试通过。

### Task 10: SQLite 三库表

**Files:**

- Modify: `liuxue/openision-crawler/src/openision_crawler/storage.py`
- Create: `liuxue/openision-crawler/tests/test_libraries_storage.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
import sqlite3
import tempfile
import unittest

from openision_crawler.storage import Storage


class LibraryStorageTests(unittest.TestCase):
    def test_init_db_creates_library_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "openision.sqlite"
            Storage(db_path).init_db()
            with sqlite3.connect(db_path) as conn:
                names = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            self.assertIn("program_library", names)
            self.assertIn("school_library", names)
            self.assertIn("admission_case_library", names)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_storage -v
```

Expected: FAIL，三张表不存在。

- [ ] **Step 3: 增加表结构**

在 `Storage.init_db()` 的 schema 初始化中加入：

```sql
CREATE TABLE IF NOT EXISTS program_library (
    program_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS school_library (
    school_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS admission_case_library (
    case_id TEXT PRIMARY KEY,
    program_id TEXT NOT NULL,
    target_school_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest tests.test_libraries_storage -v
```

Expected: PASS，1 个测试通过。

### Task 11: README 文档更新

**Files:**

- Modify: `liuxue/openision-crawler/README.md`

- [ ] **Step 1: 增加三库章节**

在 `README.md` 的“输出”章节后新增：

````markdown
## 生成河狸陪三库

三库生成使用已落盘的 `data/normalized/majors_list.jsonl` 和 `data/normalized/cases_list.jsonl`，不访问线上网络。

```bash
PYTHONPATH=src python3 -m openision_crawler.cli build-libraries
```

输出：

- `data/libraries/program_library.jsonl`
- `data/libraries/school_library.jsonl`
- `data/libraries/admission_case_library.jsonl`
- `data/reports/library_quality_report.json`

合规说明：

- 院校库是由专业和案例聚合生成的派生库。
- GPA 只作为申请参考或案例背景，不代表录取线。
- 学费未知值不会被展示成免费。
- 来源 URL 和第三方资源 URL 只作为内部溯源字段。
````

- [ ] **Step 2: 运行文档检查**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text(encoding="utf-8")
required = [
    "生成河狸陪三库",
    "build-libraries",
    "program_library.jsonl",
    "school_library.jsonl",
    "admission_case_library.jsonl",
]
missing = [item for item in required if item not in text]
raise SystemExit(f"missing: {missing}" if missing else "README ok")
PY
```

Expected: 输出 `README ok`。

### Task 12: 全量验收命令

**Files:**

- No source file required.

- [ ] **Step 1: 运行完整单元测试**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: PASS，所有测试通过。

- [ ] **Step 2: 运行三库构建**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
PYTHONPATH=src python3 -m openision_crawler.cli build-libraries
```

Expected: 输出类似：

```text
Built libraries: {'programs': 10391, 'cases': 31708, 'schools': 134}
```

- [ ] **Step 3: 检查输出文件**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
wc -l data/libraries/program_library.jsonl data/libraries/admission_case_library.jsonl data/libraries/school_library.jsonl
```

Expected:

```text
10391 data/libraries/program_library.jsonl
31708 data/libraries/admission_case_library.jsonl
school_library 行数等于派生院校数，当前审计约为 134
```

- [ ] **Step 4: 检查质量报告**

Run:

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("data/reports/library_quality_report.json").read_text(encoding="utf-8"))
assert report["joins"]["case_program_join_failures"] == 0
assert report["joins"]["case_school_join_failures"] == 0
assert report["security"]["sensitive_key_rows"] == 0
print("quality ok")
PY
```

Expected: 输出 `quality ok`。

## 验收清单

- [ ] 三库 JSONL 均能生成。
- [ ] 专业库记录数为 `10,391`。
- [ ] 案例库记录数为 `31,708`。
- [ ] 院校库由专业和案例聚合生成。
- [ ] 案例到专业 join 失败数为 `0`。
- [ ] 案例到院校 join 失败数为 `0`。
- [ ] 敏感字段扫描结果为 `0`。
- [ ] 学费 `0` 不展示为免费。
- [ ] 无效年份不进入筛选统计。
- [ ] README 包含三库生成命令和合规说明。

## 执行建议

推荐使用 `superpowers:subagent-driven-development` 按任务逐个实现，每个任务完成后运行对应测试。若在当前会话内实现，使用 `superpowers:executing-plans`，每完成 2 到 3 个任务做一次测试 checkpoint。

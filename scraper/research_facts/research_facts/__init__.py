"""科研素材事实输入包 (research fact input package).

把课题海报、项目手册、网页资料整理成同一套带证据的 JSON：六个规范字段，
每个字段都带原文、来源位置、抽取方式与宣传标记。未知字段不补写，矛盾资料
保留双方证据，重复导入结果稳定。
"""

from __future__ import annotations

from .config import CANONICAL_FIELDS, FIELD_NAMES, Settings
from .exporter import build_export, render_markdown, render_public_markdown
from .errors import (
    FactPackageError,
    InputError,
    ParseError,
    SchemaValidationError,
    StorageError,
)
from .review import ReviewDecision, ReviewRegistry, evidence_fingerprint
from .schema import (
    FieldClaim,
    FieldState,
    Identity,
    Locator,
    ProjectFactRecord,
)

__all__ = [
    "CANONICAL_FIELDS",
    "FIELD_NAMES",
    "FactPackageError",
    "FieldClaim",
    "FieldState",
    "Identity",
    "InputError",
    "Locator",
    "ParseError",
    "ProjectFactRecord",
    "ReviewDecision",
    "ReviewRegistry",
    "build_export",
    "evidence_fingerprint",
    "render_markdown",
    "render_public_markdown",
    "SchemaValidationError",
    "Settings",
    "StorageError",
    "__version__",
]

__version__ = "0.1.0"

"""Command line entry point.

Commands
--------
``ingest``    read sources, build fact records, write facts + reports
``report``    re-print reports from an existing output directory
``validate``  re-validate ``facts.jsonl`` against the canonical schema
``field``     show the evidence behind one field of one record
``profiles``  print the web source field table (the wiring surface)

Every command supports ``--dry-run``. ``ingest --dry-run`` reads the inputs and
prints the target files, the canonical field list, and the record preview
without writing anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .adapters import describe_adapters
from .adapters.web_json import SOURCE_PROFILES, profile_catalog
from .config import FIELD_NAMES, Settings, field_label
from .errors import FactPackageError, InputError
from .exporter import build_export, export_summary
from .logging_utils import configure_logging
from .pipeline import ingest, run_dry_run
from .projections import describe_publication
from .review import REVIEW_FILE, ReviewRegistry, evidence_fingerprint
from .schema import claim_display_value
from .storage import atomic_write_text, read_json, read_records

SOURCE_KINDS = ("poster_ocr", "handbook_pdf", "web_json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research_facts",
        description="科研素材事实输入包：把海报、手册、网页资料整理成带证据的统一 JSON。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", default="data/facts", help="输出目录 (default: data/facts)")
    common.add_argument("--verbose", action="store_true", help="输出 debug 级结构化日志")

    ingest_parser = sub.add_parser("ingest", parents=[common], help="提取并生成事实包")
    ingest_parser.add_argument(
        "--input",
        action="append",
        default=[],
        required=True,
        help="输入文件，可重复。可写成 path:kind (poster_ocr|handbook_pdf|web_json) 显式指定来源类型。",
    )
    ingest_parser.add_argument("--profile", default=None, help="web_json 强制使用指定 source profile")
    ingest_parser.add_argument(
        "--profile-file",
        action="append",
        default=[],
        help="加载 JSON 字段表（真实接线用），可重复。",
    )
    ingest_parser.add_argument(
        "--merge-file",
        default=None,
        help="加载人工合并决定 (default: <output-dir>/merges.json)",
    )
    ingest_parser.add_argument("--max-records", type=int, default=None, help="每个输入文件的文档数上限")
    ingest_parser.add_argument("--dry-run", action="store_true", help="只读预演，不写任何文件")
    ingest_parser.add_argument(
        "--identity-threshold", type=float, default=0.90, help="标题相似度归组阈值 (default: 0.90)"
    )
    ingest_parser.add_argument(
        "--strict-identity", action="store_true", help="只按 external_id 归组，禁用标题相似度"
    )
    ingest_parser.add_argument("--json", action="store_true", help="以 JSON 输出运行摘要")

    report_parser = sub.add_parser("report", parents=[common], help="打印已有输出目录中的报告")
    report_parser.add_argument("--json", action="store_true", help="输出完整 JSON")

    validate_parser = sub.add_parser("validate", parents=[common], help="校验 facts.jsonl")
    validate_parser.add_argument("--facts", default=None, help="facts.jsonl 路径 (default: <output-dir>/facts.jsonl)")

    field_parser = sub.add_parser("field", parents=[common], help="查看某个字段的全部证据")
    field_parser.add_argument("--facts", default=None)
    field_parser.add_argument("--record", required=True, help="record_key，支持前缀匹配")
    field_parser.add_argument("--field", required=True, choices=list(FIELD_NAMES))

    review_parser = sub.add_parser("review", parents=[common], help="记录/查看人工审核决定")
    review_parser.add_argument("--facts", default=None)
    review_parser.add_argument("--review-file", default=None, help="审核文件路径 (default: <output-dir>/reviews.json)")
    review_parser.add_argument("--merge-file", default=None, help="合并决定文件路径 (default: <output-dir>/merges.json)")
    review_parser.add_argument("--record", default=None, help="record_key，支持前缀匹配")
    review_parser.add_argument("--field", default=None, choices=list(FIELD_NAMES))
    group = review_parser.add_mutually_exclusive_group()
    group.add_argument("--approve", action="store_true", help="记录通过")
    group.add_argument("--reject", action="store_true", help="记录否决")
    group.add_argument("--reset", action="store_true", help="撤销已有决定")
    group.add_argument("--list", action="store_true", help="列出全部决定")
    group.add_argument(
        "--adjudicate",
        action="store_true",
        help="裁决冲突：必须用 --choose 指定采用哪一方的原话",
    )
    review_parser.add_argument("--reviewer", default=None, help="审核人")
    review_parser.add_argument("--note", default="", help="审核备注")
    review_parser.add_argument(
        "--choose",
        default=None,
        help="裁决时采用的那一方原话（必须逐字等于来源说过的话，不能自创）",
    )
    review_parser.add_argument(
        "--show-sides", action="store_true", help="列出该字段各方的说法（裁决前先看这个）"
    )

    export_parser = sub.add_parser("export", parents=[common], help="导出写稿/做图用事实卡")
    export_parser.add_argument("--facts", default=None)
    export_parser.add_argument("--review-file", default=None)
    export_parser.add_argument("--record", default=None, help="record_key，支持前缀匹配；缺省导出全部")
    export_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    export_parser.add_argument("--public", action="store_true", help="导出对外投影（已过滤宣传、含审核结论）")
    export_parser.add_argument("--out", default=None, help="输出文件；缺省打印到标准输出")

    inspect_parser = sub.add_parser(
        "inspect", parents=[common], help="接线自检：候选源可映射性与覆盖率，不落盘"
    )
    inspect_parser.add_argument("--input", action="append", default=[], required=True)
    inspect_parser.add_argument("--profile", default=None)
    inspect_parser.add_argument("--profile-file", action="append", default=[])
    inspect_parser.add_argument("--max-records", type=int, default=300)
    inspect_parser.add_argument("--json", action="store_true")

    sub.add_parser("profiles", help="打印 web 来源字段表（真实接线用）")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(
        output_dir=Path(getattr(args, "output_dir", "data/facts")),
        max_records=getattr(args, "max_records", None),
        dry_run=bool(getattr(args, "dry_run", False)),
        verbose=bool(getattr(args, "verbose", False)),
        inputs=list(getattr(args, "input", []) or []),
        identity_similarity_threshold=float(getattr(args, "identity_threshold", 0.90)),
        strict_identity=bool(getattr(args, "strict_identity", False)),
        profile=getattr(args, "profile", None),
        profile_files=list(getattr(args, "profile_file", []) or []),
        merge_file=getattr(args, "merge_file", None),
    )


def _facts_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "facts", None)
    if explicit:
        return Path(explicit)
    return Path(getattr(args, "output_dir", "data/facts")) / "facts.jsonl"


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_ingest(args: argparse.Namespace) -> int:
    settings = settings_from_args(args)
    if settings.profile and settings.profile not in SOURCE_PROFILES:
        print(f"未知 profile: {settings.profile}；可用: {', '.join(sorted(SOURCE_PROFILES))}", file=sys.stderr)
        return 2

    if settings.dry_run:
        payload = run_dry_run(settings)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload["errors"] else 0

    result = ingest(settings)
    summary = _ingest_summary(result)
    if getattr(args, "json", False):
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_ingest_summary(result, settings)
    return 1 if result.errors else 0


def _ingest_summary(result: Any) -> dict[str, Any]:
    reports = result.reports
    return {
        "output_dir": str(result.settings.output_dir),
        "content_digest": result.digest,
        "counts": result.manifest.get("counts", {}),
        "missing": {
            name: reports["missing"]["by_field"][name]["missing_count"] for name in FIELD_NAMES
        },
        "conflicts": reports["conflict"]["total_conflicts"],
        "promotional_claims": reports["promotional"]["total"],
        "public_summary": result.manifest.get("public_summary", {}),
        "errors": result.errors,
        "outputs": result.manifest.get("outputs", {}),
    }


def _print_ingest_summary(result: Any, settings: Settings) -> None:
    reports = result.reports
    quality = reports["quality"]
    counts = result.manifest.get("counts", {})
    print("科研素材事实输入包 · 运行完成")
    print(f"  输出目录      : {settings.output_dir}")
    print(
        f"  来源文档      : {counts.get('documents')}   记录 {counts.get('records')}   "
        f"证据 {counts.get('evidence_rows')}"
    )
    print(f"  内容摘要      : {result.digest}")
    print("  字段可用率    :")
    for name in FIELD_NAMES:
        item = quality["field_coverage"][name]
        statuses = item["status_counts"]
        detail = (
            f"可用 {item['usable']} / 缺失 {statuses['missing']} / "
            f"冲突 {statuses['conflict']} / 仅宣传 {statuses['promotional_only']}"
        )
        print(f"    - {item['field_label']}({name}) [{item['risk_level']}] {detail}")
    print(f"  冲突          : {reports['conflict']['total_conflicts']} 处，双方证据均已保留")
    print(f"  宣传表述      : {reports['promotional']['total']} 处（仅宣传字段 {len(reports['promotional']['fields_with_promotional_only'])} 个）")
    counts = result.manifest.get("counts", {})
    merge_info = result.manifest.get("merges", {})
    if merge_info.get("applied"):
        print(
            f"  人工合并      : 应用 {merge_info['applied']} 对"
            + (f"，跳过 {merge_info['skipped']} 对" if merge_info.get("skipped") else "")
        )
    print(
        f"  同名不同批次  : {counts.get('cohort_groups', 0)} 个课题组"
        f"（共 {result.manifest.get('cohorts', {}).get('records_in_groups', 0)} 条记录，不合并）"
    )
    print(
        f"  重复候选      : {counts.get('duplicate_candidates', 0)} 对"
        f"（高置信 {counts.get('high_confidence_duplicates', 0)}，只生成候选不自动合并）"
    )
    print(f"  对外可用      : {describe_publication(result.records, result.reviews)}")
    if result.errors:
        print(f"  错误          : {result.errors}")
    print("  文件          :")
    for key, path in result.manifest.get("outputs", {}).items():
        print(f"    - {key}: {path}")


def cmd_report(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    names = {
        "missing": output_dir / "missing_report.json",
        "conflict": output_dir / "conflict_report.json",
        "promotional": output_dir / "promotional_claims_report.json",
        "quality": output_dir / "quality_summary.json",
        "manifest": output_dir / "run_manifest.json",
    }
    if args.json:
        payload = {name: read_json(path) for name, path in names.items() if path.exists()}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    missing = read_json(names["missing"])
    conflict = read_json(names["conflict"])
    promotional = read_json(names["promotional"])
    quality = read_json(names["quality"])

    print("缺失报告")
    for name in FIELD_NAMES:
        item = missing["by_field"][name]
        print(f"  - {item['field_label']}({name}): 缺失 {item['missing_count']}，覆盖率 {item['coverage_rate']}")
    if missing["records_without_any_usable_field"]:
        print(f"  全字段不可用: {', '.join(missing['records_without_any_usable_field'])}")

    print("\n冲突报告")
    if not conflict["conflicts"]:
        print("  - 无")
    for item in conflict["conflicts"]:
        values = "  ||  ".join(value["value"] for value in item["values"])
        print(f"  - {item['record_key']} / {item['field_label']}({item['field']}): {values}")
        for side in item["values"]:
            for detail in side["sides"]:
                print(f"      · {detail['document_id']} {detail['locator']} → {detail['raw_text'][:60]}")

    print("\n宣传表述报告")
    print(f"  - 合计 {promotional['total']}，分类 {promotional['by_kind']}")
    for item in promotional["fields_with_promotional_only"]:
        print(f"  - 仅宣传不可用: {item['record_key']} / {item['field_label']}")
    digest = quality.get("content_digest")
    if digest:
        print(f"\n内容摘要: {digest}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = _facts_path(args)
    records = read_records(path)
    problems: list[str] = []
    for record in records:
        try:
            record.validate()
        except FactPackageError as exc:
            problems.append(f"{record.record_key}: {exc}")
    print(f"校验 {path}：{len(records)} 条记录")
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}")
        return 1
    print("  ✓ 全部记录符合规范字段结构")
    return 0


def cmd_field(args: argparse.Namespace) -> int:
    path = _facts_path(args)
    try:
        record = _resolve_record(read_records(path), args.record)
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    state = record.fields[args.field]
    print(f"记录      : {record.record_key}")
    print(f"身份      : {record.identity.provider} / {record.identity.external_id or record.identity.title_hint}")
    print(f"字段      : {field_label(args.field)} ({args.field})  风险 {state.risk_level}")
    print(f"状态      : {state.status}   核验 {state.claims[0].verification_status if state.claims else 'unverified'}")
    print(f"取值      : {state.selected_normalized_value or '（未采用：' + state.note + '）'}")
    if state.conflict_values:
        print(f"冲突取值  : {len(state.conflict_values)} 种")
    print("证据:")
    if not state.claims:
        print("  （无任何来源提到该字段，未补写）")
    for claim in state.claims:
        print(f"  - [{claim.evidence_kind}] {claim.locator.document_id} {claim.locator.pointer}")
        print(f"      原文  : {claim.raw_text}")
        print(f"      归一  : {claim.normalized_value}   置信 {claim.extraction_confidence}   方式 {claim.extraction_method}")
        if claim.matched_phrases:
            print(f"      宣传标记: {', '.join(claim.matched_phrases)}")
    if state.note:
        print(f"说明      : {state.note}")
    return 0


def _resolve_record(records, prefix: str) -> Any:
    matches = [record for record in records if record.record_key.startswith(prefix)]
    if not matches:
        raise InputError(f"未找到记录: {prefix}")
    if len(matches) > 1:
        listing = "\n".join(f"  - {item.record_key}" for item in matches[:10])
        raise InputError(f"匹配到 {len(matches)} 条，请提供更长的 record_key 前缀:\n{listing}")
    return matches[0]


def _review_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "review_file", None)
    if explicit:
        return Path(explicit)
    return Path(getattr(args, "output_dir", "data/facts")) / REVIEW_FILE


def cmd_review(args: argparse.Namespace) -> int:
    """Record or list human review decisions.

    The fingerprint is read from the current facts file, not typed in by hand,
    so an approval always refers to the evidence that is actually on disk.
    """
    review_path = _review_path(args)
    registry = ReviewRegistry.load(review_path)

    if getattr(args, "list", False):
        rows = registry.rows()
        if not rows:
            print(f"审核文件 {review_path} 暂无决定")
            return 0
        print(f"审核决定（{review_path}）")
        for item in rows:
            print(
                f"  - {item['record_key']} / {field_label(item['field'])}"
                f" → {item['decision']} · 指纹 {item['fingerprint'][:12]}"
                f" · {item['reviewer']} · {item['reviewed_at']}"
            )
        print(f"统计：{registry.counts()}")
        return 0

    if not getattr(args, "record", None) or not getattr(args, "field", None):
        print("需要 --record 与 --field（或使用 --list）", file=sys.stderr)
        return 2

    records = read_records(_facts_path(args))
    record = _resolve_record(records, args.record)
    state = record.fields[args.field]
    fingerprint = evidence_fingerprint(state)

    if getattr(args, "show_sides", False):
        _print_sides(record, state)
        return 0

    if getattr(args, "adjudicate", False):
        if state.status != "conflict":
            print(f"该字段当前状态为 {state.status}，不是冲突，无需裁决。", file=sys.stderr)
            return 1
        if not getattr(args, "choose", None):
            print("裁决必须用 --choose 指定采用哪一方的原话。", file=sys.stderr)
            _print_sides(record, state, stream=sys.stderr)
            return 2
        valid = _valid_choices(state)
        if args.choose not in valid:
            print(
                f"「{args.choose}」不是任何来源说过的话，裁决无效。\n"
                f"只能逐字使用以下之一：{'、'.join(valid)}",
                file=sys.stderr,
            )
            return 2
        existing = registry.get(record.record_key, args.field)
        if existing is not None and existing.fingerprint != fingerprint:
            print(
                "注意：证据已变化，旧裁决会失效。本次裁决将绑定当前证据指纹。",
                file=sys.stderr,
            )
        registry.set(
            record.record_key,
            args.field,
            "adjudicated",
            fingerprint,
            reviewer=getattr(args, "reviewer", None) or "unknown",
            note=getattr(args, "note", "") or "",
            chosen_value=args.choose,
        )
        registry.save(review_path)
        print(f"已裁决：{record.record_key} / {field_label(args.field)} → 采用「{args.choose}」")
        print(f"  指纹：{fingerprint}")
        print(f"  文件：{review_path}")
        print("  提示：重跑 ingest 后生效；被舍弃的一方仍作为证据保留。")
        return 0

    if getattr(args, "reset", False):
        if registry.reset(record.record_key, args.field):
            registry.save(review_path)
            print(f"已撤销：{record.record_key} / {field_label(args.field)}")
            return 0
        print("没有可撤销的决定", file=sys.stderr)
        return 1

    if not state.is_usable or state.selected_raw_text is None:
        print(
            f"该字段当前状态为 {state.status}，没有可审核的取值。"
            "冲突字段需先人工裁决，缺失字段没有可核实的内容。",
            file=sys.stderr,
        )
        return 1

    decision = "approved" if getattr(args, "approve", False) else "rejected"
    if not (getattr(args, "approve", False) or getattr(args, "reject", False)):
        print("需要 --approve / --reject / --reset 之一", file=sys.stderr)
        return 2

    registry.set(
        record.record_key,
        args.field,
        decision,
        fingerprint,
        reviewer=getattr(args, "reviewer", None) or "unknown",
        note=getattr(args, "note", "") or "",
    )
    registry.save(review_path)
    print(f"已记录：{record.record_key} / {field_label(args.field)} → {decision}")
    print(f"  取值  ：{_one_line(state.selected_raw_text)}")
    print(f"  指纹  ：{fingerprint}")
    print(f"  文件  ：{review_path}")
    if decision == "approved":
        print("  提示  ：审核只解除高风险门禁；宣传表述仍不会进入对外文案。")
    return 0


def _cohort_index_for(output_dir: str) -> dict:
    """Read the cohort report from a previous run, if it is there.

    Export is a read-only view, so a missing report simply means no cohort
    context -- it must not stop the export.
    """
    from .dedup import cohort_index

    path = Path(output_dir) / "cohort_groups.json"
    if not path.exists():
        return {}
    try:
        return cohort_index(read_json(path))
    except Exception:  # noqa: BLE001 - advisory context only
        return {}


def cmd_export(args: argparse.Namespace) -> int:
    """Render fact cards for writing, graphics, or Q&A."""
    records = read_records(_facts_path(args))
    if getattr(args, "record", None):
        records = [_resolve_record(records, args.record)]
    reviews = ReviewRegistry.load(_review_path(args))
    cohort_map = _cohort_index_for(args.output_dir)
    payload = build_export(
        records,
        reviews,
        public=bool(getattr(args, "public", False)),
        cohorts=cohort_map,
    )

    if getattr(args, "format", "markdown") == "json":
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
    else:
        text = "\n".join(item["markdown"] for item in payload["records"])
        text += f"\n<!-- {export_summary(payload)} -->\n"

    out = getattr(args, "out", None)
    if out:
        atomic_write_text(Path(out), text)
        print(f"已写入 {out}：{export_summary(payload)}")
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


def _print_sides(record: Any, state: Any, stream: Any = None) -> None:
    """List the competing statements so an adjudicator can pick a real one."""
    out = stream or sys.stdout
    print(f"字段：{field_label(state.field)} ({state.field})  状态：{state.status}", file=out)
    if state.note:
        print(f"说明：{state.note}", file=out)
    if not state.claims:
        print("  （无任何来源提到该字段）", file=out)
        return
    groups: dict[str, list[Any]] = {}
    for claim in state.claims:
        groups.setdefault(claim.compare_value, []).append(claim)
    print("各方说法（--choose 需逐字使用其中一条的原话）：", file=out)
    for index, key in enumerate(sorted(groups), start=1):
        sides = groups[key]
        claim = sides[0]
        marker = "" if claim.evidence_kind == "factual" else f"  ⚠️ {claim.evidence_kind}"
        print(f"  {index}. 「{claim_display_value(claim)}」{marker}", file=out)
        for side in sides:
            print(
                f"       {side.locator.document_id} {side.locator.pointer}"
                f"  原话：{_one_line(side.raw_text)}",
                file=out,
            )


def _valid_choices(state: Any) -> list[str]:
    """The values an adjudicator may choose: what a source actually said."""
    seen: list[str] = []
    for claim in state.claims:
        value = claim_display_value(claim)
        if value not in seen:
            seen.append(value)
    return sorted(seen)


def _one_line(text: str) -> str:
    return str(text or "").replace("\n", " / ")


def cmd_profiles(args: argparse.Namespace | None = None) -> int:
    print(json.dumps(profile_catalog(), ensure_ascii=False, indent=2))
    print("\n适配器:")
    print(json.dumps(describe_adapters(), ensure_ascii=False, indent=2))
    return 0


ERROR_HINTS: dict[str, str] = {
    "input_error": "最常见原因：来源类型未声明（用 path:kind）或缺少字段表（--profile-file / --profile）。",
    "parse_error": "输入有坏行，已跳过；明细见结构化日志。",
    "schema_validation_error": "来源里的值不符合字段类型，已拒收。",
}


def cmd_inspect(args: argparse.Namespace) -> int:
    """Assess a candidate source. Reads only; writes nothing."""
    from .merge import build_records
    from .pipeline import _load_inputs
    from .wiring import build_wiring_report, subject_signature

    settings = settings_from_args(args)
    settings.max_records = getattr(args, "max_records", None)
    outputs, inputs_meta, errors, _, _ = _load_inputs(settings)
    records, _ = build_records(outputs, settings)
    report = build_wiring_report(outputs, records, inputs_meta, errors)
    report["subject_signature"] = subject_signature(records)

    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if errors and not records else 0

    print(f"接线自检：{report['verdict']}")
    print(f"  记录 {report['records']} 条 / 文档 {report['documents']} 份 / 来源 {report['providers']}")
    print("  字段覆盖率：")
    for name in FIELD_NAMES:
        item = report["field_coverage"][name]
        print(
            f"    - {item['field_label']}({name}) {item['coverage_rate']:.0%}"
            f"  可用 {item['usable']} / 冲突 {item['conflict']} / 仅宣传 {item['promotional_only']}"
        )
    if report["unmapped_source_keys"]["total_keys"]:
        top = report["unmapped_source_keys"]["top"][:8]
        print(f"  未映射源字段 {report['unmapped_source_keys']['total_keys']} 个（待补进字段表）：")
        for item in top:
            print(f"    · {item['key']} × {item['records']}")
    if report.get("unmapped_that_look_like_fields"):
        print("  ⚠ 未映射但形似某字段的列（请确认是有意排除还是待补）：")
        for item in report["unmapped_that_look_like_fields"][:8]:
            print(f"    · {item['column']} → 形似 {'/'.join(item['looks_like'])} × {item['records']}")
    if report.get("declared_semantics"):
        print("  已声明口径：")
        for item in report["declared_semantics"][:6]:
            print(f"    · {item['profile']} / {item['field']}：{item['semantics']}")
    if report["poster_template_signatures"]:
        print("  海报模板族：", report["poster_template_signatures"])
    if report["errors"]:
        print("  错误：", report["errors"])
        print(f"  {ERROR_HINTS.get(max(report['errors']), '详见结构化日志中的 detail 字段')}")
    print("  未写入任何文件。")
    return 1 if errors and not records else 0


COMMANDS = {
    "ingest": cmd_ingest,
    "report": cmd_report,
    "validate": cmd_validate,
    "field": cmd_field,
    "review": cmd_review,
    "export": cmd_export,
    "inspect": cmd_inspect,
    "profiles": cmd_profiles,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(args, "verbose", False))
    handler = COMMANDS[args.command]
    try:
        return handler(args)
    except InputError as exc:
        print(f"输入错误: {exc}", file=sys.stderr)
        return 2
    except FactPackageError as exc:
        print(f"{exc.category}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

#!/usr/bin/env python3
"""Convert OCR JSONL output to a Feishu-friendly CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = [
    "文件名",
    "文件路径",
    "OCR引擎",
    "OCR原文",
    "平均置信度",
    "是否需复核",
    "识别块数量",
    "主标题",
    "副标题",
    "核心卖点",
    "信任背书",
    "CTA",
    "目标人群",
    "用户痛点",
    "错误类型",
    "备注",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把 OCR JSONL 转成飞书多维表导入 CSV")
    parser.add_argument("--input", default="data/output/apple_vision/results.jsonl")
    parser.add_argument("--out", default="data/output/feishu/poster_ocr_feishu.csv")
    return parser.parse_args()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "y", "是"}
    return bool(value)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    out_path = Path(args.out)

    if not input_path.exists():
        raise SystemExit(f"输入文件不存在：{input_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with input_path.open("r", encoding="utf-8") as source, out_path.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()

        for line_number, line in enumerate(source, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(f"[WARN] 跳过第 {line_number} 行：JSON 解析失败：{exc}")
                continue

            file_path = item.get("file", "")
            blocks = item.get("blocks") or []
            row = {
                "文件名": Path(file_path).name,
                "文件路径": file_path,
                "OCR引擎": item.get("engine", ""),
                "OCR原文": item.get("plain_text", ""),
                "平均置信度": item.get("confidence_avg", ""),
                "是否需复核": "是" if as_bool(item.get("needs_review", False)) else "否",
                "识别块数量": len(blocks),
                "主标题": "",
                "副标题": "",
                "核心卖点": "",
                "信任背书": "",
                "CTA": "",
                "目标人群": "",
                "用户痛点": "",
                "错误类型": "",
                "备注": "",
            }
            writer.writerow(row)
            count += 1

    print(f"[OK] 已输出 {count} 行：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

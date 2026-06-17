#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/data/output"

mkdir -p \
  "$OUTPUT_DIR/apple_vision" \
  "$OUTPUT_DIR/paddleocr" \
  "$OUTPUT_DIR/plain_text" \
  "$OUTPUT_DIR/feishu"

find "$OUTPUT_DIR" -type f -delete

echo "已清理 data/output 下的输出文件；data/input 未被改动。"

#!/usr/bin/env python3
"""小红书博主图批量 OCR 执行器（PaddleOCR PP-OCRv6，本地离线）

用途：为博主图（萌萌姐 / 伴升两批）用 PP-OCRv6 生成可检索文本，
      替代传统 OCR 在中文艺术字海报上的乱码与错字问题。

设计约束（对应 Poster OCR 项目规则）：
  - 全程本地推理，不上传任何图片，不调用云 OCR / 云 LLM；
  - 不修改原图、不删除、不移动原始图片；
  - 只写输出目录，不回写业务工作簿（回写是独立的、需授权的步骤）；
  - 断点续跑：结果以追加写方式落 results.jsonl，重跑自动跳过已完成条目；
  - 每条结果记录引擎版本、模型名与参数，保证可复现。

档位：批量用 --tier small，复核用 --tier medium。
用法：
  python scripts/ocr_batch_runner.py --tier small --workers 6 --out /tmp/ocr-batch --resume
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

TOOL_VERSION = "1.0.0"

DEFAULT_ROOT = Path("/Users/liujunliang/Documents/02-Area/06-事业/数字牧民/河狸陪")

BOOK_SPECS = [
    # (工作簿相对路径, 归档目录相对路径, OCR 文本列名)
    ("01_营销获客/02_内容生产/美研申请/小红书/萌萌姐留学逆袭/"
     "【社媒助手】博主「萌萌姐留学逆袭」的笔记数据-20261016-2235.xlsx",
     "01_营销获客/01_Inbox_待归位/20261016_萌萌姐留学逆袭图片归档", "OCR识别文本"),
    ("01_营销获客/02_内容生产/美本申请/小红书/伴升留学/"
     "【社媒助手】博主「伴升留学」的笔记数据-20261017-0835.xlsx",
     "01_营销获客/01_Inbox_待归位/伴升留学_笔记图片_20261017", "OCR文本"),
]

TIER_MODELS = {
    "tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec"),
    "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
    "medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
}

# ---------------------------------------------------------------- 质检口径

ZH = re.compile(r"[\u4e00-\u9fff]")
EN_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.@\-]{2,}")

# 关键事实实体：出现即需人工读图确认（OCR 只作线索，不作事实）
FACT_PATTERNS = {
    "院校": re.compile(r"(大学|学院|UNIV|Universit|\bUCLA\b|\bUMich\b|\bCMU\b|\bNYU\b|\bUSC\b|\bUCSB\b|\bDuke\b|\bYale\b|\bBerkeley\b)"),
    "金额": re.compile(r"[$￥€£]\s?\d[\d,]{2,}"),
    "分数": re.compile(r"(GPA|SAT|ACT|TOEFL|雅思|托福)\s*[:：]?\s*\d"),
    "日期": re.compile(r"(20\d{2}\s*年|20\d{2}[-/]\d{1,2}|\d{1,2}\s*月)"),
    "承诺": re.compile(r"(保录|保offer|必录|保过|包过|100%|全额奖学金)"),
}

_OCR = None
_TIER = None
_ENV: dict = {}


def get_ocr(tier: str):
    """每个 worker 进程内只建一次实例。"""
    global _OCR, _TIER
    if _OCR is None or _TIER != tier:
        from paddleocr import PaddleOCR
        det, rec = TIER_MODELS[tier]
        _OCR = PaddleOCR(text_detection_model_name=det, text_recognition_model_name=rec)
        _TIER = tier
        try:
            import paddleocr
            _ENV["paddleocr_version"] = paddleocr.__version__
        except Exception:
            _ENV["paddleocr_version"] = "unknown"
        _ENV["model_det"], _ENV["model_rec"] = det, rec
    return _OCR


# ---------------------------------------------------------------- 数据加载


def resolve_root(explicit: str | None) -> Path:
    cands = [Path(explicit)] if explicit else []
    cands += [DEFAULT_ROOT, DEFAULT_ROOT / "河狸陪", Path("/Users/liujunliang/河狸陪")]
    for c in cands:
        if (c / "01_营销获客").exists():
            return c
    raise SystemExit("未能定位主库根目录，请用 --root 指定")


def load_tasks_from_manifest(manifest: Path) -> list[dict]:
    """从金标准清单直接取任务（用于跑基线初标）。"""
    tasks: list[dict] = []
    with manifest.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            p = row.get("图片绝对路径")
            if not p or not Path(p).exists():
                continue
            tasks.append({
                "blogger": row.get("博主", ""), "note_id": row.get("笔记ID", ""),
                "title": row.get("笔记标题", ""), "fname": row.get("图片文件名", ""),
                "path": p, "baseline_engine": row.get("现役引擎", ""),
                "baseline_text": row.get("现役文本_参照", ""),
            })
    return tasks


def load_tasks(root: Path) -> list[dict]:
    try:
        import openpyxl
    except ModuleNotFoundError:
        raise SystemExit("[ERROR] 缺少 openpyxl，请用 .venv_paddleocr/bin/python 运行本脚本")
    tasks: list[dict] = []
    for xlsx_rel, arc_rel, textcol in BOOK_SPECS:
        xlsx, arc = root / xlsx_rel, root / arc_rel
        if not xlsx.exists():
            print(f"[WARN] 工作簿缺失，跳过：{xlsx_rel}", file=sys.stderr)
            continue
        if not arc.exists():
            print(f"[WARN] 归档目录缺失，跳过：{arc_rel}", file=sys.stderr)
            continue
        note_dirs: dict[str, Path] = {}
        for d in arc.iterdir():
            if d.is_dir():
                note_dirs.setdefault(d.name.split("_")[0], d)
        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
        ws = wb["图片OCR识别"]
        it = ws.iter_rows(values_only=True)
        head = list(next(it))
        idx = {h: i for i, h in enumerate(head)}
        blogger = "萌萌姐" if "萌萌姐" in xlsx.name else "伴升"
        for r in it:
            fname = r[idx["图片文件名"]]
            if not fname:
                continue
            note_id = r[idx["笔记ID"]]
            d = note_dirs.get(note_id)
            if not d:
                continue
            p = d / str(fname)
            if not p.exists():
                continue
            tasks.append({
                "blogger": blogger, "note_id": note_id, "title": r[idx["笔记标题"]] or "",
                "fname": str(fname), "path": str(p),
                "baseline_engine": "Tesseract 5.5.3 | chi_sim+eng",
                "baseline_text": (r[idx[textcol]] or ""),
            })
        wb.close()
    return tasks


# ---------------------------------------------------------------- 识别


def slice_long_image(path: Path, tile_h: int, overlap: int, work_dir: Path) -> list[Path]:
    from PIL import Image
    work_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(path)
    w, h = im.size
    out, y, i = [], 0, 0
    while y < h:
        y2 = min(h, y + tile_h)
        p = work_dir / f"{path.stem}__tile{i}.png"
        im.crop((0, y, w, y2)).save(p)
        out.append(p)
        if y2 >= h:
            break
        y = y2 - overlap
        i += 1
    return out


def tile_dir_for(path: Path, out_root: Path) -> Path:
    """切片目录按整路径哈希唯一化。

    不同笔记下常有同名文件（如多个 001.jpg），只用 stem 会让并发进程写同一个
    目录、互相覆盖，导致 'Image read Error'。这里加路径哈希避免冲突。
    """
    digest = hashlib.md5(str(path).encode("utf-8")).hexdigest()[:10]
    return out_root / "_tiles" / f"{path.stem}_{digest}"


def _predict(ocr, path: Path) -> tuple[list[str], list[float]]:
    texts: list[str] = []
    scores: list[float] = []
    for item in ocr.predict(str(path)):
        d = item.json if hasattr(item, "json") else {}
        payload = d.get("res", d) if isinstance(d, dict) else {}
        texts.extend(payload.get("rec_texts") or [])
        scores.extend(float(s) for s in (payload.get("rec_scores") or []))
    return texts, scores


def ocr_one(task: dict, tier: str, args) -> dict:
    ocr = get_ocr(tier)
    path = Path(task["path"])
    params = {"slice_height": args.slice_height, "slice_overlap": args.slice_overlap,
              "review_threshold": args.review_threshold}
    t0 = time.time()
    texts: list[str] = []
    scores: list[float] = []
    mode = "full"
    tiles: list[str] = []
    size = None
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        size = f"{w}x{h}"
        if h > args.slice_height:
            mode = "sliced"
            td = tile_dir_for(path, Path(args.out))
            try:
                for tp in slice_long_image(path, args.slice_height, args.slice_overlap, td):
                    t_texts, t_scores = _predict(ocr, tp)
                    texts.extend(t_texts)
                    scores.extend(t_scores)
                    tiles.append(str(tp))
            finally:
                shutil.rmtree(td, ignore_errors=True)
                tiles = []
        else:
            t_texts, t_scores = _predict(ocr, path)
            texts.extend(t_texts)
            scores.extend(t_scores)
    except Exception as exc:  # 单张失败不中断整批
        return {**task, "engine": f"PP-OCRv6_{tier}", "tier": tier, "mode": mode,
                "elapsed": round(time.time() - t0, 2), "error": f"{type(exc).__name__}: {exc}",
                "text": "", "zh_chars": 0, "en_words": 0, "conf_avg": 0.0, "blocks": 0,
                "needs_review": True, "review_reasons": ["运行异常"], "fact_fields": [],
                "image_size": size, "tiles": tiles,
                "paddleocr_version": _ENV.get("paddleocr_version", "unknown"),
                "model_det": _ENV.get("model_det"), "model_rec": _ENV.get("model_rec"),
                "params": params, "tool_version": TOOL_VERSION}

    el = round(time.time() - t0, 2)
    text = "\n".join(t for t in texts if t)
    conf_avg = round(sum(scores) / len(scores), 4) if scores else 0.0
    zh = len(ZH.findall(text))
    en = len(EN_WORD.findall(text))

    reasons = []
    if zh == 0:
        reasons.append("零中文输出")
    elif zh < 20:
        reasons.append("中文极少(<20)")
    if conf_avg < args.review_threshold:
        reasons.append(f"置信度低({conf_avg:.2f})")
    if mode == "sliced":
        reasons.append("超长图切片")
    fields = [k for k, pat in FACT_PATTERNS.items() if pat.search(text)]

    return {**task, "engine": f"PP-OCRv6_{tier}", "tier": tier, "mode": mode,
            "elapsed": el, "error": "", "text": text, "zh_chars": zh, "en_words": en,
            "conf_avg": conf_avg, "blocks": len(texts), "needs_review": bool(reasons),
            "review_reasons": reasons, "fact_fields": fields,
            "image_size": size, "tiles": tiles,
            "paddleocr_version": _ENV.get("paddleocr_version", "unknown"),
            "model_det": _ENV.get("model_det"), "model_rec": _ENV.get("model_rec"),
            "params": params, "tool_version": TOOL_VERSION}


def _init_worker(tier: str):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    get_ocr(tier)


# ---------------------------------------------------------------- 输出


def _write_reports(out: Path, jsonl: Path):
    rows = []
    with jsonl.open(encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rev = [r for r in rows if r.get("needs_review")]
    with (out / "review_queue.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["博主", "笔记ID", "笔记标题", "图片文件名", "档位", "模式", "中文字数", "置信度",
                    "复核原因", "命中关键实体", "图片路径"])
        for r in rev:
            w.writerow([r["blogger"], r["note_id"], r["title"], r["fname"], r["tier"], r["mode"],
                        r["zh_chars"], r["conf_avg"], "|".join(r["review_reasons"]),
                        "|".join(r["fact_fields"]), r["path"]])
    summary = {
        "total": len(rows),
        "review_needed": len(rev),
        "zero_chinese": sum(1 for r in rows if r.get("zh_chars") == 0),
        "errors": sum(1 for r in rows if r.get("error")),
        "sliced": sum(1 for r in rows if r.get("mode") == "sliced"),
        "avg_elapsed": round(sum(r.get("elapsed", 0) for r in rows) / len(rows), 2) if rows else 0,
        "tier": rows[0]["tier"] if rows else None,
        "paddleocr_version": rows[0].get("paddleocr_version") if rows else None,
        "model_det": rows[0].get("model_det") if rows else None,
        "model_rec": rows[0].get("model_rec") if rows else None,
        "tool_version": TOOL_VERSION,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[report] {summary}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="小红书博主图批量 OCR（PP-OCRv6，本地离线）")
    ap.add_argument("--root", default=None, help="主库根目录，默认自动探测")
    ap.add_argument("--manifest", default=None, help="改从金标准清单取任务（跑基线初标用）")
    ap.add_argument("--tier", default="small", choices=list(TIER_MODELS))
    ap.add_argument("--out", required=True, help="输出目录（建议放在仓库之外）")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="仅处理前 N 张（调试用）")
    ap.add_argument("--resume", action="store_true", help="跳过 results.jsonl 中已完成的条目")
    ap.add_argument("--review-threshold", type=float, default=0.70)
    ap.add_argument("--slice-height", type=int, default=2200, help="超过该高度按长图切片")
    ap.add_argument("--slice-overlap", type=int, default=200)
    args = ap.parse_args()

    root = resolve_root(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jsonl = out / "results.jsonl"

    if args.manifest:
        tasks = load_tasks_from_manifest(Path(args.manifest))
        print(f"[plan] 清单模式 {args.manifest} / 档位 {args.tier} / 可处理图片 {len(tasks)} 张", flush=True)
    else:
        root = resolve_root(args.root)
        tasks = load_tasks(root)
        print(f"[plan] 根目录 {root} / 档位 {args.tier} / 可处理图片 {len(tasks)} 张", flush=True)

    done: set[tuple] = set()
    if args.resume and jsonl.exists():
        with jsonl.open(encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                done.add((r["blogger"], r["note_id"], r["fname"]))
        print(f"[resume] 已完成 {len(done)} 张，将跳过", flush=True)

    todo = [t for t in tasks if (t["blogger"], t["note_id"], t["fname"]) not in done]
    remaining = len(todo)
    if args.limit:
        todo = todo[:args.limit]
    print(f"[run] 剩余未处理 {remaining} 张，本次处理 {len(todo)} 张，worker {args.workers}", flush=True)

    t_start = time.time()
    ok = fail = 0
    with jsonl.open("a", encoding="utf-8") as jf:
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                                 initargs=(args.tier,)) as ex:
            futs = {ex.submit(ocr_one, t, args.tier, args): t for t in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                jf.write(json.dumps(r, ensure_ascii=False) + "\n")
                jf.flush()
                if r.get("error"):
                    fail += 1
                else:
                    ok += 1
                if i % 20 == 0 or i == len(todo):
                    rate = (time.time() - t_start) / i
                    eta = rate * (len(todo) - i) / 60
                    print(f"[{i}/{len(todo)}] 成功{ok} 失败{fail} | {rate:.1f}s/张 | 剩余约 {eta:.0f} 分钟", flush=True)

    _write_reports(out, jsonl)
    print(f"[done] 用时 {(time.time()-t_start)/60:.1f} 分钟 -> {out}", flush=True)


if __name__ == "__main__":
    main()

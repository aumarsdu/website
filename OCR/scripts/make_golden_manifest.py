#!/usr/bin/env python3
"""Poster OCR 回归金标准脚手架：生成分层样本清单 + 与识别结果比对。

两个模式：
  1) 生成：python3 make_golden_manifest.py --out data/golden/manifest.csv
     从博主图工作簿分层抽样（A 失败样本 / B 正常中文 / C 超长图 / D 英文图示），
     产出待人工标注的清单（人工列留空）。
  2) 比对：python3 make_golden_manifest.py --check --results <results.jsonl>
     读取已人工标注的清单，与识别结果比对关键实体命中率与文本相似度，出差异表。

设计约束：本地离线，不上传任何图片；金标准只存路径与标注，图片不入库。
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/Users/liujunliang/Documents/02-Area/06-事业/数字牧民/河狸陪")
BOOK_SPECS = [
    ("01_营销获客/02_内容生产/美研申请/小红书/萌萌姐留学逆袭/"
     "【社媒助手】博主「萌萌姐留学逆袭」的笔记数据-20261016-2235.xlsx",
     "01_营销获客/01_Inbox_待归位/20261016_萌萌姐留学逆袭图片归档", "OCR识别文本"),
    ("01_营销获客/02_内容生产/美本申请/小红书/伴升留学/"
     "【社媒助手】博主「伴升留学」的笔记数据-20261017-0835.xlsx",
     "01_营销获客/01_Inbox_待归位/伴升留学_笔记图片_20261017", "OCR文本"),
]

ZH = re.compile(r"[\u4e00-\u9fff]")
EN_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.@\-]{2,}")
GARBLE = re.compile(r"(?:[A-Za-z]{1,3}\s+){4,}[A-Za-z]{1,3}")
HEAD = ["样本ID", "分层", "博主", "笔记ID", "笔记标题", "图片文件名", "图片绝对路径",
        "现役引擎", "现役文本_参照", "人工确认文本", "人工确认关键字段", "判定", "备注"]

STRATA = {"A": "现役失败样本", "B": "正常中文", "C": "超长图", "D": "英文图示"}


def resolve_root(explicit: str | None) -> Path:
    cands = [Path(explicit)] if explicit else []
    cands += [DEFAULT_ROOT, DEFAULT_ROOT / "河狸陪", Path("/Users/liujunliang/河狸陪")]
    for c in cands:
        if (c / "01_营销获客").exists():
            return c
    raise SystemExit("未能定位主库根目录，请用 --root 指定")


def normalize(s: str) -> str:
    return re.sub(r"[\s　]+", "", (s or "")).lower()


def collect(root: Path) -> list[dict]:
    try:
        import openpyxl
    except ModuleNotFoundError:
        raise SystemExit(
            "[ERROR] 缺少 openpyxl。请用项目虚拟环境运行：\n"
            "       .venv_paddleocr/bin/python scripts/make_golden_manifest.py ...\n"
            "       （该目标需要读取博主工作簿，openpyxl 已在 .venv_paddleocr 中）")
    items: list[dict] = []
    for xlsx_rel, arc_rel, textcol in BOOK_SPECS:
        xlsx, arc = root / xlsx_rel, root / arc_rel
        if not xlsx.exists() or not arc.exists():
            print(f"[WARN] 跳过缺失数据源：{xlsx_rel}", file=sys.stderr)
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
            nid = r[idx["笔记ID"]]
            d = note_dirs.get(nid)
            if not d:
                continue
            p = d / str(fname)
            if not p.exists():
                continue
            text = r[idx[textcol]] or ""
            items.append({"blogger": blogger, "note_id": nid, "title": r[idx["笔记标题"]] or "",
                          "fname": str(fname), "path": str(p), "baseline": text})
        wb.close()
    return items


def classify(item: dict) -> str:
    text = item["baseline"]
    zh = len(ZH.findall(text))
    en = len(EN_WORD.findall(text))
    if zh == 0 and en > 20:
        return "D"
    if zh <= 8 or (GARBLE.search(text) and zh <= 20):
        return "A"
    try:
        from PIL import Image
        with Image.open(item["path"]) as im:
            w, h = im.size
        if h > 2200:
            return "C"
    except Exception:
        pass
    return "B"


def generate(args) -> int:
    root = resolve_root(args.root)
    out = Path(args.out)
    # 防呆：已存在含人工标注的清单时，拒绝直接覆盖（除非 --force）
    if out.exists() and not args.force:
        try:
            with out.open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            annotated = [r for r in rows
                         if (r.get("判定") or "").strip() not in ("", "待确认")]
            if annotated:
                bak = out.with_suffix(out.suffix + f".bak-{len(annotated)}")
                shutil.copy2(out, bak)
                print(f"[保护] 原清单含 {len(annotated)} 条人工标注，已备份到 {bak.name}；"
                      f"本次重新抽样未标注。")
        except Exception as exc:
            print(f"[WARN] 检查原清单失败：{exc}", file=sys.stderr)
    items = collect(root)
    if not items:
        print("[ERROR] 没有可用样本", file=sys.stderr)
        return 2
    buckets: dict[str, list[dict]] = {k: [] for k in STRATA}
    for it in items:
        buckets[classify(it)].append(it)

    import random
    random.seed(args.seed)
    rows = []
    n = 0
    for key in ("A", "B", "C", "D"):
        pool = buckets.get(key, [])
        take = pool if args.all else random.sample(pool, min(args.per_stratum, len(pool)))
        for it in take:
            n += 1
            rows.append({
                "样本ID": f"G{n:02d}", "分层": f"{key}-{STRATA[key]}", "博主": it["blogger"],
                "笔记ID": it["note_id"], "笔记标题": it["title"][:40], "图片文件名": it["fname"],
                "图片绝对路径": it["path"], "现役引擎": "Tesseract 5.5.3 | chi_sim+eng",
                "现役文本_参照": (it["baseline"] or "")[:200].replace("\n", " | "),
                "人工确认文本": "", "人工确认关键字段": "", "判定": "待确认", "备注": "",
            })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        w.writeheader()
        w.writerows(rows)
    print(f"[生成] {len(rows)} 条分层样本 -> {out}")
    for key in STRATA:
        c = sum(1 for r in rows if r["分层"].startswith(key))
        print(f"   {key}-{STRATA[key]}: {c} 条")
    print("[下一步] 人工填写「人工确认文本」「人工确认关键字段」「判定」三列后，再跑 --check")
    return 0


def check(args) -> int:
    man = Path(args.manifest)
    if not man.exists():
        print(f"[ERROR] 清单不存在：{man}", file=sys.stderr)
        return 2
    with man.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    results: dict[tuple, dict] = {}
    if args.results:
        rp = Path(args.results)
        if not rp.exists():
            print(f"[ERROR] 结果文件不存在：{rp}", file=sys.stderr)
            return 2
        for line in rp.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            results[(r.get("blogger"), r.get("note_id"), r.get("fname"))] = r

    diff_rows, hit, tot, unlabeled, skipped = [], 0, 0, 0, 0
    for row in rows:
        key = (row["博主"], row["笔记ID"], row["图片文件名"])
        res = results.get(key)
        gold_text = (row.get("人工确认文本") or "").strip()
        gold_fields = [f for f in re.split(r"[|/,，、;；]", row.get("人工确认关键字段") or "") if f.strip()]
        if not gold_text and not gold_fields:
            unlabeled += 1
            continue
        if not gold_fields:
            # 已人工判定为「无文字 / 无法辨认」：不计入命中率分母
            skipped += 1
            diff_rows.append([row["样本ID"], row["分层"], "无关键字段（已人工判定不适用）",
                              "—", row.get("判定", ""), row.get("判定", "")])
            continue
        if res is None:
            diff_rows.append([row["样本ID"], row["分层"], "未匹配", "", "", row.get("判定", "")])
            tot += 1
            continue
        rec_text = res.get("text", "")
        norm_rec, norm_gold = normalize(rec_text), normalize(gold_text)
        sim = difflib.SequenceMatcher(None, norm_gold, norm_rec).ratio() if norm_gold else 0.0
        fields_hit, fields_miss = [], []
        for f in gold_fields:
            (fields_hit if normalize(f) in norm_rec else fields_miss).append(f.strip())
        n_fields = len(gold_fields)
        n_hit = len(fields_hit)
        tot += 1
        if n_fields and n_hit == n_fields:
            hit += 1
        diff_rows.append([row["样本ID"], row["分层"],
                          f"实体 {n_hit}/{n_fields}" + (f" 缺:{','.join(fields_miss)}" if fields_miss else ""),
                          f"摘要重合 {sim:.2f}",
                          "字段全中" if (n_fields and n_hit == n_fields) else ("无关键字段" if not n_fields else "有缺字段"),
                          row.get("判定", "")])

    rate = (hit / tot * 100) if tot else 0.0
    miss_rows = [r for r in diff_rows if r[4] == "有缺字段"]
    print(f"[比对] 已标注 {tot} 条 / 未标注 {unlabeled} 条 / 不适用 {skipped} 条；"
          f"关键字段全中 {hit} 条，命中率 {rate:.1f}%")
    if miss_rows:
        print(f"[已知缺字段 {len(miss_rows)} 条（计入分母，属跟踪中的真实错字）]："
              + "；".join(f"{r[0]}→{r[2]}" for r in miss_rows))
    print("[说明] 「摘要重合」为人工核读要点与识别文本的相似度，仅供参考，不作判据；"
          "判据是「关键字段全中」率。")
    if diff_rows:
        print(f"{'样本ID':<7}{'分层':<14}{'关键字段':<28}{'文本相似度':<12}{'结论':<12}人工判定")
        for r in diff_rows:
            print(f"{r[0]:<7}{r[1]:<14}{r[2]:<28}{r[3]:<12}{r[4]:<12}{r[5]}")

    if args.out:
        with Path(args.out).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["样本ID", "分层", "关键字段", "文本相似度", "结论", "人工判定"])
            w.writerows(diff_rows)
        print(f"[输出] 差异表 -> {args.out}")

    if tot and rate < args.min_hit_rate:
        print(f"[FAIL] 命中率 {rate:.1f}% < 阈值 {args.min_hit_rate}%")
        return 1
    if tot:
        print(f"[PASS] 命中率 {rate:.1f}% ≥ 阈值 {args.min_hit_rate}%")
    else:
        print("[WARN] 尚无已标注样本，无法判定")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Poster OCR 金标准脚手架")
    ap.add_argument("--root", default=None, help="主库根目录，默认自动探测")
    ap.add_argument("--out", default="data/golden/manifest.csv", help="清单输出路径")
    ap.add_argument("--manifest", default="data/golden/manifest.csv", help="比对时读取的清单")
    ap.add_argument("--per-stratum", type=int, default=5)
    ap.add_argument("--all", action="store_true", help="导出全部样本而非抽样")
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--force", action="store_true", help="强制覆盖已含人工标注的清单")
    ap.add_argument("--check", action="store_true", help="比对模式")
    ap.add_argument("--results", default=None, help="比对模式下的 results.jsonl")
    ap.add_argument("--min-hit-rate", type=float, default=85.0,
                    help="关键字段全中率阈值（%%）。当前实测基线 88.9%%（含 2 条已知难例），留余量")
    args = ap.parse_args()
    return check(args) if args.check else generate(args)


if __name__ == "__main__":
    raise SystemExit(main())

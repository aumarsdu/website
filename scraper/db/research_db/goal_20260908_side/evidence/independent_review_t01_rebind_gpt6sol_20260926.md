# T01-R1 盐趣冻结样本受控重绑定独立复核

复核日期：2026-09-26  
复核者：gpt-6-sol via codex-cli  
结论：**PASS，仅针对本次 T01-R1 `yanqu_ocr` 冻结样本的位置重绑定。**

## 范围与判定

我在本机只读 `pilot_manifest.json`、`source_registry.json`、合集 CSV、20 张原图及保留 zip，独立计算哈希并逐行核验。`pilot_manifest.json` 中 `yanqu_ocr` 恰有 20 个 `csv_data_row` 引用，全部指向已不存在的 `盐趣/盐趣海报-2026年9月4日/海报文字识别_PP-OCRv6.csv`，且全部声明同一个文件 SHA-256。重绑定目标与 zip 内原路径 CSV 的实测 SHA-256 均等于冻结记录和登记值；195 个数据行及 20 个冻结位置均可复现。因此原路径的内容按字节可复现，登记的新物理位置可承接这 20 个冻结引用。

本结论不扩大到 T01 其他来源或后续语义验收。原目录仍不存在，使用方需要按登记的 `rebound_to` 解析旧引用。

## 本机命令与证据摘录

工作目录：`/Users/liujunliang/Workspace/knowledge-legacy/scraper/db/research_db/goal_20260908_side`。执行前运行 `pwd; git status --short --branch; git rev-parse --show-toplevel`；Git 根为 `/Users/liujunliang/Workspace/knowledge-legacy`，已有大量无关脏文件，本次未改动或整理。报告目标文件在写入前不存在。

哈希命令：

```bash
shasum -a 256 pilot_manifest.json source_registry.json /Users/liujunliang/Workspace/knowledge-legacy/scraper/盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv
```

实测输出：

```text
1bbf64e94b3ff02c5ef0cf798603237e63ffeb2d02e300b0fc75e43d7e3949c5  pilot_manifest.json
26a65f86b0816ff431abb1b5f7e6db5932574e357c15a16af8e66491662d2dee  source_registry.json
0ff1a345256a6c40f5e369fbce392d75f37ff60843ec2cfa1a3263c4e34c6018  /Users/liujunliang/Workspace/knowledge-legacy/scraper/盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv
```

以下命令从冻结记录取出全部位置，流式读 CSV，对每个位置比对 `poster_path`、`status`、原图路径、原图 SHA-256 与字节数；随后只把 zip 中目标 CSV 解流到系统临时目录，计算哈希，并由 `TemporaryDirectory` 自动清理。zip 文件名按其旧式 CP437 映射还原 UTF-8 后与冻结路径比对，未修改 zip。

```bash
python3 -B - <<'PY'
import csv,hashlib,json,shutil,tempfile,zipfile
from pathlib import Path
base=Path('/Users/liujunliang/Workspace/knowledge-legacy/scraper')
m=json.loads(Path('pilot_manifest.json').read_text())
r=json.loads(Path('source_registry.json').read_text())
refs=next(s for s in m['sources'] if s['source_code']=='yanqu_ocr')['references']
images={x['csv_row']:x for x in m['yanqu_original_image_candidates']}
inp=next(s for s in r['sources'] if s['source_code']=='yanqu_ocr')['inputs'][0]
hash_file=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
with (base/inp['relative_path']).open(encoding='utf-8-sig',newline='') as f:
 rows={n:row for n,row in enumerate(csv.DictReader(f),1)}
image_ok=sum(rows[x['position']]['poster_path']==images[x['position']]['csv_poster_path']==images[x['position']]['original_relative_path'] and rows[x['position']]['status']=='ok' and (base/images[x['position']]['resolved_collection_path']).is_file() and hash_file(base/images[x['position']]['resolved_collection_path'])==images[x['position']]['image_sha256'] and (base/images[x['position']]['resolved_collection_path']).stat().st_size==images[x['position']]['image_bytes'] for x in refs)
with tempfile.TemporaryDirectory(prefix='t01-yanqu-rebind-') as tmp, zipfile.ZipFile(base/'盐趣/盐趣海报-2026年9月4日.zip') as z:
 info=next(i for i in z.infolist() if not i.filename.startswith('__MACOSX') and i.filename.encode('cp437').decode('utf-8')=='盐趣海报-2026年9月4日/海报文字识别_PP-OCRv6.csv')
 p=Path(tmp)/'original.csv'
 with z.open(info) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst)
 zip_sha=hash_file(p)
print(json.dumps({'frozen_refs':len(refs),'positions':[x['position'] for x in refs],'csv_rows':len(rows),'registry_unit_count':inp['unit_count'],'image_checks_passed':image_ok,'rebound_sha256':hash_file(base/inp['relative_path']),'zip_original_sha256':zip_sha,'registry_sha256':inp['sha256'],'old_path_exists':(base/inp['registered_path_missing']['path']).exists()},ensure_ascii=False))
PY
```

关键输出：

```json
{"frozen_refs": 20, "positions": [1, 11, 21, 31, 41, 52, 62, 72, 82, 92, 103, 113, 123, 133, 143, 154, 164, 174, 184, 195], "csv_rows": 195, "registry_unit_count": 195, "image_checks_passed": 20, "rebound_sha256": "0ff1a345256a6c40f5e369fbce392d75f37ff60843ec2cfa1a3263c4e34c6018", "zip_original_sha256": "0ff1a345256a6c40f5e369fbce392d75f37ff60843ec2cfa1a3263c4e34c6018", "registry_sha256": "0ff1a345256a6c40f5e369fbce392d75f37ff60843ec2cfa1a3263c4e34c6018", "old_path_exists": false}
```

进一步逐项检查：20 个引用的 `relative_path` 均为原 CSV，`unit` 均为 `csv_data_row`，`file_sha256` 均为完整值 `0ff1a345256a6c40f5e369fbce392d75f37ff60843ec2cfa1a3263c4e34c6018`；位置无重复，均在 195 行内。合集 CSV 实测大小 `1,638,065` 字节，等于登记 `byte_size`；195 行 `status` 均为 `ok`。20 个 `yanqu_original_image_candidates` 与冻结位置一一对应，`resolved_collection_path` 均为合集根目录拼接 CSV 的 `poster_path`，均在 `existing_candidates` 中，原图存在且哈希、大小匹配。zip 解码后的原条目大小同为 `1,638,065` 字节。

登记修正的本机核验：`registered_path_missing.path` 与冻结旧路径一致；`rebound_to` 与当前 `inputs[0].relative_path` 一致；`observed_at` 和 T06 `input_location_rebinding` amendment 的 `at` 均为 `2026-09-26T00:30:43.752151+00:00`；说明文字所述“目录已不在、zip 仍在、目标副本哈希前缀不变”与当前磁盘及上述完整哈希一致。`pilot_manifest.json` 重测 SHA-256 为冻结值 `1bbf64e94b3ff02c5ef0cf798603237e63ffeb2d02e300b0fc75e43d7e3949c5`，本次引用本身未被改写；重绑定映射记录在 `source_registry.json`。

## 证据边界

`observed_at` 是登记时间声明；本次能验证其格式、与 amendment 时间一致和当前路径状态，不能从当前文件反证目录被移走的历史时刻或原因。这不影响旧内容与新位置的字节同一性判定。复核只写入本报告；临时解流目录已由上下文管理器删除。

{"verdict": "PASS", "rebind_confirmed": true, "blocking_issues": [], "non_blocking_notes": ["registered_path_missing 的历史时间和目录移走原因仅为登记声明；本次独立核验了当前缺失状态、登记一致性和字节同一性"], "reviewer": "gpt-6-sol via codex-cli", "date": "2026-09-26"}

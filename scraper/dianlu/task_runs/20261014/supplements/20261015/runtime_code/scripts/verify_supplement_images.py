"""Verify complete supplemental image files with bundled Pillow, offline."""
import hashlib
import json
from pathlib import Path
from PIL import Image

root = Path('/Users/liujunliang/Workspace/knowledge-legacy/scraper/dianlu/task_runs/20261014/supplements/20261015')
rows = [json.loads(line) for line in (root/'data/raw/resource_attempts.jsonl').read_text().splitlines()]
rows = list({x['url']:x for x in rows}.values())
results = []
for row in rows:
    if not row.get('local_path'):
        continue
    p = root/row['local_path']
    result = {'url':row['url'],'local_path':row['local_path']}
    assert p.is_file() and p.stat().st_size == row['size_bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']
    if (row.get('content_type') or '').startswith('image/') and 'svg' not in row['content_type']:
        with Image.open(p) as im:
            result.update(format=im.format, dimensions=im.size)
            im.verify()
        with Image.open(p) as im:
            im.load()
        result['full_image_decode']='passed'
    results.append(result)
(root/'reports/image_validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps({'files_verified':len(results),'results':results},ensure_ascii=False))

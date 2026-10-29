"""Reuse prior files only when today's attachment metadata names the same URL."""
import hashlib
import json
import shutil
from pathlib import Path

from sou_crawler.pbl_crawler import _load_attachment_metadata
from sou_crawler.utils import file_extension_from_url, stable_hash


def main():
    root = Path('/Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP')
    run = root / 'output_pbl_incremental_20261013_repaired'
    cache = run / 'assets/_download_cache'
    cache.mkdir(parents=True, exist_ok=True)
    metadata = _load_attachment_metadata(run / 'raw/pbl_attachment_metadata.jsonl')
    projects = [json.loads(line) for line in (run / 'processed/projects.jsonl').open()
                if line.strip()]
    needed_ids = {str(asset['attachment_id']) for project in projects
                  for asset in project.get('assets', []) if asset.get('attachment_id')}
    direct_urls = {asset['url'] for project in projects
                   for asset in project.get('direct_assets', []) if asset.get('url')}
    report_path = run / 'reports/history_cache_reuse.json'
    reused = json.loads(report_path.read_text()) if report_path.exists() else []
    for manifest in sorted(root.glob('output_pbl*/processed/asset_manifest.jsonl')):
        if manifest.is_relative_to(run):
            continue
        for line in manifest.open():
            if not line.strip():
                continue
            item = json.loads(line)
            source = Path(item.get('file') or '')
            # Historical manifests may use paths relative to the HIREP directory.
            if not source.is_absolute():
                source = root / source
            source = source.resolve()
            allowed_assets = (manifest.parent.parent / 'assets').resolve()
            if not source.is_relative_to(allowed_assets) or not source.is_file():
                continue
            url = item.get('source_url')
            asset_id = str(item.get('attachment_id') or '')
            if asset_id in needed_ids and metadata.get(asset_id, {}).get('url') == url:
                meta = metadata[asset_id]
                target = cache / (asset_id + file_extension_from_url(
                    url, '.' + (meta.get('ext') or 'bin')))
            elif url in direct_urls:
                target = cache / (stable_hash(url) + file_extension_from_url(url))
            else:
                continue
            if not target.resolve().is_relative_to(cache.resolve()) or target.exists():
                continue
            if source.stat().st_size == 0:
                continue
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source, target)
            assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
            reused.append({'source': str(source), 'cache': str(target),
                           'source_url': url, 'bytes': target.stat().st_size,
                           'sha256': digest})
    report_path.write_text(json.dumps(reused, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'verified_reused_cache_files': len(reused)}))


if __name__ == '__main__':
    main()

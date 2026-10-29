"""Record the additive execution's exact sources and local alias candidates."""
import hashlib
import json
from pathlib import Path
import shutil

repo=Path('/Users/liujunliang/Workspace/knowledge-legacy/scraper/dianlu')
base=repo/'task_runs/20261014'
root=base/'supplements/20261015'
runtime=root/'runtime_code'
runtime.mkdir(exist_ok=True)
names=['dianedu_archiver/supplement.py','dianedu_archiver/supplement_articles.py',
       'dianedu_archiver/finalize_supplement.py','dianedu_archiver/public_transport.py',
       'dianedu_archiver/robots_policy.py','dianedu_archiver/referenced_archive.py',
       'scripts/verify_supplement_images.py','scripts/supplement_research_index.py',
       'scripts/supplement_provenance.py']
hashes=[]
for name in names:
    dst=runtime/name
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(repo/name,dst)
    hashes.append(f'{hashlib.sha256(dst.read_bytes()).hexdigest()}  {name}\n')
(runtime/'runtime.sha256').write_text(''.join(hashes))
for initial in [runtime/'initial_supplement.py',runtime/'initial_supplement_articles.py',runtime/'network_supplement_articles.py']:
    if initial.is_file():
        with (runtime/'runtime.sha256').open('a') as f:
            f.write(f'{hashlib.sha256(initial.read_bytes()).hexdigest()}  {initial.name}\n')
with (base/'reports/gap_investigation_20261015/resource_triage.csv').open(encoding='utf-8-sig') as f:
    import csv
    rows=list(csv.DictReader(f))
aliases=[]
manifest=json.loads((base/'data/processed/referenced_manifest.json').read_text())
lookup={x['url']:x for x in manifest}
for row in rows:
    if not row['saved_same_id_candidates']:
        continue
    candidates=json.loads(row['saved_same_id_candidates'])
    for c in candidates:
        rec=lookup[c['url']]
        p=base/c['local_path']
        assert p.stat().st_size==rec['size_bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256']
        aliases.append({'original_restricted_url':row['url'],'source_url':row['source_url'],
            'public_url':c['url'],'local_path':c['local_path'],'size_bytes':c['size_bytes'],
            'sha256':rec['sha256'],'same_file_id':True,'original_host_not_requested':True,
            'identity_status':'same_id_public_version_available_original_bytes_unverified'})
(root/'reports/local_public_alias_candidates.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2))
prior=Path('/private/tmp/dianlu_recheck_result.json')
if prior.is_file():
    shutil.copyfile(prior,root/'reports/original_full_recheck.json')
print(json.dumps({'source_files_snapshotted':len(names),'local_same_id_candidates_verified':len(aliases),'original_recheck_copied':prior.is_file()}))
import sqlite3
conn=sqlite3.connect(f'file:{base}/data/processed/dianedu.sqlite?mode=ro',uri=True)
dbrows=[json.loads(x[0]) for x in conn.execute('SELECT data_json FROM assets')]
conn.close()
dbmap={x['url']:x for x in dbrows}
different=[u for u in dbmap.keys() & lookup.keys() if dbmap[u]!=lookup[u]]
detail={'original_asset_db_rows':len(dbrows),'manifest_rows':len(lookup),
        'missing_db_urls':sorted(lookup.keys()-dbmap.keys()),'extra_db_urls':sorted(dbmap.keys()-lookup.keys()),
        'differing_record_count':len(different),
        'differing_field_counts':dict(__import__('collections').Counter(k for u in different for k in dbmap[u].keys()|lookup[u].keys() if dbmap[u].get(k)!=lookup[u].get(k)))}
(root/'reports/original_asset_db_reconciliation.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in detail.items() if not k.endswith('_urls')}))
semantic_matches=all({k:v for k,v in dbmap[u].items() if k!='error'}==lookup[u]
    and dbmap[u].get('error')==({'error_type':lookup[u]['error_type']} if lookup[u].get('error_type') else None)
    for u in lookup.keys() & dbmap.keys()) and dbmap.keys()==lookup.keys()
detail['semantic_match_after_explicit_error_serialization_normalization']=semantic_matches
detail['normalization']='DB adds error=null or error={error_type:...}; all other fields match manifest exactly'
(root/'reports/original_asset_db_reconciliation.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2))
assert semantic_matches
print(json.dumps({'semantic_match_after_explicit_error_serialization_normalization':semantic_matches}))

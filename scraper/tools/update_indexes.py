"""Prepare a scoped, reviewed index update; publish only with explicit --publish."""
import argparse
import collections
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from poster_index import common, direction

ROOT=common.SCRAPER_ROOT
BATCH=ROOT/'采集批次/20261013/海报索引更新'
FORMAL=common.OUTPUT_DIR
NAMES=('集思未来','HIREP','中科浩博')
ALIASES={'集思':'集思未来','HIREP':'HIREP','中科':'中科浩博'}


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')


def changes(before,after):
    old={x['recordId']:x for x in before};new={x['recordId']:x for x in after};out=[]
    for key in sorted(old.keys()|new.keys()):
        a,b=old.get(key),new.get(key)
        if a==b:continue
        fields=sorted(k for k in (a or {}).keys()|(b or {}).keys() if (a or {}).get(k)!=(b or {}).get(k))
        show=('title','schoolBegins','direction','projectType','format','posterPath','posterVariant','posterSha256','sourceFile')
        out.append({'recordId':key,'action':'add' if a is None else 'remove' if b is None else 'modify',
                    'changed_fields':fields,'before':{k:a.get(k) for k in show} if a else None,
                    'after':{k:b.get(k) for k in show} if b else None})
    return out


def prepare():
    acceptance=read(BATCH/'acceptance.json')
    required={'valid':True,'originals_unchanged':True,'dimensions_match':True,
              'ocr_remaining_target_blocks':0,'decodable_qr':0,'visual_reviewed':True}
    if any(acceptance.get(k)!=v for k,v in required.items()):
        raise RuntimeError('Poster acceptance has not passed')
    approved=acceptance['posters']
    if len(approved)!=103 or len({(x['supplier'],x['recordId']) for x in approved})!=103:
        raise RuntimeError('Expected 103 unique accepted poster references')
    approval={(x['supplier'],x['recordId']):x for x in approved}
    wanted={name:{} for name in NAMES}
    for row in csv.DictReader((ROOT/'采集批次/20261013/新增课题.csv').open(encoding='utf-8-sig')):
        wanted[ALIASES[row['供应商']]][row['稳定ID']]=row
    candidate=BATCH/'candidate-final';candidate.mkdir(exist_ok=True)
    preview=[];exceptions=[];receipts=[];inputs={}
    for name in NAMES:
        old_doc=read(FORMAL/f'{name}.index.json');old_report=read(FORMAL/f'{name}.report.json')
        inputs[f'{name}.index.json']=digest(FORMAL/f'{name}.index.json')
        inputs[f'{name}.report.json']=digest(FORMAL/f'{name}.report.json')
        full=read(BATCH/'candidate-before-processing'/f'{name}.index.json')['items']
        available={x['recordId']:x for x in full}
        merged={x['recordId']:x for x in old_doc['items']}
        for rid,row in wanted[name].items():
            item=available.get(rid)
            if item is None:
                if name!='集思未来' or rid!='829c8210-bbd1-11f1-b9a3-952f7ac65092':
                    raise RuntimeError(f'unexpected missing index item: {name}:{rid}')
                exceptions.append({'supplier':name,'recordId':rid,'title':row['课题名称'],
                                   'reason':'no_course_poster; thumbnail and avatar are not substitutes'})
                continue
            item=dict(item);qa=approval[(name,rid)]
            if digest(Path(item['posterPath']))!=qa['source_original_sha256']:
                raise RuntimeError('Index source differs from accepted original')
            output=Path(qa['output'])
            if not output.is_relative_to(BATCH/'processed') or digest(output)!=qa['output_sha256']:
                raise RuntimeError('Accepted output path/hash changed')
            if name=='中科浩博':
                duplicates=[k for k,v in merged.items() if v['title']==item['title'] and k!=rid]
                if len(duplicates)>1:raise RuntimeError('Ambiguous title replacement')
                for key in duplicates:
                    previous=merged.pop(key)
                    receipts.append({'supplier':name,'old_recordId':key,'new_recordId':rid,
                                     'old_path':previous['posterPath'],'new_path':str(output),
                                     'preserved_previous_processed':str(ROOT/'中科/output/repair_backups/20261013-layout-after-normalize'/Path(previous['posterPath']).relative_to(ROOT/'中科/output/site'))})
            item['posterCandidates']=list(dict.fromkeys([item['posterPath'],*item.get('posterCandidates',[])]))
            item['posterPath']=str(output);item['posterSha256']=qa['output_sha256']
            item['posterVariant']=qa['variant']
            merged[rid]=item
        items=list(merged.values());diff=changes(old_doc['items'],items)
        full_diff=changes(old_doc['items'],full)
        batch_ids=set(wanted[name])|{x['old_recordId'] for x in receipts if x['supplier']==name}
        other=[x for x in full_diff if x['recordId'] not in batch_ids]
        preview.append({'supplier':name,'old_count':len(old_doc['items']),'candidate_count':len(items),
                        'full_rebuild_count':len(full),'applied_batch_changes':diff,
                        'other_history_changes_not_published':other})
        # Existing records outside this bounded batch must remain exactly unchanged.
        for item in old_doc['items']:
            if item['recordId'] not in batch_ids and merged[item['recordId']]!=item:
                raise RuntimeError('Unrelated historical item changed')
        report=dict(old_report);missing=[rid for rid in dict.fromkeys(report.get('missing_poster_ids') or []) if rid not in merged]
        report.pop('generatedAt',None)
        legacy_keys=('records_per_file','manifest_entries','project_type_sources','project_type_pending')
        report['previous_source_metrics_snapshot']={k:report.pop(k) for k in legacy_keys if k in report}
        for exception in exceptions:
            if exception['supplier']==name and exception['recordId'] not in missing:missing.append(exception['recordId'])
        report.update({'posters_found':len(items),'with_school_begins':sum(bool(x['schoolBegins']) for x in items),
                       'school_begins_future':sum(bool(x['schoolBegins']) and x['schoolBegins']>'2026-10-13' for x in items),
                       'poster_variant_distribution':dict(collections.Counter(x['posterVariant'] for x in items)),
                       'subject_distribution':dict(collections.Counter(x['subject'] for x in items)),
                       'missing_poster_ids':missing,'format_distribution':common.format_distribution(items,today='2026-10-13'),
                       'project_type_distribution':dict(collections.Counter(x['projectType'] for x in items)),
                       **direction.summarize(items),
                       'update_scope':{'date':'2026-10-13','mode':'accepted_batch_merge_preserving_history',
                                       'accepted_posters':sum(x['supplier']==name for x in approved),
                                       'full_rebuild_candidates':len(full),'historical_changes_deferred':len(other),
                                       'acceptance_file':str(BATCH/'acceptance.json')}})
        report['previous_source_metrics_snapshot']['total_courses']=old_report.get('total_courses')
        report['total_courses']=len(items)+len(missing)
        report['total_courses_basis']='indexed stable IDs plus explicitly listed missing-poster IDs in the scoped catalog'
        if 'missing_poster_count' in report:report['missing_poster_count']=len(missing)
        common.OUTPUT_DIR=candidate
        common.write_index_and_report(name,items,report)
    inputs['direction_overrides.json']=digest(FORMAL/'direction_overrides.json')
    write(BATCH/'formal-input-hashes.json',inputs)
    write(BATCH/'index-diff.json',preview);write(BATCH/'exceptions.json',exceptions)
    write(BATCH/'zhongke-title-replacement.json',receipts)
    with (BATCH/'index-diff.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.writer(file);writer.writerow(['供应商','范围','动作','记录ID','变化字段'])
        for entry in preview:
            for key,scope in (('applied_batch_changes','本批应用'),('other_history_changes_not_published','其他历史候选暂缓')):
                for change in entry[key]:writer.writerow([entry['supplier'],scope,change['action'],change['recordId'],','.join(change['changed_fields'])])
    write(BATCH/'preview-integrity.json',{
        'acceptance_sha256':digest(BATCH/'acceptance.json'),
        'candidate_files':{f'{name}.{kind}.json':digest(candidate/f'{name}.{kind}.json')
                           for name in NAMES for kind in ('index','report')},
        'diff_sha256':digest(BATCH/'index-diff.json'),
        'overrides_sha256':inputs['direction_overrides.json']})
    print(json.dumps({'candidate_counts':{x['supplier']:x['candidate_count'] for x in preview},'exceptions':len(exceptions)},ensure_ascii=False))


def publish():
    inputs=read(BATCH/'formal-input-hashes.json')
    for name,wanted_hash in inputs.items():
        if digest(FORMAL/name)!=wanted_hash:raise RuntimeError('Formal file changed since preview; stop without overwrite')
    acceptance=read(BATCH/'acceptance.json')
    if not acceptance.get('valid') or not acceptance.get('visual_reviewed'):
        raise RuntimeError('Acceptance revoked')
    candidate=BATCH/'candidate-final';files=[f'{name}.{kind}.json' for name in NAMES for kind in ('index','report')]
    integrity=read(BATCH/'preview-integrity.json')
    if digest(BATCH/'acceptance.json')!=integrity['acceptance_sha256'] or digest(BATCH/'index-diff.json')!=integrity['diff_sha256']:
        raise RuntimeError('Acceptance or reviewed diff changed since preview')
    for name in files:
        if digest(candidate/name)!=integrity['candidate_files'][name]:
            raise RuntimeError('Candidate changed since preview')
    for poster in acceptance['posters']:
        if digest(Path(poster['source']))!=poster['source_original_sha256']:
            raise RuntimeError('Original changed since acceptance')
    for name in NAMES:
        doc=read(candidate/f'{name}.index.json');items=doc['items']
        if len({x['recordId'] for x in items})!=len(items):raise RuntimeError('Duplicate stable ID')
        for item in items:
            path=Path(item['posterPath'])
            if not path.is_file() or digest(path)!=item['posterSha256']:
                raise RuntimeError('Candidate poster missing or hash changed')
    # Media validation may take time: recheck immediately before taking the snapshot.
    for name,wanted_hash in inputs.items():
        if digest(FORMAL/name)!=wanted_hash:raise RuntimeError('Formal file changed during media validation')
    backup=FORMAL/'backups/20261013-index-posters'
    backup.mkdir(parents=True,exist_ok=False)
    for name in files+['README.md','direction_overrides.json']:
        shutil.copy2(FORMAL/name,backup/name)
    write(backup/'backup-manifest.json',{name:digest(backup/name) for name in files+['README.md','direction_overrides.json']})
    for name,wanted_hash in inputs.items():
        if digest(backup/name)!=wanted_hash or digest(FORMAL/name)!=wanted_hash:
            raise RuntimeError('Formal file changed while backing up; nothing replaced')
    # Allocate and flush every new/rollback payload before touching formal files.
    # An ENOSPC while staging therefore leaves the complete old generation intact.
    for name in files:
        for suffix,source in (('.20261013.tmp',candidate/name),('.rollback.tmp',backup/name)):
            with (FORMAL/(name+suffix)).open('xb') as output:
                output.write(source.read_bytes());output.flush();os.fsync(output.fileno())
    replaced=[]
    try:
        for name in files:
            if digest(FORMAL/name)!=inputs[name]:
                raise RuntimeError('Formal file changed immediately before replacement')
            temporary=FORMAL/(name+'.20261013.tmp')
            os.replace(temporary,FORMAL/name);replaced.append(name)
        if digest(FORMAL/'direction_overrides.json')!=inputs['direction_overrides.json']:
            raise RuntimeError('Overrides changed during publish')
        result={'valid':True,'backup':str(backup),'files':{name:digest(FORMAL/name) for name in files},
                'overrides_unchanged':True,'candidate_matches_formal':all(digest(FORMAL/name)==digest(candidate/name) for name in files)}
        if not result['candidate_matches_formal']:raise RuntimeError('Readback mismatch')
        write(BATCH/'formal-readback.json',result)
    except BaseException as failure:
        recovery_errors=[]
        for name in reversed(replaced):
            try:os.replace(FORMAL/(name+'.rollback.tmp'),FORMAL/name)
            except OSError as error:recovery_errors.append(f'{name}: {error}')
        if recovery_errors:
            raise RuntimeError('Recovery incomplete; preserved backup at '+str(backup)+'; '+ '; '.join(recovery_errors)) from failure
        raise
    print(json.dumps({'published_files':len(files),'readback_valid':True,'backup':str(backup)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    publish() if args.publish else prepare()

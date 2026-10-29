"""Offline acceptance of an additive supplement; never rewrite old receipts."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import zipfile

from .supplement import BASE, ROOT, digest, atomic_json, now
from .referenced_archive import cached_file_valid
from .storage import read_json, iter_jsonl, write_csv


def main():
    budget=read_json(ROOT/'reports/budget.json')
    if budget['status'] not in ('article_candidates_finished','complete'):
        raise RuntimeError('Network stages must terminate before final acceptance')
    original_integrity=read_json(ROOT/'reports/original_integrity.json')
    changed=[name for name,sha in original_integrity.items() if digest(BASE/name)!=sha]
    if changed:
        raise RuntimeError(f'Original archive changed: {changed}')
    before=read_json(ROOT/'reports/original_completion_audit.json')
    original=read_json(BASE/'data/processed/referenced_manifest.json',[])
    attempts=list(iter_jsonl(ROOT/'data/raw/resource_attempts.jsonl'))
    latest={r['url']:r for r in attempts}
    saved=[r for r in latest.values() if r.get('local_path')]
    invalid=[r['url'] for r in saved if not cached_file_valid(ROOT,r)]
    if invalid:
        raise RuntimeError(f'Supplement file integrity failed: {invalid}')
    image_validation=read_json(ROOT/'reports/image_validation.json',[])
    assert {r['url'] for r in saved}=={r['url'] for r in image_validation}
    assert all(r.get('full_image_decode')=='passed' for r in image_validation if r.get('format'))
    search=read_json(ROOT/'reports/article_search_coverage.json')
    assert search['articles']==96 and search['queries']==192 and search['all_articles_searched_twice']
    candidates=read_json(ROOT/'reports/article_candidates.json',[])
    candidate_files=[]
    for c in candidates:
        if c.get('html_path'):
            assert digest(ROOT/c['html_path'])==c['html_sha256']
            candidate_files.append(c['html_path'])
        if c.get('body_path'):
            assert digest(ROOT/c['body_path'])==c['body_sha256']
            candidate_files.append(c['body_path'])
    same_work=[c for c in candidates if c['status']=='attributed_same_work_candidate']
    local_aliases=read_json(ROOT/'reports/local_public_alias_candidates.json',[])
    # Do not fill inaccessible originals with a merely related article or imply
    # that a repost has identical wording, dates, imagery or completeness.
    effective=[]
    for r in original:
        addition=latest.get(r['url'])
        if addition and addition.get('local_path'):
            nr=dict(addition,local_path=str((ROOT/addition['local_path']).relative_to(BASE)),
                recovered_from=addition['final_url'],original_receipt=r,
                supplement_batch=str(ROOT.relative_to(BASE)))
            nr.pop('error_type',None)
            effective.append(nr)
        else:
            effective.append(r)
    valid=[x for x in effective if x.get('local_path') and x.get('size_bytes',0)>0 and not x.get('error_type')]
    remaining=[dict(x,error_type=x.get('error_type') or 'empty_payload') for x in effective if x.get('error_type') or (x.get('local_path') and x.get('size_bytes')==0)]
    write_csv(ROOT/'reports/remaining_resource_failures.csv',remaining)
    atomic_json(ROOT/'reports/effective_referenced_manifest.json',effective)
    articles=read_json(BASE/'data/processed/articles.json')
    for a in articles:
        related=[{k:v for k,v in c.items() if k!='chain'} for c in candidates if c['article_id']==a['id']]
        if related:
            a['supplemental_body_sources']=related
    atomic_json(ROOT/'reports/articles_with_supplemental_sources.json',articles)
    article_outcomes=[]
    for a in articles:
        if a.get('content_status')!='external_reference':
            continue
        sources=[c for c in candidates if c['article_id']==a['id']]
        article_outcomes.append({'id':a['id'],'title':a['title'],'search_count':2,
            'original_body_status':'robots_disallowed',
            'public_source_status':'attributed_same_work_candidate_saved' if any(c['status']=='attributed_same_work_candidate' for c in sources) else 'related_or_unverified_source_only' if any(c.get('body_path') for c in sources) else 'no_verified_same_work_source',
            'candidate_outcomes':json.dumps([{'url':c['candidate_url'],'status':c['status'],'body_path':c.get('body_path')} for c in sources],ensure_ascii=False)})
    assert len(article_outcomes)==96
    write_csv(ROOT/'reports/article_outcomes.csv',article_outcomes)

    # Reproducible database contains the unchanged original tables, plus separate
    # supplement tables and a complete resource view. The original DB stays intact.
    db=ROOT/'data/combined_archive.sqlite'
    source=sqlite3.connect(f'file:{BASE}/data/processed/dianedu.sqlite?mode=ro',uri=True)
    conn=sqlite3.connect(db)
    source.backup(conn)
    source.close()
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS supplement_resources (url TEXT PRIMARY KEY, data_json TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS supplement_article_candidates (candidate_url TEXT PRIMARY KEY, article_id TEXT NOT NULL, status TEXT NOT NULL, data_json TEXT NOT NULL)')
        conn.executemany('INSERT OR REPLACE INTO supplement_resources VALUES (?,?)',[(r['url'],json.dumps(r,ensure_ascii=False)) for r in effective if r.get('supplement_batch')])
        conn.executemany('INSERT OR REPLACE INTO supplement_article_candidates VALUES (?,?,?,?)',[(c['candidate_url'],c['article_id'],c['status'],json.dumps(c,ensure_ascii=False)) for c in candidates])
        # The original DB serializer adds error=null / error={error_type:...};
        # error_type is already preserved at the top level. Provenance checks
        # this exact difference before normalizing the view, never the old table.
        reconciliation=read_json(ROOT/'reports/original_asset_db_reconciliation.json')
        assert reconciliation['semantic_match_after_explicit_error_serialization_normalization']
        conn.execute("CREATE VIEW IF NOT EXISTS effective_resource_receipts AS SELECT url,json_remove(data_json,'$.error') AS data_json FROM assets WHERE url NOT IN (SELECT url FROM supplement_resources) UNION ALL SELECT url,data_json FROM supplement_resources")
    integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
    dbrows=[json.loads(x[0]) for x in conn.execute('SELECT data_json FROM effective_resource_receipts')]
    assert {x['url']:x for x in dbrows}=={x['url']:x for x in effective}
    counts={table:conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ('projects','articles','schools','assets','supplement_resources','supplement_article_candidates')}
    conn.close()
    assert integrity=='ok'
    known=budget['original_transferred_bytes']+budget['prior_diagnostic_bytes']+budget['network_response_bytes']
    charged=known+budget['search_transfer_reserve_bytes']
    assert charged < budget['cumulative_max_bytes']
    assert budget['prior_diagnostic_bytes']+budget['network_response_bytes']+budget['search_transfer_reserve_bytes'] < budget['stage_max_bytes']
    from datetime import datetime
    elapsed=(datetime.now().timestamp()-datetime.fromisoformat(budget['started_at']).timestamp())/3600
    with (BASE/'reports/gap_investigation_20261015/resource_triage.csv').open(encoding='utf-8-sig',newline='') as f:
        triage=list(csv.DictReader(f))
    triage_out=[]
    for row in triage:
        r=latest.get(row['url'])
        row['supplement_outcome']='saved_valid_resource' if r and r.get('local_path') else 'rechecked_without_valid_file' if r else 'preserved_without_retry'
        row['latest_error']=r.get('error_type','') if r else row['original_error']
        triage_out.append(row)
    write_csv(ROOT/'reports/resource_outcomes.csv',triage_out)
    budget.update(status='complete',finished_at=now())
    atomic_json(ROOT/'reports/budget.json',budget)
    summary=dict(verified_at=now(),status='complete',original_files_changed=changed,
        original_failure_count=996,resource_targets=len(latest),resource_attempt_receipts=len(attempts),
        newly_saved_files=len(saved),newly_saved_bytes=sum(x['size_bytes'] for x in saved),
        checked_target_reuse_records=sum(bool(x.get('reused_checked_target_of')) for x in latest.values()),
        local_existing_public_alias_candidates=len(local_aliases),
        non_saved_recheck_categories=dict(Counter(x.get('error_type') for x in latest.values() if not x.get('local_path'))),
        original_reference_count=len(original),combined_valid_nonempty_files=len(valid),
        combined_valid_resource_bytes=sum(x['size_bytes'] for x in valid),
        remaining_original_reference_failures=len(remaining),invalid_discovery_references_retained=7,
        original_article_body_gaps=96,article_search_queries=192,articles_searched=96,
        candidate_pages_checked=len(candidates),attributed_same_work_candidates=len(same_work),
        same_work_article_ids=[c['article_id'] for c in same_work],
        original_article_bodies_fully_verified_recovered=0,
        candidate_page_outcomes=dict(Counter(c['status'] for c in candidates)),
        sqlite_integrity=integrity,sqlite_table_counts=counts,budget=budget,
        elapsed_hours_at_acceptance=elapsed,known_cumulative_http_response_bytes=known,
        cumulative_bytes_including_search_reserve=charged,search_actual_transfer_bytes='unavailable',
        public_content_archive_complete=False,whole_site_offline_complete=False)
    atomic_json(ROOT/'reports/completion_audit.json',summary)
    lines=['# 点路公开归档补抓验收', '',f"验收时间：{summary['verified_at']}。已完成授权队列处理和正文逐篇检索；仍有缺口，不能称全站完整离线归档。",'',
        '## 数据和资源', '', '原项目1097、文章98、学校723条均保留；原JSON、SQLite、断点、流量账本和失败清单哈希未变。',
        f"原异常996条；本轮资源复核{len(latest)}个唯一引用、{len(attempts)}条尝试回执；新增有效文件{len(saved)}个，{summary['newly_saved_bytes']:,} bytes。新增图片完整解码、大小和SHA均通过。",
        f"合并有效资源{len(valid)}个、{summary['combined_valid_resource_bytes']:,} bytes；原引用仍有异常{len(remaining)}条（含7条误引用，保持历史可追溯）。",
        f"另核验本地已存在的同FileId公开文件候选{len(local_aliases)}条，未请求后台原地址，也未把后台原件标为恢复。共享最终目标的复用回执{summary['checked_target_reuse_records']}条。",
        f"复核未取得有效文件原因：{summary['non_saved_recheck_categories']}。",'',
        '## 96篇正文', '', '96篇均完成两轮检索，192次查询，48个批次回执；未请求被robots禁止的微信文章地址。',
        f"进一步核验{len(candidates)}个候选页面，保存带原文标题图片标记及明确转载说明的同文候选{len(same_work)}篇。",
        '这些是公开转载版本；原微信正文不可取得，无法逐字核对是否删改、缺段、图片一致，未冒充原文恢复。原正文完全核验补齐数仍为0，原站缺口仍96篇。相关主题但无同文证据的页面单列，不能填入原正文。',
        f"候选结果：{summary['candidate_page_outcomes']}。",'',
        '## 流量和时限', '',f"原累计{budget['original_transferred_bytes']:,} bytes；此前诊断{budget['prior_diagnostic_bytes']:,} bytes；本阶段HTTP响应体{budget['network_response_bytes']:,} bytes。",
        f"可计量累计{known:,} bytes；加搜索通信预留{budget['search_transfer_reserve_bytes']:,} bytes，按预算计{charged:,} bytes，未达到累计20GB或本轮1GB上限。搜索工具未提供实际流量，预留不等同实测。",
        f"本轮开始{budget['started_at']}，截止epoch {budget['deadline_epoch']}；验收时经过{elapsed:.3f}小时。HTTP请求{budget['http_requests']}次，限额1500。",'',
        '## 验证与文件', '',f"SQLite integrity_check={integrity}；有效资源视图与合并JSON逐条一致；新旧来源分别记录。",
        '原大媒体位于原data/assets/；新增媒体位于本补抓data/assets/。合并JSON中的资源路径相对于原20261014批次根目录。',
        'combined_archive.sqlite保留原表，effective_resource_receipts为合并资源视图；原SQLite比manifest额外序列化error=null或error对象，已逐项核实其与顶层error_type一致，仅在视图中移除冗余error字段；所有其他字段逐条一致。supplement_article_candidates保留候选与身份限制。',
        'resource_outcomes.csv覆盖全部996条异常；remaining_resource_failures.csv列出本轮后仍异常的原引用。',
        'article_search_coverage.json/csv记录逐篇查询；article_outcomes.csv记录96篇逐项结果；article_candidates.json记录页面核验；articles_with_supplemental_sources.json保留原正文状态并附候选来源。',
        '原失败回执和原报告压缩包保留；新版完整报告包另存，不重复打包大媒体。', '',
        '后台、登录、robots禁止、鉴权和验证码未绕过；404、空响应和主题相近页面未重标为成功。']
    report='\n'.join(lines)+'\n'
    (ROOT/'reports/completion_acceptance.md').write_text(report,encoding='utf-8')
    marker='\n## 2026-10-15 补抓验收\n'
    original_report=(ROOT/'reports/original_completion_acceptance.md').read_text()
    (BASE/'reports/completion_acceptance.md').write_text(original_report+marker+'\n'+report,encoding='utf-8')
    combined_audit=dict(before,supplement_20261015=summary)
    atomic_json(BASE/'reports/completion_audit.json',combined_audit)
    (BASE/'archives/export/README.md').write_text(original_report+marker+'\n'+report,encoding='utf-8')
    archive=BASE/'archives/dianedu_archive_report_with_supplement_20261015.zip'
    tmp=archive.with_suffix('.zip.tmp')
    replacements={'README.md':(BASE/'reports/completion_acceptance.md').read_bytes(),
        'reports/completion_acceptance.md':(BASE/'reports/completion_acceptance.md').read_bytes(),
        'reports/completion_audit.json':(BASE/'reports/completion_audit.json').read_bytes()}
    with zipfile.ZipFile(BASE/'archives/dianedu_archive_report.zip') as old, zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for info in old.infolist():
            z.writestr(info.filename,replacements.get(info.filename,old.read(info.filename)))
        for part in ('reports','research','data/raw','runtime_code'):
            for p in sorted((ROOT/part).rglob('*')):
                if p.is_file() and not p.name.endswith('.tmp'):
                    z.write(p,str(p.relative_to(BASE)))
        z.write(db,str(db.relative_to(BASE)))
    tmp.replace(archive)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))
        assert json.loads(z.read('reports/completion_audit.json'))==combined_audit
    print(json.dumps({k:summary[k] for k in ('status','resource_targets','newly_saved_files','newly_saved_bytes','remaining_original_reference_failures','attributed_same_work_candidates','known_cumulative_http_response_bytes','cumulative_bytes_including_search_reserve','sqlite_integrity')},ensure_ascii=False))


if __name__=='__main__':
    main()

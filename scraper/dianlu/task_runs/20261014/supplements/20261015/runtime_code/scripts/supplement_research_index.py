"""Reconcile per-article search receipts without claiming a negative proof."""
import csv
import json
import re
from pathlib import Path
from collections import defaultdict,Counter

base=Path('/Users/liujunliang/Workspace/knowledge-legacy/scraper/dianlu/task_runs/20261014')
root=base/'supplements/20261015'
articles=[x for x in json.loads((base/'data/processed/articles.json').read_text()) if x.get('content_status')=='external_reference']
by_id=defaultdict(list)
all_results=[]
total=0
for n in range(48):
    p=root/'research'/f'search_{n:03}.json'
    d=json.loads(p.read_text())
    assert len(d['article_ids'])==len(d['queries'])==4
    for article_id,query in zip(d['article_ids'],d['queries']):
        by_id[article_id].append({'query':query,'receipt':str(p.relative_to(root))})
        total+=1
    all_results.extend({'title':m[1],'url':m[2],'receipt':str(p.relative_to(root))} for m in re.finditer(r'^([^\n]+) \((https?://[^\n]+)\)$',d['result'],re.M))
assert len(by_id)==96 and total==192 and all(len(v)==2 for v in by_id.values())
candidate_set={x['url']:x for x in all_results}
rows=[]
for a in articles:
    rows.append({'id':a['id'],'title':a['title'],'original_url':a['raw'].get('WechatUrl') or a['raw'].get('Link'),
                 'search_count':len(by_id[a['id']]),'search_receipts':by_id[a['id']],
                 'original_body_status':'robots_disallowed','search_conclusion':'searched_twice_no_automatic_identity_claim'})
(root/'reports/article_search_coverage.json').write_text(json.dumps({'articles':96,'queries':192,'batch_receipts':48,'unique_result_urls':len(candidate_set),'all_articles_searched_twice':True,'rows':rows},ensure_ascii=False,indent=2))
(root/'research/discovered_result_urls.json').write_text(json.dumps(list(candidate_set.values()),ensure_ascii=False,indent=2))
with (root/'reports/article_search_coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['id','title','original_url','search_count','original_body_status','search_conclusion'])
    w.writeheader();w.writerows({k:v for k,v in r.items() if k!='search_receipts'} for r in rows)
print(json.dumps({'articles':96,'queries':192,'all_articles_searched_twice':True,'unique_result_urls':len(candidate_set)},ensure_ascii=False))

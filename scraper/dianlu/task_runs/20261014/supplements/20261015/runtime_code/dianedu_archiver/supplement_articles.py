"""Archive only discovered public article candidates; keep identity uncertainty."""
import asyncio
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .supplement import BASE, ROOT, SupplementalCrawler, atomic_json, now
from .storage import read_json, append_jsonl, iter_jsonl

# These exact public URLs came from the 192 per-article search queries. No
# guessed endpoints, account pages, proxy content or restricted WeChat URLs.
CANDIDATES = [
    ('08dbd8fb-832c-48e6-87c6-241df1f169bd', 'https://www.jingsailian.com/news/450628.html'),
    ('08dbd609-5035-4454-8ead-1a833a82a88c', 'https://www.jingsailian.com/xiaxiao/530004.html'),
    ('08dbf9f5-3c9c-4a7d-8343-850c71beb2e2', 'https://www.jingsailian.com/xiaxiao/1634084.html'),
    ('08dbf9f4-9864-4f9d-8bee-2ec3331ee1fa', 'https://www.jingsailian.com/xiaxiao/1628412.html'),
    ('08dbd903-252f-42ff-815a-964ab78f203c', 'https://paper.dxy.cn/article/869041'),
    ('08dbd903-252f-42ff-815a-964ab78f203c', 'https://www.sohu.com/a/722908003_121124347'),
    ('08dbd903-ba6b-4fe5-8ed4-b16138e3f3b7', 'https://huaren.us/showtopic.html?topicid=2958701'),
    ('08dbd903-ba6b-4fe5-8ed4-b16138e3f3b7', 'https://m.sohu.com/a/936429198_100057799'),
]


def normalize(text):
    return ''.join(c.lower() for c in text if c.isalnum())


def parse_candidate(body, original_title):
    soup = BeautifulSoup(body, 'lxml')
    article = soup.select_one('.entry-content, .article-content, article, #articleContent, #contentText, .post-content, .single-content, .article__detail')
    if not article:
        return {'status': 'body_container_missing'}
    for tag in article.select('script, style, nav, form, iframe'):
        tag.decompose()
    text = article.get_text('\n', strip=True)
    if len(text) < 200:
        return {'status': 'body_missing_or_challenge'}
    marker = any(normalize(original_title) in normalize(x.get('alt', '')) for x in article.select('img[alt]'))
    full = soup.get_text(' ', strip=True)
    repost = '转载发布' in full and '版权归原作者' in full
    # The original body is inaccessible: even exact original-title image markers
    # prove a public same-work candidate, never byte identity or completeness.
    return {'status': 'attributed_same_work_candidate' if marker and repost else 'related_content_identity_unverified',
            'original_title_image_marker': marker, 'explicit_repost_notice': repost,
            'original_body_byte_comparison_possible': False, 'body_text': text,
            'body_characters': len(text), 'page_title': soup.title.get_text(strip=True) if soup.title else None}


async def main():
    crawler = SupplementalCrawler()
    crawler.blocked |= {urlparse(x['url']).hostname for x in iter_jsonl(ROOT/'data/raw/http_attempts.jsonl') if x.get('status_code') in (401,403)}
    crawler.state['blocked_hosts'] = sorted(crawler.blocked)
    if crawler.state.get('status') not in ('resource_queue_finished', 'article_candidates_finished'):
        await crawler.client.aclose()
        raise RuntimeError('Finish or explicitly stop resource queue before another budget writer starts')
    articles = {x['id']:x for x in read_json(BASE/'data/processed/articles.json', [])}
    old = {x['candidate_url']:x for x in iter_jsonl(ROOT/'data/raw/article_attempts.jsonl')}
    try:
        for article_id, original in CANDIDATES:
            prior = old.get(original)
            retry_missing = prior and prior.get('status') == 'body_container_missing' and not prior.get('parser_retry_once')
            if prior and not retry_missing:
                continue
            current = original
            row = {'article_id': article_id, 'original_title': articles[article_id]['title'],
                   'candidate_url': original, 'checked_at': now(), 'chain': []}
            if retry_missing:
                row.update(parser_retry_once=True, previous_attempt_at=prior['checked_at'])
            for _ in range(5):
                if not await crawler.allowed(current):
                    row['status'] = 'robots_disallowed_or_unavailable'
                    break
                reply, body = await crawler.request(current, max_bytes=5_000_000)
                row['chain'].append(reply)
                if reply.get('error_type'):
                    row['status'] = reply['error_type']
                    break
                if reply.get('status_code') in (301,302,303,307,308) and reply.get('location'):
                    current = urljoin(current, reply['location'])
                    continue
                if reply.get('status_code') != 200:
                    row['status'] = f"http_{reply.get('status_code')}"
                    break
                key = hashlib.sha256(original.encode()).hexdigest()
                html_path = ROOT/'data/raw'/f'article_{key}.html'
                html_path.write_bytes(body)
                row.update(html_path=str(html_path.relative_to(ROOT)),
                    html_sha256=hashlib.sha256(body).hexdigest(), html_size_bytes=len(body))
                parsed = parse_candidate(body, row['original_title'])
                row.update({k:v for k,v in parsed.items() if k != 'body_text'})
                row['final_url'] = current
                if parsed.get('body_text'):
                    text_path = ROOT/'data/raw'/f'article_{key}.txt'
                    text_path.write_text(parsed['body_text'], encoding='utf-8')
                    row.update(html_path=str(html_path.relative_to(ROOT)), body_path=str(text_path.relative_to(ROOT)),
                        html_sha256=hashlib.sha256(body).hexdigest(), html_size_bytes=len(body),
                        body_sha256=hashlib.sha256(text_path.read_bytes()).hexdigest())
                break
            else:
                row['status'] = 'too_many_redirects'
            append_jsonl(ROOT/'data/raw/article_attempts.jsonl', row)
            old[original] = row
            crawler.state['blocked_hosts'] = sorted(crawler.blocked)
            crawler.save_state()
        atomic_json(ROOT/'reports/article_candidates.json', list(old.values()))
        crawler.state['status'] = 'article_candidates_finished'
        crawler.save_state()
    finally:
        await crawler.client.aclose()


def reparse_offline():
    records = {x['candidate_url']:x for x in iter_jsonl(ROOT/'data/raw/article_attempts.jsonl')}
    for url, old in list(records.items()):
        if old.get('status')!='body_container_missing' or not old.get('html_path'):
            continue
        parsed=parse_candidate((ROOT/old['html_path']).read_bytes(),old['original_title'])
        if not parsed.get('body_text'):
            continue
        row=dict(old,previous_status=old['status'],offline_reparsed_at=now())
        row.update({k:v for k,v in parsed.items() if k!='body_text'})
        path=(ROOT/old['html_path']).with_suffix('.txt')
        path.write_text(parsed['body_text'],encoding='utf-8')
        row.update(body_path=str(path.relative_to(ROOT)),body_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        append_jsonl(ROOT/'data/raw/article_attempts.jsonl',row)
        records[url]=row
    atomic_json(ROOT/'reports/article_candidates.json',list(records.values()))


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline-reparse',action='store_true')
    args=parser.parse_args()
    if args.offline_reparse:
        reparse_offline()
    else:
        asyncio.run(main())

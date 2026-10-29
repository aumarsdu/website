import pytest
from dianedu_archiver.supplement import check_budget, valid_asset


def budget():
    return dict(prior_diagnostic_bytes=72845, search_transfer_reserve_bytes=10_000_000,
        network_response_bytes=20, original_transferred_bytes=12_122_596_034,
        cumulative_max_bytes=20_000_000_000, stage_max_bytes=1_000_000_000,
        deadline_epoch=200, http_requests=10, max_http_requests=1500)


def test_both_budgets_include_old_traffic_diagnostic_and_search_reserve():
    state = budget()
    check_budget(state, at=100)
    state['stage_max_bytes'] = 10_072_865
    with pytest.raises(RuntimeError, match='byte_budget'):
        check_budget(state, at=100)
    state['stage_max_bytes'] = 1_000_000_000
    state['original_transferred_bytes'] = 19_990_000_000
    with pytest.raises(RuntimeError, match='byte_budget'):
        check_budget(state, at=100)


def test_deadline_and_request_cap_stop_without_reset():
    state = budget()
    with pytest.raises(RuntimeError, match='time_budget'):
        check_budget(state, at=201)
    state['http_requests'] = 1500
    with pytest.raises(RuntimeError, match='http_request_budget'):
        check_budget(state, at=100)


def test_homepage_and_empty_payload_do_not_count_as_image_recovery():
    assert valid_asset(b'', 'image/jpeg') == 'empty_payload'
    assert valid_asset(b'<html>new site</html>', 'text/html') == 'non_asset_payload'
    assert valid_asset(b'wrong', 'image/jpeg') == 'image_signature_mismatch'
    assert valid_asset(b'\xff\xd8\xff' + b'data', 'image/jpeg') is None


def test_final_target_aliases_reuse_receipt_without_a_second_download(tmp_path):
    import asyncio
    import csv
    import time
    from dianedu_archiver.supplement import SupplementalCrawler
    root=tmp_path/'supplement'
    base=tmp_path/'base'
    (root/'reports').mkdir(parents=True)
    (root/'data/raw').mkdir(parents=True)
    (base/'reports/gap_investigation_20261015').mkdir(parents=True)
    p=base/'reports/gap_investigation_20261015/resource_triage.csv'
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['url','historical_final_url','category'])
        w.writeheader()
        w.writerows([dict(url='https://example.com/'+x,historical_final_url='https://cdn.example.com/same.jpg',category='suspected_stale_or_missing') for x in ['a','b']])
    crawler=SupplementalCrawler.__new__(SupplementalCrawler)
    crawler.root,crawler.base=root,base
    crawler.state=dict(budget(),deadline_epoch=time.time()+60)
    crawler.receipts={}
    crawler.checked_targets={}
    calls=[]
    async def download(item):
        calls.append(item['url'])
        return dict(item,error_type='http_404')
    class Client:
        async def aclose(self):pass
    crawler.download=download
    crawler.client=Client()
    asyncio.run(crawler.run())
    assert len(calls)==1
    assert len(crawler.receipts)==2
    assert crawler.receipts['https://example.com/b']['reused_checked_target_of']=='https://example.com/a'
    assert crawler.state['original_transferred_bytes']==12_122_596_034

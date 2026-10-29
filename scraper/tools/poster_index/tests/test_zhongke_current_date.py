import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from poster_index import zhongke


class CurrentDateTest(unittest.TestCase):
    def test_public_detail_date_precedes_old_inventory_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            poster=Path(tmp)/'poster.jpg';poster.write_bytes(b'image')
            title='AI与数字营销战略：品牌管理与顾客价值创造'
            record={'id':'new-id','title':title,'category':'商科',
                    'raw':{'startTime':'2027-01-23'},'crawled_at':'2026-10-13'}
            mapping={'exact':{title:[poster]},'norm':{}}
            with patch.object(zhongke,'_load_records',side_effect=[[record],[]]), \
                 patch.object(zhongke,'_poster_stem_map',return_value=mapping), \
                 patch.object(zhongke,'_site_poster_map',return_value={}), \
                 patch.object(zhongke,'_october_dates',return_value=({'new-id':'2026-11-07'},{})):
                items,_=zhongke.build()
            self.assertEqual(items[0]['schoolBegins'],'2027-01-23')

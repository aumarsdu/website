from sou_crawler.api_analysis import classify_record
from sou_crawler.discovery import extract_static_endpoints
import unittest


class ApiAnalysisTest(unittest.TestCase):
    def test_classify_list_asset_api(self):
        record = {
            "url": "https://edu4-crm-api.neoschool.com/sdm/mtc/pubController/pageV2?page=1&pageSize=20",
            "method": "GET",
            "status": 200,
            "body_summary": {
                "array_paths": ["$.data.records"],
                "paths_sample": ["$.data.total", "$.data.records[].title", "$.data.records[].posterUrl"],
            },
        }
        result = classify_record(record)
        self.assertIn("项目列表接口", result["likely_types"])
        self.assertTrue(result["signals"]["has_pagination"])
        self.assertGreater(result["score"], 0)

    def test_extract_static_endpoints_from_bundle_text(self):
        script = "baseURL:'https://edu4-crm-api.neoschool.com';function x(){return I({url:'/sdm/mtc/pubController/getPoster',method:'post'})}"
        result = extract_static_endpoints(script, "https://pbl.hirepglobal.com/js/index.js")
        self.assertEqual(result[0]["url"], "https://edu4-crm-api.neoschool.com/sdm/mtc/pubController/getPoster")


if __name__ == "__main__":
    unittest.main()

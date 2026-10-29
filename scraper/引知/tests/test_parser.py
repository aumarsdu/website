import unittest

from caoliao_archiver.parser import (
    extract_tpl_ids,
    extract_urls_from_html,
    extract_urls_from_json,
)


class ParserTests(unittest.TestCase):
    def test_extract_urls_from_html_handles_common_attrs(self):
        html = """
        <html>
          <img src="/a.png">
          <video poster="https://static.clewm.net/poster.jpg"></video>
          <img srcset="/small.png 1x, https://static.clewm.net/large.png 2x">
          <div style="background-image: url('/bg.png')"></div>
          <a href="https://example.com/doc.pdf">download</a>
          <a href="navLink:http://qr71.cn/odBU6p/qHdi0EF?list_name=demo.pdf">查看</a>
        </html>
        """
        urls = extract_urls_from_html(html, "https://h.qr61.cn/odBU6p/qYtCDec")
        self.assertIn("https://h.qr61.cn/a.png", urls)
        self.assertIn("https://h.qr61.cn/small.png", urls)
        self.assertIn("https://h.qr61.cn/bg.png", urls)
        self.assertIn("https://static.clewm.net/poster.jpg", urls)
        self.assertIn("https://static.clewm.net/large.png", urls)
        self.assertIn("https://example.com/doc.pdf", urls)
        self.assertIn("http://qr71.cn/odBU6p/qHdi0EF?list_name=demo.pdf", urls)

    def test_extract_urls_from_json_recurses(self):
        payload = {
            "field": {
                "value": [
                    "see https://oss.cli.im/file.pdf",
                    "navLink:https://h.qr61.cn/odBU6p/qB0CEBW?list_name=demo",
                ]
            }
        }
        self.assertEqual(
            extract_urls_from_json(payload),
            {
                "https://oss.cli.im/file.pdf",
                "https://h.qr61.cn/odBU6p/qB0CEBW?list_name=demo",
            },
        )

    def test_extract_tpl_ids_only_form_operations(self):
        operations = [
            {"element_type": 2, "element_value": "122507"},
            {"element_type": 1, "element_value": "88001"},
            {"element_type": 2, "element_value": 122507},
        ]
        self.assertEqual(extract_tpl_ids(operations), [122507])


if __name__ == "__main__":
    unittest.main()

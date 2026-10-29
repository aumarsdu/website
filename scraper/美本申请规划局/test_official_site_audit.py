import unittest
from official_site_audit import Page, valid_url


class OfficialAuditTests(unittest.TestCase):
    def test_public_url(self):
        self.assertEqual(valid_url('https://example.org/program#fees'), 'https://example.org/program')

    def test_reject_private_and_credential_urls(self):
        for value in ['file:///tmp/a', 'http://localhost/a', 'http://127.0.0.1/a', 'http://10.0.0.1/a', 'https://user:password@example.org/']:
            with self.assertRaises(ValueError):
                valid_url(value)

    def test_parser_retains_evidence_and_links(self):
        parser = Page()
        parser.feed('<title>Example Program</title><script>private()</script><h2>2027 Tuition</h2><p>$500</p><a href="/admissions">Eligibility</a>')
        self.assertEqual(parser.title, ['Example Program'])
        self.assertNotIn('private()', parser.lines)
        self.assertIn('$500', parser.lines)
        self.assertEqual(parser.links, [{'href': '/admissions', 'label': 'Eligibility'}])


if __name__ == '__main__':
    unittest.main()

import json
import unittest
from pathlib import Path

from structured_data_audit import decode_flight, parse_page, walk


class StructuredTests(unittest.TestCase):
    def test_archived_page(self):
        root = Path(__file__).parent
        status = json.loads((root / '抓取核查状态_20261014.json').read_text())
        html = (root / status['latest_run'] / 'raw/activities.html').read_text()
        parser, ld, flight, other = parse_page(html)
        self.assertEqual(ld[0]['@type'], 'WebPage')
        self.assertEqual(other, [])
        decoded, unparsed = decode_flight(flight)
        self.assertTrue(decoded)
        self.assertEqual(unparsed, [])

    def test_graph_and_microdata(self):
        html = '<div itemscope itemtype="https://schema.org/Event"></div><script type="application/ld+json">{"@graph":[{"@type":"Event","name":"Sample"}]}</script>'
        parser, ld, _, _ = parse_page(html)
        self.assertEqual(len(parser.semantic), 1)
        self.assertTrue(any(isinstance(x, dict) and x.get('name') == 'Sample' for x in walk(ld)))

    def test_flight_is_decoded_as_data(self):
        payload = [1, '1:{"name":"sample"}\n2:I[1,[],"default"]\n3:$undefined\n']
        html = '<script>self.__next_f.push(' + json.dumps(payload) + ')</script>'
        _, _, flight, _ = parse_page(html)
        decoded, unparsed = decode_flight(flight)
        self.assertEqual(decoded[0]['value']['name'], 'sample')
        self.assertEqual(decoded[1]['kind'], 'import')
        self.assertEqual(unparsed, ['3:$undefined'])


if __name__ == '__main__':
    unittest.main()

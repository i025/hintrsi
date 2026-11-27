import unittest
from pathlib import Path
from window_report import load_records, summarize


class WindowReportTests(unittest.TestCase):
    def test_single_timestamp(self):
        self.assertEqual(summarize([{'time': 7, 'value': 11}], 7, 7),
                         {'count': 1, 'total': 11, 'first': 7, 'last': 7})

    def test_both_boundaries(self):
        rows = [{'time': 1, 'value': 2}, {'time': 2, 'value': 5}, {'time': 3, 'value': 8}]
        self.assertEqual(summarize(rows, 1, 2),
                         {'count': 2, 'total': 7, 'first': 1, 'last': 2})

    def test_empty_window(self):
        self.assertEqual(summarize([{'time': 3, 'value': 8}], 4, 6),
                         {'count': 0, 'total': 0, 'first': None, 'last': None})

    def test_all_twenty_shards(self):
        records = load_records(Path(__file__).parent / 'data')
        self.assertEqual(len(records), 40)
        self.assertEqual(summarize(records, 0, 39),
                         {'count': 40, 'total': 2460, 'first': 0, 'last': 39})


if __name__ == '__main__':
    unittest.main()

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('elapsed', Path(__file__).parents[1] / 'scripts/pipeline_elapsed_seconds.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ElapsedTests(unittest.TestCase):
    def test_seconds_and_milliseconds(self):
        self.assertEqual(module.elapsed_seconds('1700000000', 1700000542), 542)
        self.assertEqual(module.elapsed_seconds('1700000000000', 1700000542), 542)

    def test_iso_timestamp(self):
        self.assertEqual(module.elapsed_seconds('2023-11-14T22:13:20Z', 1700000542), 542)

    def test_missing_timestamp_fails_closed(self):
        with self.assertRaises(ValueError):
            module.elapsed_seconds(None)

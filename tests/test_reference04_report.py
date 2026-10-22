"""The delivery report must distinguish incompatibility from bad evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.compare_reference04 import ROOT, report


class ReferenceReportTests(unittest.TestCase):
    def test_optional_profile_matches_all_observed_economic_fields(self):
        result, status = report(observed_presto88=True)
        self.assertEqual(status, 0)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['differences'], 0)
        self.assertEqual(len(result['cases']), 5)
        self.assertEqual(result['profile'], 'observed-presto88')
        self.assertIn('not a certification', result['scope'])

    def test_partial_comparison_reports_three_incompatible_cases(self):
        result, status = report()
        self.assertEqual(status, 1)
        self.assertEqual(result['errors'], [])
        mismatches = {case['case'] for case in result['cases'] if case['differences']}
        self.assertEqual(mismatches, {'dimensions', 'rounding', 'factor_text'})
        self.assertGreater(result['differences'], 3)
        for case in result['cases']:
            self.assertIn('factor', case['uncompared_fields'])

    def test_changed_fixture_is_invalid_evidence_not_a_known_gap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'docs/evidencias-04/ensayos', root / 'docs/evidencias-04/ensayos')
            shutil.copytree(ROOT / 'tests/reference04/presto88', root / 'tests/reference04/presto88')
            fixture = root / 'tests/reference04/presto88/dimensions.bc3'
            fixture.write_bytes(fixture.read_bytes() + b'\r\n')
            result, status = report(root)
            self.assertEqual(status, 2)
            self.assertEqual(result['errors'], [{'case': 'dimensions', 'error': 'Fixture hash mismatch'}])

    def test_evidence_path_cannot_escape_its_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'docs/evidencias-04/ensayos', root / 'docs/evidencias-04/ensayos')
            shutil.copytree(ROOT / 'tests/reference04/presto88', root / 'tests/reference04/presto88')
            path = root / 'docs/evidencias-04/ensayos/simple-observado.json'
            observation = json.loads(path.read_text(encoding='utf-8'))
            observation['evidence'] = ['../../../tests/reference04/presto88/simple.bc3']
            path.write_text(json.dumps(observation), encoding='utf-8')
            result, status = report(root)
            self.assertEqual(status, 2)
            self.assertEqual(result['errors'][0]['case'], 'simple')
            self.assertIn('outside evidence root', result['errors'][0]['error'])

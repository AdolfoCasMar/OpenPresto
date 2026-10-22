from pathlib import Path
import json
import shutil
import tempfile
import unittest

from tools.compare_locked_prices04 import ROOT, report


class LockComparisonReportTests(unittest.TestCase):
    def test_observed_fields_match_with_explicit_unknowns(self):
        result, status = report()
        self.assertEqual(status, 0, result['errors'])
        self.assertEqual(len(result['checks']), 29)
        self.assertEqual(result['differences'], 0)
        self.assertIn('native_persistence', result['uncompared_fields'])
        self.assertIn('BC3', result['uncompared_fields'])

    def test_changes_and_invalid_evidence_are_distinguished(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path('tests/reference04/price_override')
            shutil.copytree(ROOT / relative, root / relative)
            manifest = json.loads((root / relative / 'manifest.json').read_text(encoding='utf-8'))
            for path in manifest['native_results']:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / path, target)
                data = json.loads(target.read_text(encoding='utf-8'))
                for shot in data['screenshots']:
                    shutil.copy2(ROOT / shot['path'], root / shot['path'])
            observation = root / manifest['native_results'][1]
            data = json.loads(observation.read_text(encoding='utf-8'))
            data['observed']['resources_before_edit'][0]['quantity'] = '3'
            observation.write_text(json.dumps(data), encoding='utf-8')
            result, status = report(root)
            self.assertEqual(status, 1)
            self.assertEqual(result['differences'], 1)
            self.assertEqual(result['errors'], [])
            shot = root / data['screenshots'][0]['path']
            shot.write_bytes(b'altered screenshot')
            result, status = report(root)
            self.assertEqual(status, 2)
            self.assertIn('Screenshot hash mismatch', result['errors'])


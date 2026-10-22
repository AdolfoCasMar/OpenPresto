"""An import result must describe actual content without concealing failures."""
import unittest
from openpresto.pzh_importer import _import, PZHImportError
from openpresto.pzh_archive import import_summary
from openpresto.storage import dumps,loads
from test_pzh_percentages import fixture
from unittest.mock import patch


class PZHSummaryTests(unittest.TestCase):
    def test_no_management_data_is_not_an_unsupported_management_warning(self):
        b=_import(fixture(concept_field3=True),'synthetic.pzh').budget
        summary,partial=import_summary(b)
        self.assertIn('Gestión: sin datos en este archivo.',summary)
        self.assertNotIn('0x03',summary)
        self.assertFalse(partial)
        self.assertTrue(any('0x03' in note for note in b.import_warnings))
        self.assertEqual(import_summary(loads(dumps(b))),(summary,partial))

    def test_skipped_modules_are_not_described_as_absent(self):
        summary,partial=import_summary(_import(fixture(),'synthetic.pzh',modules=set()).budget)
        self.assertIn('Gestión: no seleccionado',summary)
        self.assertNotIn('Gestión: sin datos',summary)
        self.assertFalse(partial)

    def test_optional_failure_remains_visible(self):
        with patch('openpresto.pzh_certifications.import_certifications',side_effect=PZHImportError('test error')):
            b=_import(fixture(),'synthetic.pzh').budget
        summary,partial=import_summary(b)
        self.assertTrue(partial)
        self.assertIn('Certificaciones: no convertido',summary)
        self.assertIn('Importación parcial',summary)
        self.assertEqual(import_summary(loads(dumps(b))),(summary,partial))

    def test_unresolved_reference_is_a_real_warning(self):
        summary,partial=import_summary(_import(fixture(unresolved=True),'synthetic.pzh').budget)
        self.assertTrue(partial)
        self.assertIn('Importación parcial',summary)


if __name__=='__main__':unittest.main()

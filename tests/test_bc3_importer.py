"""Pruebas de la importación estructural conservadora."""
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal
from openpresto.bc3_importer import BC3ImportError, import_bc3


class ImportTests(unittest.TestCase):
    def sample(self, records):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'test.bc3'
        path.write_bytes(records.encode('cp1252'))
        return path

    def test_minimal_structure_and_decimal(self):
        path = self.sample('~V|SOFT|FIEBDC-3/2002|Presto 8.8||ANSI|\n'
            '~C|ROOT##||Obra|3.00|\n~C|P|m2|Partida|1.50|\n'
            '~D|ROOT##|P\\1\\2\\|\n~M|ROOT##\\P|datos no procesados|\n')
        result = import_bc3(path)
        self.assertEqual(result.root_code, 'ROOT##')
        self.assertEqual(len(result.budget.relations), 1)
        self.assertEqual(result.budget.relations[0].quantity, Decimal('2'))
        self.assertEqual(result.declared_prices['ROOT##'], Decimal('3.00'))
        self.assertEqual(result.unsupported_counts['M'], 1)
        self.assertTrue(any(k == 'M' for k, _ in result.raw_records))

    def test_missing_reference_rejected(self):
        path = self.sample('~V|SOFT|FIEBDC-3/2002|Presto 8.8||ANSI|\n'
                           '~C|R##||Obra|0|\n~D|R##|NO\\1\\1\\|\n')
        with self.assertRaises(BC3ImportError):
            import_bc3(path)

    def test_nonunit_factor_warns_without_changing_calculation_or_source(self):
        from openpresto.calculations import BudgetCalculator
        from openpresto.storage import dumps, loads
        for factor in ('2', '0', '-1'):
            with self.subTest(factor=factor):
                path = self.sample('~V|SOFT|FIEBDC-3/2002|Presto||ANSI|\n'
                    '~C|R##||Obra|0|\n~C|P|m|Partida|4.25|\n'
                    f'~D|R|P\\{factor}\\1.5\\|\n')
                original = path.read_bytes()
                result = import_bc3(path)
                notes = [w for w in result.warnings if w.startswith('~D R / P: factor')]
                self.assertEqual(len(notes), 1)
                self.assertEqual(result.budget.relations[0].quantity,
                                 Decimal(factor) * Decimal('1.5'))
                self.assertEqual(path.read_bytes(), original)
                restored = loads(dumps(result.budget))
                self.assertEqual(restored.import_warnings, result.warnings)
                self.assertEqual(restored.source_records, result.raw_records)
                self.assertEqual(BudgetCalculator(restored).total(),
                                 BudgetCalculator(result.budget).total())

    def test_unit_factor_does_not_emit_relation_warning(self):
        path = self.sample('~V|SOFT|FIEBDC-3/2002|Presto||ANSI|\n'
            '~C|R##||Obra|0|\n~C|P|m|Partida|1|\n~D|R|P\\1.00\\2\\|\n')
        result = import_bc3(path)
        self.assertFalse(any(w.startswith('~D R / P: factor') for w in result.warnings))

    def test_multiple_roots_rejected(self):
        path = self.sample('~V|SOFT|FIEBDC-3/2002|Presto 8.8||ANSI|\n'
                           '~C|A##||Uno|0|\n~C|B##||Dos|0|\n')
        with self.assertRaises(BC3ImportError):
            import_bc3(path)

    def test_invalid_structure_rejected(self):
        for source in ('', '~C|R##||Sin version|0|',
                       '~V|SOFT|FIEBDC-3/2002|Presto||ANSI|\n~C|A##||A|0|\n'
                       '~D|A##|X\\1\\|'):
            with self.subTest(source=source):
                with self.assertRaises(BC3ImportError):
                    import_bc3(self.sample(source))

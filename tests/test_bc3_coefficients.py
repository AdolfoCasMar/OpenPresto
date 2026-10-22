import unittest
from decimal import Decimal
from pathlib import Path
import tempfile

from openpresto.bc3_coefficients import economic_coefficients
from openpresto.bc3_importer import import_bc3, BC3ImportError


class CoefficientTests(unittest.TestCase):
    def test_order_empty_fields_and_terminal_separator(self):
        self.assertEqual(economic_coefficients('5\\13\\6\\2\\21\\'),
                         tuple(map(Decimal, ('5', '13', '6', '2', '21'))))
        self.assertEqual(economic_coefficients('5\\\\6'),
                         tuple(map(Decimal, ('5', '0', '6', '0', '0'))))
        self.assertEqual(economic_coefficients(''), (Decimal(0),) * 5)
        for invalid in ('NaN', '0\\Infinity', 'abc', '1\\2\\3\\4\\5\\6'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                economic_coefficients(invalid)

    def test_only_zero_economic_block_can_pass_import_gate(self):
        original = (Path(__file__).parent / 'reference04/presto88/simple.bc3').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'case.bc3'
            for field in ('0\\0\\0\\0\\0', '0\\0\\0\\0\\21', '5'):
                path.write_bytes(original + ('~K||' + field + '|\r\n').encode('ascii'))
                for profile in (False, True):
                    with self.subTest(field=field, profile=profile):
                        if field == '0\\0\\0\\0\\0':
                            import_bc3(path, observed_presto88=profile)
                        else:
                            with self.assertRaises(BC3ImportError):
                                import_bc3(path, observed_presto88=profile)

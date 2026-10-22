from decimal import Decimal
from pathlib import Path
import codecs
import csv
import io
import unittest

from openpresto.bc3 import BC3Error, MAX_BYTES, concepts_csv, parse, read


class ParserTests(unittest.TestCase):
    def test_ansi_accents_and_exact_decimal(self):
        raw = '~V|Autor|FIEBDC-3/95|Prueba||ANSI|\r\n~C|A|m²|Albañilería|0.10||0|\r\n'.encode('cp1252')
        doc = parse(raw)
        self.assertEqual(doc.encoding, 'cp1252')
        self.assertEqual(doc.concepts[0].summary, 'Albañilería')
        self.assertEqual(doc.concepts[0].price, Decimal('0.10'))
        self.assertEqual(doc.raw, raw)

    def test_text_before_concept_and_alias(self):
        doc = parse(b'~T|alias|Texto\ncon dos lineas.|~C|A\\alias|u|Resumen|3|||')
        self.assertEqual(doc.concepts[0].text, 'Texto\ncon dos lineas.')

    def test_unknown_records_remain_in_copy(self):
        raw = b'~C|A|u|Uno|1|||~D|A|B\\1\\2\\|~M|A|1|2|other|\x1a'
        doc = parse(raw)
        self.assertEqual(doc.raw, raw)
        self.assertEqual(doc.counts['M'], 1)
        self.assertTrue(any('~D' in w and '~M' in w for w in doc.warnings))

    def test_missing_invalid_and_zero_prices_differ(self):
        doc = parse(b'~C|A|u|Sin precio||||~C|B|u|Cero|0|||~C|C|u|Invalido|NaN|||')
        self.assertIsNone(doc.concepts[0].price)
        self.assertEqual(doc.concepts[1].price, Decimal(0))
        self.assertIsNone(doc.concepts[2].price)
        self.assertTrue(any('no interpretable' in w for w in doc.warnings))

    def test_multiple_prices_are_explicit(self):
        doc = parse(b'~C|A|u|Uno|10\\12\\|||')
        self.assertEqual(doc.concepts[0].price, Decimal(10))
        self.assertTrue(any('varios precios' in w for w in doc.warnings))

    def test_repeated_record_preserves_omitted_fields(self):
        doc = parse(b'~C|A|m2|Resumen|9|||~C|A|||10|||')
        self.assertEqual(len(doc.concepts), 1)
        self.assertEqual(doc.concepts[0].summary, 'Resumen')
        self.assertEqual(doc.concepts[0].price, Decimal(10))

    def test_utf8_bom_and_default_oem(self):
        self.assertEqual(parse(codecs.BOM_UTF8 + '~C|A|u|Cañón|1|||'.encode()).concepts[0].summary, 'Cañón')
        self.assertEqual(parse('~C|A|u|Cañón|1|||'.encode('cp850')).concepts[0].summary, 'Cañón')

    def test_rejects_invalid_input(self):
        for raw in (b'garbage', b'MZ\0data', b'~C||u|No code|1|||', b'~V|only|', b'~INVALID|x|'):
            with self.subTest(raw=raw), self.assertRaises(BC3Error):
                parse(raw)

    def test_rejects_unknown_encoding_and_oversize(self):
        with self.assertRaises(BC3Error):
            parse(b'~V|A|FIEBDC-3/95|A||ALIEN|~C|A|u|a|1|||')
        with self.assertRaises(BC3Error):
            parse(b'x' * (MAX_BYTES + 1))

    def test_csv_quotes_and_formula_protection(self):
        doc = parse(b'~C|=1+1|u|=HYPERLINK("x"); text|2|||')
        rows = list(csv.reader(io.StringIO(concepts_csv(doc).decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(rows[1][0], "'=1+1")
        self.assertTrue(rows[1][2].startswith("'="))
        self.assertEqual(rows[1][3], '2')

    def test_demo(self):
        doc = read(Path(__file__).resolve().parents[1] / 'openpresto/data/ejemplo.bc3')
        self.assertEqual(len(doc.concepts), 7)
        self.assertEqual(doc.concepts[-1].price, Decimal('8.90'))


if __name__ == '__main__':
    unittest.main()

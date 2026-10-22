"""Synthetic regression tests: no private project data is included."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from openpresto.bc3_measurements import parse_measurement, rebuild_record, BC3MeasurementLine
from openpresto.bc3_importer import import_bc3
from openpresto.calculations import BudgetCalculator
from openpresto.storage import dumps, loads, save_budget, StorageError
from openpresto.measurements import summarize_relation


def record(rows, declared='0'):
    return parse_measurement('R##\\P|1\\|' + declared + '|' + '\\'.join(v for row in rows for v in row) + '\\|')


SAMPLE = ('~V|OpenPresto|FIEBDC-3/2002|OpenPresto||ANSI|\n'
          '~C|R##||Obra de prueba|3.02|\n~C|P|m|Partida de prueba|2|\n'
          '~D|R##|P\\1\\1.51\\|\n'
          '~M|R##\\P|1\\|1.51|\\Primera\\1\\1.005\\\\\\3\\b/2\\1\\1\\\\\\1\\Subtotal\\\\\\\\\\|\n')


class RoundingRegressionTests(unittest.TestCase):
    def test_round_each_line_before_sum_with_deductions(self):
        r = record([('', '', '1', '1.005', '', ''), ('', '', '1', '1.005', '', ''),
                    ('', '', '-1', '.005', '', '')])
        self.assertEqual(r.calculated_quantity, Decimal('2.01'))
        self.assertEqual(r.lines[-1].partial, Decimal('-.01'))

    def test_subtotals_reset_and_never_double_count(self):
        r = record([('', '', '2', '', '', ''), ('1', 'Parcial', '', '', '', ''),
                    ('', '', '3', '', '', ''), ('2', 'Acumulado', '', '', '', ''),
                    ('', '', '4', '', '', ''), ('1', '', '', '', '', '')])
        self.assertEqual([v.partial for v in r.lines], list(map(Decimal, ('2', '2', '3', '5', '4', '4'))))
        self.assertEqual(r.calculated_quantity, Decimal('9'))

    def test_description_only_and_formula(self):
        r = record([('', 'Descripción', '', '', '', ''), ('3', 'b/2', '', '1.01', '', '')])
        self.assertEqual(r.lines[0].partial, 0)
        self.assertEqual(r.calculated_quantity, Decimal('.51'))

    def test_formula_literal_does_not_pass_through_binary_float(self):
        r = record([('3', ' 1.00499999999999999 ', '', '', '', '')])
        self.assertEqual(r.calculated_quantity, Decimal('1.00'))

    def test_invalid_line_invalidates_total(self):
        for row in (('9', '', '', '', '', ''), ('', '', 'NaN', '', '', ''),
                    ('3', '1/0', '', '', '', ''), ('', '', '1e999999', '', '', '')):
            with self.subTest(row=row):
                r = record([row, ('2', '', '', '', '', '')])
                self.assertIsNone(r.calculated_quantity)
                self.assertIsNone(r.lines[-1].partial)
                self.assertTrue(r.warnings)

    def test_edit_recalculates_subtotals_and_rejects_delimiters(self):
        r = record([('', '', '2', '', '', ''), ('1', '', '', '', '', '')])
        edited = rebuild_record(r, [replace(r.lines[0], a='3'), r.lines[1]])
        self.assertEqual(edited.lines[1].partial, 3)
        self.assertIsNone(edited.declared_quantity)
        with self.assertRaises(ValueError):
            rebuild_record(r, [replace(r.lines[0], description='bad|record')])


class IntegratedProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'sample.bc3'
        self.path.write_bytes(SAMPLE.encode('cp1252'))

    def test_import_save_reload_preserves_lines_and_total(self):
        result = import_bc3(self.path)
        self.assertEqual(len(result.budget.bc3_measurements), 1)
        b = loads(dumps(result.budget))
        self.assertEqual(BudgetCalculator(b).total(), Decimal('3.02'))
        r = b.relations[0]
        self.assertEqual(len(b.bc3_measurements[r.id].lines), 3)
        summary = summarize_relation(b, r.id)
        self.assertEqual(summary.quantity, Decimal('1.51'))
        self.assertEqual(len(summary.entries), 2)
        self.assertEqual(b.source_records, result.raw_records)

    def test_ambiguous_duplicate_measurement_is_not_applied(self):
        self.path.write_bytes((SAMPLE + SAMPLE[SAMPLE.index('~M'):]).encode('cp1252'))
        result = import_bc3(self.path)
        self.assertFalse(result.budget.bc3_measurements)
        self.assertTrue(any('Varios registros' in w for w in result.warnings))

    def test_wrong_position_is_not_applied(self):
        self.path.write_bytes(SAMPLE.replace('~M|R##\\P|1\\|', '~M|R##\\P|2\\|').encode('cp1252'))
        result = import_bc3(self.path)
        self.assertFalse(result.budget.bc3_measurements)
        self.assertIn('M', result.unsupported_counts)

    def test_source_protected(self):
        source = self.path.read_bytes()
        with self.assertRaises(StorageError):
            save_budget(import_bc3(self.path).budget, self.path)
        self.assertEqual(self.path.read_bytes(), source)

    def test_invalid_extended_json_rejected(self):
        import json
        data = json.loads(dumps(import_bc3(self.path).budget))
        data['bc3']['measurements']['missing'] = next(iter(data['bc3']['measurements'].values()))
        with self.assertRaises(StorageError):
            loads(json.dumps(data))


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        IntegratedProjectTests.setUp(self)
        from openpresto.presto_workspace import PrestoWorkspace
        self.window = PrestoWorkspace()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_load_edit_undo_redo_save_reopen(self):
        w = self.window
        self.assertTrue(w.load_path(self.path))
        self.assertTrue(w.dirty)
        self.assertIsNone(w.path)
        self.assertEqual(w.measurements_table.rowCount(), 3)
        rid = w.budget.relations[0].id
        r = w.budget.bc3_measurements[rid]
        w.budget.bc3_measurements[rid] = rebuild_record(r, [replace(r.lines[0], b='2'), *r.lines[1:]])
        w._changed()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('5'))
        w.undo()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('3.02'))
        w.redo()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('5'))
        w.path = Path(self.temp.name) / 'saved.json'
        self.assertTrue(w.save())
        self.assertTrue(w.load_path(w.path))
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('5'))

    def test_failed_load_preserves_project(self):
        w = self.window
        w.load_path(self.path)
        old = w.budget
        with patch.object(w, '_error'):
            self.assertFalse(w.load_path(Path(self.temp.name) / 'missing.bc3'))
        self.assertIs(w.budget, old)

    def test_delete_measurement_and_undo(self):
        w = self.window
        w.load_path(self.path)
        w.bottom_tabs.setCurrentWidget(w.measurements_table)
        w.measurements_table.selectRow(0)
        self.app.processEvents()
        w.delete_selected()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('1'))
        w.undo()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('3.02'))

    def test_search(self):
        w = self.window
        w.load_path(self.path)
        w.search.setText('no match')
        self.assertTrue(w.prices.isRowHidden(0))
        w.search.setText('Partida')
        self.assertFalse(w.prices.isRowHidden(0))

    def test_edit_concept_through_dialog_and_undo(self):
        from openpresto.editor import ConceptDialog
        from PySide6.QtWidgets import QDialog
        w = self.window
        w.load_path(self.path)
        w.bottom_tabs.setCurrentWidget(w.concepts_table)
        w.concepts_table.selectRow(1)
        self.app.processEvents()
        def accept(dialog):
            dialog.price.setText('4')
            return QDialog.DialogCode.Accepted
        with patch.object(ConceptDialog, 'exec', accept):
            w.edit_selected()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('6.04'))
        w.undo()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('3.02'))

    def test_cancelled_new_keeps_document(self):
        w = self.window
        w.load_path(self.path)
        old = w.budget
        with patch.object(w, '_confirm_discard', return_value=False):
            w.new_budget()
        self.assertIs(w.budget, old)

    def test_failed_save_keeps_dirty_and_previous_file(self):
        w = self.window
        w.load_path(self.path)
        w.path = Path(self.temp.name) / 'saved.json'
        w.path.write_text('previous', encoding='utf-8')
        with patch('openpresto.storage.os.replace', side_effect=OSError('test failure')), patch.object(w, '_error'):
            self.assertFalse(w.save())
        self.assertTrue(w.dirty)
        self.assertEqual(w.path.read_text(encoding='utf-8'), 'previous')

    def test_uncalculable_edit_is_rolled_back(self):
        w = self.window
        w.load_path(self.path)
        w.budget.concepts['P'] = replace(w.budget.concepts['P'], base_price='1e999999')
        with patch.object(w, '_error'):
            w._changed()
        self.assertEqual(BudgetCalculator(w.budget).total(), Decimal('3.02'))

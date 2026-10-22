import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer, QItemSelectionModel
from PySide6.QtWidgets import QApplication, QMdiArea, QMdiSubWindow, QDialog
from openpresto.presto_workspace import PrestoWorkspace
from openpresto.budget import Budget, BudgetConcept, BudgetRelation, BudgetMeasurement
from openpresto.calculations import BudgetCalculator
from openpresto.storage import dumps as project_dumps, loads, save_budget
from openpresto.editor import ConceptDialog, RelationDialog, MeasurementDialog
from test_integrated_project import SAMPLE


def dumps(budget):
    # Object-key order can change after history restoration; list order and all
    # values must still match. Compare the complete project canonically.
    return json.dumps(json.loads(project_dumps(budget)), sort_keys=True)


class Workspace03Tests(unittest.TestCase):
    def test_adjust_price_menu_preview_cancel_apply_undo_redo_and_reopen(self):
        from PySide6.QtWidgets import QMessageBox
        fixture = Path(__file__).resolve().parents[1] / 'docs/evidencias-04/ensayos/bloqueo-generado-openpresto-pendiente.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        action = self.w.commands['ajustar-precio'][0]
        self.assertTrue(action.isEnabled())
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        for reply in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes):
            with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=('20,00', True)), patch('openpresto.mdi_workspace.QMessageBox.question', return_value=reply) as preview:
                action.trigger()
            text = preview.call_args.args[2]
            self.assertIn('Resultado: 20.02', text)
            self.assertIn('140.14', text)
            self.assertIn('OVR1', text)
            self.assertIn('demás partidas', text)
            if reply == QMessageBox.StandardButton.No:
                self.assertEqual(dumps(self.w.budget), before)
                self.assertEqual(len(self.w._undo), history)
        self.assertEqual(len(self.w._undo), history + 1)
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('140.14'))
        self.assertEqual(self.w.budget.locked_prices, {})
        self.w.current_code = 'OVB#'
        self.w.refresh()
        self.assertEqual(self.w.prices.item(0,6).text(), '20.02')
        after = dumps(self.w.budget)
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)
        self.w.redo()
        self.assertEqual(dumps(self.w.budget), after)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'adjusted.json'
            save_budget(self.w.budget, path)
            self.w.dirty = False
            self.assertTrue(self.w.load_path(path))
            self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('140.14'))

    def test_adjust_price_cell_uses_single_transaction_and_can_cancel(self):
        from PySide6.QtWidgets import QMessageBox
        fixture = Path(__file__).resolve().parents[1] / 'docs/evidencias-04/ensayos/bloqueo-generado-openpresto-pendiente.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        for reply in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes):
            with patch('openpresto.mdi_workspace.QInputDialog.getItem', return_value=('Ajustar recursos', True)), patch('openpresto.mdi_workspace.QMessageBox.question', return_value=reply):
                self.w.prices.item(0,6).setText('13')
            if reply == QMessageBox.StandardButton.No:
                self.assertEqual(dumps(self.w.budget), before)
                self.assertEqual(self.w.prices.item(0,6).text(), '14.00')
                self.assertEqual(len(self.w._undo), history)
        self.assertEqual(self.w.prices.item(0,6).text(), '13.02')
        self.assertEqual(len(self.w._undo), history + 1)
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)

    def test_adjust_price_invalid_or_cancelled_input_keeps_project_and_history(self):
        fixture = Path(__file__).parent / 'reference04/price_override/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        for text, accepted in [('20', False), ('NaN', True), ('1000', True)]:
            with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=(text, accepted)), patch('openpresto.mdi_workspace.QMessageBox.question') as preview, patch.object(self.w, '_error') as error:
                self.w.adjust_selected_price()
                preview.assert_not_called()
                self.assertEqual(error.called, accepted)
            self.assertEqual(dumps(self.w.budget), before)
            self.assertEqual(len(self.w._undo), history)
        self.w.current_code = 'OVITEM'
        self.w.refresh()
        self.assertFalse(self.w.commands['ajustar-precio'][0].isEnabled())

    def test_selected_basic_prices_multiply_preview_cancel_and_single_undo(self):
        from PySide6.QtWidgets import QMessageBox
        fixture = Path(__file__).parent / 'reference04/price_override/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.current_code = 'OVITEM'
        self.w.refresh()
        selection = self.w.prices.selectionModel()
        selection.select(self.w.prices.model().index(1,0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual(len(selection.selectedRows()), 2)
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        for reply in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes):
            with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=('2',True)), patch('openpresto.mdi_workspace.QMessageBox.question', return_value=reply) as preview:
                self.w.multiply_selected_prices()
            self.assertIn('OVR1', preview.call_args.args[2])
            self.assertIn('OVR2', preview.call_args.args[2])
            if reply == QMessageBox.StandardButton.No:
                self.assertEqual(dumps(self.w.budget), before)
                self.assertEqual(len(self.w._undo), history)
        self.assertEqual(self.w.budget.total(), Decimal('140'))
        self.assertEqual(len(self.w._undo), history+1)
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)
        self.w.redo()
        self.assertEqual(self.w.budget.total(), Decimal('140'))
        after = dumps(self.w.budget)
        with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=('2',False)), patch('openpresto.mdi_workspace.QMessageBox.question') as preview:
            self.w.multiply_selected_prices()
            preview.assert_not_called()
        self.assertEqual(dumps(self.w.budget), after)
        with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=('NaN',True)), patch.object(self.w,'_error') as error, patch('openpresto.mdi_workspace.QMessageBox.question') as preview:
            self.w.multiply_selected_prices()
            error.assert_called_once()
            preview.assert_not_called()
        self.assertEqual(dumps(self.w.budget), after)

    def test_price_columns_visibility_preserves_project_selection_and_edit_mapping(self):
        self.load_native()
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        selected = self.w.selected_relation
        menu = self.w.price_columns_menu()
        actions = {action.text(): action for action in menu.actions()}
        self.assertTrue(actions['PrPres'].isChecked())
        actions['PrPres'].trigger()
        self.assertTrue(self.w.prices.isColumnHidden(6))
        self.w.refresh()
        self.assertTrue(self.w.prices.isColumnHidden(6))
        self.assertEqual(dumps(self.w.budget), before)
        self.assertEqual(len(self.w._undo), history)
        self.assertEqual(self.w.selected_relation, selected)
        actions['Mostrar todas las columnas'].trigger()
        self.assertFalse(any(self.w.prices.isColumnHidden(c) for c in range(self.w.prices.columnCount())))
        self.assertEqual(dumps(self.w.budget), before)
        self.assertEqual(len(self.w._undo), history)
        actions['CanPres'].trigger()
        self.w.prices.item(0, 6).setText('4')
        self.assertEqual(self.w.budget.concepts['P'].base_price, Decimal('4'))
        self.assertEqual(self.w.budget.total(), Decimal('13'))
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)
        self.assertTrue(self.w.prices.isColumnHidden(5))
        menu.deleteLater()

    def test_synonym_search_selection_and_reopen(self):
        fixture = Path(__file__).parent / 'reference04/aliases/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture))
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        self.assertEqual(self.w.prices.item(0,0).text(), 'ITEM')
        self.assertIn('ALT', self.w.prices.item(0,0).toolTip())
        row = list(self.w.budget.concepts).index('ITEM')
        self.assertIn('ALT', self.w.concepts_table.item(row,0).toolTip())
        self.w.search.setText('unknown-code')
        self.assertTrue(self.w.prices.isRowHidden(0))
        self.assertIsNone(self.w.active_concept)
        self.w.search.setText('alt')
        self.assertFalse(self.w.prices.isRowHidden(0))
        self.assertEqual(self.w.active_concept, 'ITEM')
        self.assertEqual(dumps(self.w.budget), before)
        self.assertEqual(len(self.w._undo), history)
        with patch.object(self.w, '_error') as error:
            self.w._transaction(lambda: self.w.budget.add_concept(BudgetConcept('ALT')))
            self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), before)
        self.assertEqual(len(self.w._undo), history)
        self.w.search.clear()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'synonyms.json'
            save_budget(self.w.budget, target)
            self.w.dirty = False
            self.assertTrue(self.w.load_path(target))
        self.w.search.setText('ALT')
        self.assertFalse(self.w.prices.isRowHidden(0))
        self.assertEqual(self.w.active_concept, 'ITEM')

    def test_composed_price_cell_cancel_block_and_undo(self):
        fixture = Path(__file__).parent / 'reference04/price_override/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        for entered, accepted in [('20', False), ('20,00', True)]:
            with patch('openpresto.mdi_workspace.QInputDialog.getItem',
                       return_value=('Precio bloqueado', accepted)) as dialog:
                self.w.prices.item(0,6).setText(entered)
                dialog.assert_called_once()
            if not accepted:
                self.assertEqual(dumps(self.w.budget), before)
                self.assertEqual(len(self.w._undo), history)
                self.assertEqual(self.w.prices.item(0,6).text(), '10.00')
        self.assertEqual(self.w.budget.total(), Decimal('140.00'))
        self.assertEqual(len(self.w._undo), history + 1)
        self.assertEqual(len(self.w.budget.relations), 6)
        self.assertEqual(self.w.budget.concepts['OVITEM'].base_price, Decimal('0'))
        self.w.current_code = 'OVB#'
        self.w.refresh()
        self.assertEqual(self.w.prices.item(0,6).text(), '20.00')
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)
        for entered in ['NaN', '-1', 'abc']:
            with patch('openpresto.mdi_workspace.QInputDialog.getItem') as dialog, patch.object(self.w, '_error') as error:
                self.w.prices.item(0,6).setText(entered)
                self.assertTrue(error.called)
                dialog.assert_not_called()
            self.assertEqual(dumps(self.w.budget), before)

    def test_price_context_unlock_targets_clicked_relation_and_can_cancel(self):
        sample = Path(__file__).resolve().parents[1] / 'openpresto/data/precio-bloqueado-demo.openpresto.json'
        self.assertTrue(self.w.load_path(sample))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        self.w.show_panel('precios')
        QApplication.processEvents()
        item = self.w.prices.item(0, 6)
        position = self.w.prices.visualItemRect(item).center()
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        with patch('openpresto.mdi_workspace.QMenu') as menu:
            menu.return_value.exec.return_value = None
            self.w.price_context_menu(position)
        self.assertEqual(dumps(self.w.budget), before)
        self.assertEqual(len(self.w._undo), history)
        self.w.active_concept = 'OVR1'
        with patch('openpresto.mdi_workspace.QMenu') as menu:
            unlock = self.w.commands['desbloquear-precio'][0]
            menu.return_value.exec.side_effect = lambda *args: unlock.trigger()
            self.w.price_context_menu(position)
            menu.return_value.addAction.assert_any_call(unlock)
        self.assertEqual(self.w.budget.locked_prices, {})
        self.assertEqual(self.w.budget.total(), Decimal('70'))
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)
        with patch('openpresto.mdi_workspace.QMenu') as menu:
            other_column = self.w.prices.visualItemRect(self.w.prices.item(0, 4)).center()
            self.w.price_context_menu(other_column)
            menu.assert_called_once()
        self.assertEqual(dumps(self.w.budget), before)

    def test_composed_concept_dialog_shows_current_price_without_changing_base(self):
        fixture = Path(__file__).parent / 'reference04/price_override/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.show_panel('conceptos')
        row = list(self.w.budget.concepts).index('OVITEM')
        self.w.concepts_table.setCurrentCell(row, 0)
        base = self.w.budget.concepts['OVITEM'].base_price
        for lock, expected in [(False, '10.00'), (True, '20.00')]:
            if lock:
                self.w._transaction(lambda: self.w.budget.locked_prices.update({'OVITEM': Decimal('20')}))
            def accept(dialog):
                self.assertEqual(dialog.price.text(), expected)
                self.assertFalse(dialog.price.isEnabled())
                dialog.summary.setText('Descripción editada ' + expected)
                return QDialog.DialogCode.Accepted
            with patch.object(ConceptDialog, 'exec', accept):
                self.w.edit_selected()
            self.assertEqual(self.w.budget.concepts['OVITEM'].base_price, base)
            self.assertEqual(self.w.budget.concept_price('OVITEM'), Decimal(expected))
            self.assertEqual(self.w.budget.concepts['OVITEM'].summary, 'Descripción editada ' + expected)
        self.assertEqual(self.w.budget.locked_prices, {'OVITEM': Decimal('20')})

    def test_locked_price_actions_history_and_reopen(self):
        fixture = Path(__file__).parent / 'reference04/price_override/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        before = dumps(self.w.budget)
        for value, accepted in [('20', False), ('NaN', True), ('-2', True)]:
            with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=(value, accepted)), patch.object(self.w, '_error'):
                self.w.lock_selected_price()
            self.assertEqual(dumps(self.w.budget), before)
        with patch('openpresto.mdi_workspace.QInputDialog.getText', return_value=('20,00', True)):
            self.w.lock_selected_price()
        self.assertEqual(self.w.budget.total(), Decimal('140.00'))
        self.assertEqual(self.w.prices.item(0, 6).foreground().color().name(), '#ef7777')
        locked = dumps(self.w.budget)
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), before)
        self.w.redo()
        self.assertEqual(dumps(self.w.budget), locked)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'locked.json'
            save_budget(self.w.budget, target)
            self.w.dirty = False
            self.assertTrue(self.w.load_path(target))
        self.w.current_code = 'OVITEM'
        self.w.refresh()
        self.w.prices.item(0, 6).setText('5')
        self.assertEqual(self.w.budget.total(), Decimal('140.00'))
        self.w.current_code = 'OVA#'
        self.w.refresh()
        self.w.unlock_selected_price()
        self.assertEqual(self.w.budget.total(), Decimal('98'))
        self.assertEqual(self.w.prices.item(0, 6).text(), '14.00')
        self.w.undo()
        self.assertEqual(self.w.budget.total(), Decimal('140.00'))

    def test_indirect_bc3_export_preserves_project_and_rejects_overwrite(self):
        sample = Path(__file__).resolve().parents[1] / 'openpresto/data/indirectos-demo.openpresto.json'
        self.assertTrue(self.w.load_path(sample))
        before = dumps(self.w.budget)
        history = len(self.w._undo)
        expected = (Path(__file__).resolve().parents[1] /
            'docs/evidencias-04/ensayos/indirectos-generados-exportador-pendiente.bc3').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'indirect.bc3'
            with patch('openpresto.mdi_workspace.QFileDialog.getSaveFileName',
                       return_value=(str(target), 'BC3')), patch('openpresto.mdi_workspace.QInputDialog.getItem', return_value=('cp1252', True)), patch(
                       'openpresto.mdi_workspace.QMessageBox.information'):
                self.w.export_budget()
            self.assertEqual(target.read_bytes(), expected)
            self.assertEqual(dumps(self.w.budget), before)
            self.assertEqual(len(self.w._undo), history)
            self.w.dirty = False
            self.assertTrue(self.w.load_path(target, observed_presto88=True))
            from openpresto.calculations import calculator_for
            self.assertEqual(calculator_for(self.w.budget).total(), Decimal('390.22'))
            self.w.current_code = 'CIA#'
            self.w.refresh()
            self.assertEqual(self.w.prices.item(0,6).text(), '70.05')
            self.assertEqual(self.w.prices.item(0,7).text(), '147.10')
            self.assertEqual(self.w.prices.item(1,7).text(), '22.47')
            project = Path(directory) / 'reimported.json'
            save_budget(self.w.budget, project)
            self.assertTrue(self.w.load_path(project))
            self.assertEqual(calculator_for(self.w.budget).total(), Decimal('390.22'))
            with patch('openpresto.mdi_workspace.QFileDialog.getSaveFileName',
                       return_value=(str(target), 'BC3')), patch('openpresto.mdi_workspace.QInputDialog.getItem', return_value=('cp1252', True)), patch.object(self.w, '_error') as error:
                self.w.export_budget()
                self.assertTrue(error.called)
            self.assertEqual(target.read_bytes(), expected)

    def test_indirect_configuration_undo_and_reopen(self):
        from openpresto.calculations import calculator_for
        fixture = Path(__file__).parent / 'reference04/indirect_costs/baseline.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        baseline = dumps(self.w.budget)
        with patch('openpresto.mdi_workspace.QInputDialog.getItem',
                   side_effect=[('Configurar', True), ('Excluir', True)]), patch(
                   'openpresto.mdi_workspace.QInputDialog.getText',
                   side_effect=[('CIA#, CIB#', True), ('5,00', True)]):
            self.w.configure_indirect_costs()
        self.assertEqual(calculator_for(self.w.budget).total(), Decimal('389.14'))
        edited = dumps(self.w.budget)
        history = len(self.w._undo)
        for chapters, rate in [('CIA#', '5'), ('CIA#, CIB#', 'NaN'),
                               ('CIA#, CIB#', '-1'), ('CIA#, CIB#', '5.001')]:
            with self.subTest(chapters=chapters, rate=rate), patch(
                    'openpresto.mdi_workspace.QInputDialog.getItem',
                    side_effect=[('Configurar', True), ('Incluir', True)]), patch(
                    'openpresto.mdi_workspace.QInputDialog.getText',
                    side_effect=[(chapters, True), (rate, True)]), patch.object(self.w, '_error') as error:
                self.w.configure_indirect_costs()
                self.assertTrue(error.called)
            self.assertEqual(dumps(self.w.budget), edited)
            self.assertEqual(len(self.w._undo), history)
        with patch('openpresto.mdi_workspace.QInputDialog.getItem', return_value=('Desactivar', True)):
            self.w.configure_indirect_costs()
        self.assertEqual(calculator_for(self.w.budget).total(), Decimal('371.64'))
        self.assertIsNone(self.w.budget.indirect_config)
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), edited)
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), baseline)
        self.w.redo()
        self.assertEqual(dumps(self.w.budget), edited)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'indirect.json'
            save_budget(self.w.budget, path)
            self.w.dirty = False
            self.assertTrue(self.w.load_path(path))
            self.assertEqual(calculator_for(self.w.budget).total(), Decimal('389.14'))

    def test_percentage_profile_edit_undo_save_reopen_and_protected_base(self):
        from openpresto.calculations import calculator_for
        fixture = Path(__file__).parent / 'reference04/percentages/order_scope.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.assertEqual(calculator_for(self.w.budget).total(), Decimal('840.73'))
        self.w.current_code = 'PCTD'
        self.w.refresh()
        self.assertEqual(self.w.prices.item(3,5).text(), '0.701')
        self.assertFalse(self.w.prices.item(3,5).flags() & Qt.ItemFlag.ItemIsEditable)
        baseline = dumps(self.w.budget)
        self.w.prices.item(3,6).setText('20')
        self.assertEqual(self.w.prices.item(3,7).text(), '14.02')
        self.assertEqual(self.w.prices.item(4,7).text(), '8.41')
        self.assertEqual(calculator_for(self.w.budget).total(), Decimal('848.44'))

        self.w.undo()
        self.assertEqual(dumps(self.w.budget), baseline)
        self.w.redo()
        edited = dumps(self.w.budget)
        with patch.object(self.w, '_error') as error:
            self.w.prices.item(3,6).setText('NaN')
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), edited)
        with patch.object(self.w, '_error') as error:
            self.w.prices.item(3,5).setText('999')
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), edited)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'percentage.openpresto.json'
            save_budget(self.w.budget, path)
            self.assertTrue(self.w.load_path(path))
        self.assertEqual(dumps(self.w.budget), edited)
        self.assertEqual(calculator_for(self.w.budget).total(), Decimal('848.44'))

        with tempfile.TemporaryDirectory() as directory:
            exported = Path(directory) / 'edited-percentages.bc3'
            with patch('openpresto.mdi_workspace.QFileDialog.getSaveFileName', return_value=(str(exported), 'BC3')), \
                    patch('openpresto.mdi_workspace.QInputDialog.getItem', return_value=('cp1252', True)), \
                    patch('openpresto.mdi_workspace.QMessageBox.information'):
                self.w.export_budget()
            self.assertTrue(exported.exists())
            self.assertTrue(self.w.load_path(exported, observed_presto88=True))
            self.assertEqual(calculator_for(self.w.budget).total(), Decimal('848.44'))
            self.w.current_code = 'PCTD'
            self.w.refresh()
            self.assertEqual(self.w.prices.item(3,7).text(), '14.02')
            self.assertEqual(self.w.prices.item(4,7).text(), '8.41')

    def test_unsupported_percentage_load_keeps_existing_project(self):
        self.load_native()
        stable = dumps(self.w.budget)
        previous_path = self.w.path
        fixture = Path(__file__).parent / 'reference04/percentages/prefix_pending.bc3'
        with patch.object(self.w, '_error') as error:
            self.assertFalse(self.w.load_path(fixture))
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), stable)
        self.assertEqual(self.w.path, previous_path)
    def test_first_phase_quantity_replaces_origin_and_undo_restores_it(self):
        from openpresto.phase_editor import PhaseScheduleDialog
        observed = json.loads((Path(__file__).resolve().parents[1] /
            'docs/evidencias-04/ensayos/fases-certificacion-observadas.json').read_text(encoding='utf-8'))['origin_to_first_phase']
        self.load_certification_budget()
        self.w.certification_table.item(0,4).setText(observed['previous_origin_quantity'])
        self.w.show_panel('certificacion-fases')
        panel = self.w.certification_phase_panel
        def configure(dialog):
            dialog.start.setText('2026-10-15')
            dialog.ends.setPlainText('2026-11-30\n2026-12-31')
            dialog.approved.setValue(1)
            return QDialog.DialogCode.Accepted
        with patch.object(PhaseScheduleDialog, 'exec', configure):
            panel.configure()
        stable = dumps(self.w.budget)
        panel.table.item(0,3).setText(observed['entered_phase_quantity'])
        self.assertNotIn('r1', self.w.budget.certified_quantities)
        self.assertEqual(self.w.budget.phase_certified_quantities[1]['r1'], 2)
        self.assertEqual(panel.table.item(0,7).text(), observed['resulting_cumulative_amount'])
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), stable)
        self.assertEqual(self.w.budget.certified_quantities['r1'], Decimal(observed['previous_origin_quantity']))
        self.w.redo()
        self.assertEqual(panel.table.item(0,7).text(), '25.00')

    def load_phase_budget(self):
        from test_certifications import CertificationTests
        from openpresto.certification_phases import CertificationSchedule
        b = CertificationTests().budget()
        b.certification_schedule = CertificationSchedule('2026-01-01',
            ('2026-01-31','2026-02-28','2026-03-31'), 2)
        b.phase_certified_quantities = {1:{'r1':Decimal(2)},2:{'r1':Decimal(3)},3:{'r1':Decimal(100)}}
        path = self.root / 'phases.json'
        save_budget(b,path)
        self.assertTrue(self.w.load_path(path))
        self.w.show_panel('certificacion-fases')
        self.app.processEvents()

    def test_phase_edit_future_exclusion_history_and_reopen(self):
        self.load_phase_budget()
        panel = self.w.certification_phase_panel
        self.assertEqual(panel.table.item(0,7).text(), '62.50')
        panel.table.item(0,3).setText('4')
        self.assertEqual(panel.table.item(0,7).text(), '87.50')
        panel.phase.setCurrentIndex(2)
        panel.table.item(0,3).setText('200')
        self.assertEqual(panel.table.item(0,7).text(), '87.50')
        self.w.undo()
        self.assertEqual(self.w.budget.phase_certified_quantities[3]['r1'], 100)
        self.w.undo()
        self.assertEqual(panel.table.item(0,7).text(), '62.50')
        self.w.redo()
        stable = dumps(self.w.budget)
        with patch.object(self.w, '_error'):
            panel.table.item(0,3).setText('NaN')
        self.assertEqual(dumps(self.w.budget), stable)
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(panel.table.item(0,7).text(), '87.50')

    def test_phase_calendar_approval_and_protected_reordering(self):
        from openpresto.phase_editor import PhaseScheduleDialog
        self.load_phase_budget()
        panel = self.w.certification_phase_panel
        def approve(dialog):
            dialog.approved.setValue(3)
            return QDialog.DialogCode.Accepted
        with patch.object(PhaseScheduleDialog, 'exec', approve):
            panel.configure()
        self.assertEqual(panel.table.item(0,7).text(), '1312.50')
        self.w.undo()
        self.assertEqual(panel.table.item(0,7).text(), '62.50')
        stable = dumps(self.w.budget)
        def reorder(dialog):
            dialog.ends.setPlainText('2026-01-31\n2026-02-15\n2026-02-28\n2026-03-31')
            return QDialog.DialogCode.Accepted
        with patch.object(PhaseScheduleDialog, 'exec', reorder), patch.object(self.w, '_error') as error:
            panel.configure()
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), stable)

    def test_phase_data_protects_relation_and_concept_role(self):
        self.load_phase_budget()
        stable = dumps(self.w.budget)
        self.w.show_panel('relaciones')
        self.w.relations_table.setCurrentCell(2,0)
        with patch.object(self.w, '_error') as error:
            self.w.delete_selected()
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), stable)
        self.w.show_panel('precios')
        self.w.prices.setCurrentCell(0,1)
        with patch.object(self.w, '_error') as error:
            self.w.prices.item(0,1).setText('partida')
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), stable)

    def load_certification_budget(self):
        from test_certifications import CertificationTests
        path = self.root / 'certification.json'
        save_budget(CertificationTests().budget(), path)
        self.assertTrue(self.w.load_path(path))
        self.w.show_panel('certificacion')
        self.app.processEvents()

    def test_certification_edit_history_invalid_and_reopen(self):
        self.load_certification_budget()
        before_price = BudgetCalculator(self.w.budget).total()
        table = self.w.certification_table
        table.item(0,4).setText('4,125')
        self.assertEqual(table.item(0,6).text(), '51.56')
        self.assertEqual(self.w.budget.certified_quantities['r1'], Decimal('4.125'))
        self.assertEqual(BudgetCalculator(self.w.budget).total(), before_price)
        stable = dumps(self.w.budget)
        with patch.object(self.w, '_error'):
            table.item(0,4).setText('NaN')
        self.assertEqual(dumps(self.w.budget), stable)
        self.w.undo()
        self.assertEqual(self.w.budget.certified_quantities, {})
        self.w.redo()
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(self.w.budget.certified_quantities['r1'], Decimal('4.125'))
        table.item(0,4).setText('11')
        self.assertEqual(table.item(0,7).text(), 'Exceso')
        table.item(0,4).setText('')
        self.assertNotIn('r1', self.w.budget.certified_quantities)

    def test_certified_relation_cannot_be_deleted_until_cleared(self):
        self.load_certification_budget()
        self.w.certification_table.item(0,4).setText('4')
        stable = dumps(self.w.budget)
        self.w.show_panel('relaciones')
        self.w.relations_table.setCurrentCell(2,0)
        with patch.object(self.w, '_error') as error:
            self.w.delete_selected()
        self.assertTrue(error.called)
        self.assertEqual(dumps(self.w.budget), stable)

    def test_concept_measurement_precision_dialog_history_and_reopen(self):
        self.load_native(True)
        self.w.budget.measurements[0] = replace(self.w.budget.measurements[0], length=Decimal('1.005'))
        self.w._changed()
        self.w.show_panel('conceptos')
        row = next(i for i in range(self.w.concepts_table.rowCount()) if self.w.concepts_table.item(i,0).text() == 'P')
        self.w.concepts_table.setCurrentCell(row,0)
        def accept(dialog):
            self.assertEqual(dialog.measurement_decimals.value(), -1)
            dialog.measurement_decimals.setValue(2)
            return QDialog.DialogCode.Accepted
        with patch.object(ConceptDialog, 'exec', accept):
            self.w.edit_selected()
        self.assertEqual(self.w.budget.relation_quantity('rp'), Decimal('2.02'))
        self.w.undo()
        self.assertEqual(self.w.budget.relation_quantity('rp'), Decimal('2.010'))
        self.w.redo()
        self.w.path = self.root / 'measurement-precision.json'
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(self.w.budget.concepts['P'].measurement_decimals, 2)
        self.assertEqual(self.w.budget.measurements[0].length, Decimal('1.005'))
        self.assertEqual(self.w.budget.relation_quantity('rp'), Decimal('2.02'))

    def test_annul_dimension_dialog_history_and_reopen(self):
        self.load_native(True)
        self.w.show_panel('mediciones')
        self.w.measurements_table.setCurrentCell(0,0)
        def accept(dialog):
            dialog.annulled['length'].setChecked(True)
            return QDialog.DialogCode.Accepted
        with patch.object(MeasurementDialog, 'exec', accept):
            self.w.edit_selected()
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('2'))
        self.assertEqual(self.w.budget.measurements[0].length, Decimal('4'))
        self.w.undo()
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('8'))
        self.w.redo()
        self.w.path = self.root / 'annulled.json'
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('2'))

    def test_native_formula_cell_rejects_error_undo_and_persists(self):
        self.load_native(measurements=True)
        self.w.prices.setCurrentCell(0, 0)
        self.w.show_panel('mediciones')
        self.app.processEvents()
        self.w.measurements_table.item(0, 5).setText('B^2')
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('32'))
        self.assertEqual(self.w.budget.measurements[0].formula, 'B^2')
        stable = dumps(self.w.budget)
        with patch.object(self.w, '_error') as error:
            self.w.measurements_table.item(0, 5).setText('1/0')
        error.assert_called_once()
        self.assertEqual(dumps(self.w.budget), stable)
        self.w.undo()
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('8'))
        self.w.redo()
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('32'))
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(self.w.budget.measurements[0].partial(), Decimal('32'))

    def test_export_command_writes_current_text_without_changing_project(self):
        fixture = Path(__file__).parent / 'reference04/presto88/simple.bc3'
        self.assertTrue(self.w.load_path(fixture, observed_presto88=True))
        self.w.budget.concepts['ITEM'] = replace(self.w.budget.concepts['ITEM'], text='Exportado por Qt')
        self.w._changed()
        before = dumps(self.w.budget)
        dirty = self.w.dirty
        target = self.root / 'exported.bc3'
        with patch('openpresto.mdi_workspace.QFileDialog.getSaveFileName', return_value=(str(target), 'BC3')), \
             patch('openpresto.mdi_workspace.QInputDialog.getItem', return_value=('cp1252', True)), \
             patch('openpresto.mdi_workspace.QMessageBox.information'):
            self.w.commands['exportar'][0].trigger()
        from openpresto.bc3_importer import import_bc3
        result = import_bc3(target, observed_presto88=True).budget
        self.assertEqual(result.concepts['ITEM'].text, 'Exportado por Qt')
        self.assertEqual(dumps(self.w.budget), before)
        self.assertEqual(self.w.dirty, dirty)

    def test_observed_profile_import_factor_view_edit_undo_and_reopen(self):
        fixture = Path(__file__).parent / 'reference04/presto88/factor_text.bc3'
        original = fixture.read_bytes()
        with patch('openpresto.mdi_workspace.QFileDialog.getOpenFileName', return_value=(str(fixture), 'BC3')):
            self.w.commands['importar-perfil88'][0].trigger()
        self.assertEqual(self.w.prices.item(0, 8).text(), '2')
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('17.00'))
        self.w.prices.item(0, 5).setText('3')
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('25.50'))
        self.w.undo()
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('17.00'))
        self.w.path = self.root / 'profile.json'
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(self.w.budget.relations[0].factor, Decimal('2'))
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('17.00'))
        self.assertEqual(fixture.read_bytes(), original)

    def test_root_precision_action_cancel_undo_save_and_reopen(self):
        fixture = Path(__file__).parent / 'reference04/presto88/rounding.bc3'
        self.assertTrue(self.w.load_path(fixture))
        self.w.path = self.root / 'precision.json'
        self.assertTrue(self.w.save())
        original = dumps(self.w.budget)
        with patch('openpresto.mdi_workspace.QInputDialog.getInt', return_value=(0, False)):
            self.w.commands['precision-raiz'][0].trigger()
        self.assertEqual(dumps(self.w.budget), original)
        self.assertFalse(self.w.dirty)
        with patch('openpresto.mdi_workspace.QInputDialog.getInt', return_value=(0, True)):
            self.w.commands['precision-raiz'][0].trigger()
        self.assertTrue(self.w.dirty)
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('4.00'))
        self.w.undo()
        self.assertEqual(dumps(self.w.budget), original)
        self.assertFalse(self.w.dirty)
        self.w.redo()
        self.assertEqual(self.w.budget.root_quantity_decimals, 0)
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(self.w.path))
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('4.00'))
        self.assertEqual(json.loads(dumps(self.w.budget))['version'], 4)
        with patch('openpresto.mdi_workspace.QInputDialog.getInt', return_value=(-1, True)):
            self.w.commands['precision-raiz'][0].trigger()
        self.assertEqual(BudgetCalculator(self.w.budget).total(), Decimal('4.02'))

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.w = PrestoWorkspace()
        self.w.show()
        self.app.processEvents()
        self.addCleanup(self.close_window)

    def close_window(self):
        self.w._text_pending = False
        self.w._text_timer.stop()
        self.w.dirty = False
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def load_native(self,measurements=False):
        b = Budget('R')
        for c in (BudgetConcept('R',summary='Obra'),BudgetConcept('P','m2','Partida',base_price='3',text='Texto inicial'),BudgetConcept('Q','u','Otra',base_price='5',text='Otra descripción')):
            b.add_concept(c)
        b.add_relation(BudgetRelation('R','P','2',1,id='rp'))
        b.add_relation(BudgetRelation('R','Q','1',2,id='rq'))
        if measurements:
            b.add_measurement(BudgetMeasurement('rp','Sala','2','4',id='m1'))
            b.add_measurement(BudgetMeasurement('rq','Otra','3',id='m2'))
        path = self.root/'native.json'
        save_budget(b,path)
        self.assertTrue(self.w.load_path(path))
        self.app.processEvents()
        return path

    def load_bc3(self):
        path = self.root/'input.bc3'
        path.write_bytes((SAMPLE+'~T|P|Texto importado.|\n').encode('cp1252'))
        self.assertTrue(self.w.load_path(path))
        self.app.processEvents()
        return path

    def test_empty_workspace_shows_welcome_without_project_windows(self):
        self.assertIs(self.w.centralWidget(),self.w.section_ui.stack)
        self.assertEqual(self.w.section_ui.stack.currentIndex(),1)
        self.assertIsInstance(self.w.mdi,QMdiArea)
        self.assertEqual(self.w.mdi.subWindowList(),[])
        self.assertFalse(self.w.project_open)
        self.assertEqual([a.text() for a in self.w.menuBar().actions() if a.isVisible()],['Archivo','?'])
        self.assertFalse(self.w.commands['Guardar'][0].isEnabled())
        self.assertTrue(self.w.isVisible())

    def test_mdi_windows_close_reopen_and_layout(self):
        self.load_native()
        self.assertEqual(len(self.w.mdi.subWindowList()),4)
        self.assertTrue(all(isinstance(w,QMdiSubWindow) for w in self.w.mdi.subWindowList()))
        window = self.w.windows['texto']
        window.move(65,80)
        window.resize(330,240)
        self.assertEqual(window.pos().x(),65)
        window.close()
        self.assertTrue(window.isHidden())
        self.w.show_panel('texto')
        self.assertIs(self.w.windows['texto'],window)
        self.assertFalse(window.isHidden())
        self.assertEqual(len(self.w.mdi.subWindowList()),4)
        self.assertEqual([a.text() for a in self.w.menuBar().actions() if a.isVisible()],
                         ['Archivo','Edición','Ver','Cálculos','Informes','Ventana','?'])
        self.assertTrue(self.w.commands['exportar'][0].isEnabled())
        self.w.tile_windows(True)
        self.assertNotEqual(self.w.windows['texto'].y(),self.w.windows['precios'].y())

    def test_direct_quantity_price_undo_save_reopen(self):
        path = self.load_native()
        self.w.prices.item(0,5).setText('4')
        self.assertEqual(self.w.budget._relation('rp').quantity,Decimal('4'))
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('17'))
        self.w.prices.item(0,6).setText('2.5')
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('15'))
        self.w.undo()
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('17'))
        self.w.redo()
        self.assertTrue(self.w.save())
        self.assertTrue(self.w.load_path(path))
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('15'))

    def test_save_preserves_history_and_dirty_tracks_saved_state(self):
        self.load_native()
        self.w.prices.item(0,5).setText('4')
        self.assertTrue(self.w.save())
        self.assertFalse(self.w.dirty)
        self.w.undo()
        self.assertTrue(self.w.dirty)
        self.assertEqual(self.w.budget._relation('rp').quantity,Decimal('2'))
        self.w.redo()
        self.assertFalse(self.w.dirty)
        self.assertEqual(self.w.budget._relation('rp').quantity,Decimal('4'))

    def test_relation_edit_validation_and_secondary_sync(self):
        self.load_native()
        self.w.show_panel('relaciones')
        self.w.relations_table.setCurrentCell(1,0)
        self.assertEqual(self.w.active_concept,'Q')
        self.assertEqual(self.w.text_editor.toPlainText(),'Otra descripción')
        def accept(dialog):
            dialog.quantity.setText('3')
            dialog.position.setText('3')
            return QDialog.DialogCode.Accepted
        with patch.object(RelationDialog,'exec',accept):
            self.w.edit_selected()
        self.assertEqual(self.w.budget._relation('rq').position,3)
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('21'))
        self.w.undo()
        before = dumps(self.w.budget)
        def cycle(dialog):
            dialog.child_code.setCurrentText('R')
            return QDialog.DialogCode.Accepted
        with patch.object(RelationDialog,'exec',cycle),patch.object(self.w,'_error'):
            self.w.edit_selected()
        self.assertEqual(dumps(self.w.budget),before)

    def test_pending_text_cancelled_close_is_not_lost(self):
        self.load_native()
        self.w.text_editor.setPlainText('Texto pendiente')
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):
            self.assertFalse(self.w.close_project())
        self.assertTrue(self.w.project_open)
        self.assertEqual(self.w.budget.concepts['P'].text,'Texto pendiente')

    def test_old_v2_project_migrates_imported_text(self):
        self.load_bc3()
        data = json.loads(dumps(self.w.budget))
        data['version'] = 2
        for c in data['concepts']:
            c.pop('text')
        restored = loads(json.dumps(data))
        self.assertEqual(restored.concepts['P'].text,'Texto importado.')
        self.assertEqual(json.loads(dumps(restored))['version'],3)

    def test_measurement_selection_and_edit(self):
        self.load_native(True)
        self.assertFalse(self.w.measurements_table.isRowHidden(0))
        self.assertTrue(self.w.measurements_table.isRowHidden(1))
        self.w.measurements_table.item(0,2).setText('5')
        self.assertEqual(self.w.budget.relation_quantity('rp'),Decimal('10'))
        self.assertEqual(self.w.prices.item(0,5).text(),'10.000')
        self.w.prices.setCurrentCell(1,0)
        self.assertTrue(self.w.measurements_table.isRowHidden(0))
        self.assertFalse(self.w.measurements_table.isRowHidden(1))
        self.assertEqual(self.w.text_editor.toPlainText(),'Otra descripción')

    def test_measured_quantity_cannot_be_overwritten(self):
        self.load_native(True)
        self.assertFalse(self.w.prices.item(0,5).flags() & Qt.ItemFlag.ItemIsEditable)
        with patch.object(self.w,'_error') as error:
            self.w.prices.item(0,5).setText('999')
        error.assert_called_once()
        self.assertEqual(self.w.budget.relation_quantity('rp'),Decimal('8'))
        self.assertEqual(self.w.budget._relation('rp').quantity,Decimal('2'))

    def test_invalid_cell_rolls_back_without_history_entry(self):
        self.load_native()
        before = dumps(self.w.budget)
        with patch.object(self.w,'_error'):
            self.w.prices.item(0,6).setText('NaN')
        self.assertEqual(dumps(self.w.budget),before)
        self.assertFalse(self.w._undo)

    def test_keyboard_edit_and_delete_key_do_not_remove_relation(self):
        from PySide6.QtTest import QTest
        self.load_native()
        self.w.show_prices()
        self.w.prices.setCurrentCell(0,5)
        self.w.prices.setFocus()
        self.app.processEvents()
        QTest.keyClick(self.w.prices,Qt.Key.Key_F2)
        self.app.processEvents()
        edit = QApplication.focusWidget()
        from PySide6.QtWidgets import QLineEdit
        self.assertIsInstance(edit,QLineEdit)
        QTest.keyClick(edit,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(edit,Qt.Key.Key_Delete)
        QTest.keyClicks(edit,'4')
        QTest.keyClick(edit,Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(len(self.w.budget.relations),2)
        self.assertEqual(self.w.budget._relation('rp').quantity,Decimal('4'))

    def test_repeated_concept_has_independent_measurements(self):
        path = self.load_native(True)
        b = self.w.budget
        b.add_relation(BudgetRelation('R','P','9',3,id='rp2'))
        b.add_measurement(BudgetMeasurement('rp2','Segunda aparición','7',id='m3'))
        save_budget(b,path)
        self.w.load_path(path)
        self.w.prices.setCurrentCell(2,0)
        self.assertEqual(self.w.selected_relation,'rp2')
        shown = [i for i in range(self.w.measurements_table.rowCount()) if not self.w.measurements_table.isRowHidden(i)]
        self.assertEqual(len(shown),1)
        self.assertEqual(self.w.measurements_table.item(shown[0],0).text(),'Segunda aparición')
        self.w.measurements_table.item(shown[0],1).setText('11')
        self.assertEqual(self.w.budget.relation_quantity('rp2'),Decimal('11'))
        self.assertEqual(self.w.budget.relation_quantity('rp'),Decimal('8'))

    def test_bc3_formula_edit_save_and_original_protection(self):
        path = self.load_bc3()
        original = path.read_bytes()
        self.assertEqual(self.w.text_editor.toPlainText(),'Texto importado.')
        self.w.measurements_table.item(1,5).setText('b*2')
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('6.02'))
        self.assertEqual(self.w.measurements_table.item(2,7).text(),'3.01')
        with patch.object(self.w,'_error'):
            self.w.measurements_table.item(1,5).setText('1/0')
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('6.02'))
        self.w.path = self.root/'edited.json'
        self.assertTrue(self.w.save())
        self.w.load_path(self.w.path)
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('6.02'))
        self.assertEqual(path.read_bytes(),original)

    def test_text_flush_selection_undo_and_persistence(self):
        path = self.load_native()
        self.w.text_editor.setPlainText('Texto cambiado ñ')
        self.w.prices.setCurrentCell(1,0)
        self.assertEqual(self.w.budget.concepts['P'].text,'Texto cambiado ñ')
        self.assertEqual(self.w.active_concept,'Q')
        self.assertEqual(self.w.text_editor.toPlainText(),'Otra descripción')
        self.w.undo()
        self.assertEqual(self.w.budget.concepts['P'].text,'Texto inicial')
        self.w.redo()
        self.w.text_editor.setPlainText('Nuevo Q')
        self.assertTrue(self.w.save())
        self.w.load_path(path)
        self.assertEqual(self.w.budget.concepts['Q'].text,'Nuevo Q')

    def test_erase_imported_text_does_not_restore_original_on_reload(self):
        self.load_bc3()
        self.w.text_editor.clear()
        self.w.flush_text()
        restored = loads(dumps(self.w.budget))
        self.assertEqual(restored.concepts['P'].text,'')
        self.assertEqual(json.loads(dumps(restored))['version'],3)

    def test_delete_last_native_measurement_keeps_zero_and_undo(self):
        self.load_native(True)
        self.w.show_panel('mediciones')
        self.w.measurements_table.setCurrentCell(0,0)
        self.w.delete_selected()
        self.assertEqual(self.w.budget.relation_quantity('rp'),Decimal(0))
        self.w.undo()
        self.assertEqual(self.w.budget.relation_quantity('rp'),Decimal(8))

    def test_delete_relation_from_prices_targets_correct_model_row(self):
        self.load_native()
        self.w.prices.setCurrentCell(1,0)
        self.w.show_prices()
        self.w.delete_selected()
        self.assertEqual([r.id for r in self.w.budget.relations],['rp'])
        self.w.undo()
        self.assertEqual([r.id for r in self.w.budget.relations],['rp','rq'])

    def test_new_add_concepts_relations_measurements_via_dialogs(self):
        self.w.new_budget()
        values = iter([('R','0'),('P','5')])
        def concept(dialog):
            code,price = next(values)
            dialog.code.setText(code); dialog.price.setText(price)
            return QDialog.DialogCode.Accepted
        with patch.object(ConceptDialog,'exec',concept):
            self.w.add_concept(); self.w.add_concept()
        def relation(dialog):
            dialog.parent_code.setCurrentText('R'); dialog.child_code.setCurrentText('P')
            dialog.quantity.setText('2')
            return QDialog.DialogCode.Accepted
        with patch.object(RelationDialog,'exec',relation):
            self.w.add_relation()
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('10'))
        def measurement(dialog):
            dialog.n.setText('3'); dialog.length.setText('2')
            return QDialog.DialogCode.Accepted
        with patch.object(MeasurementDialog,'exec',measurement):
            self.w.add_measurement()
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('30'))
        self.w.undo()
        self.assertEqual(BudgetCalculator(self.w.budget).total(),Decimal('10'))

    def test_close_project_and_failed_open_leave_workspace_consistent(self):
        self.load_native()
        self.assertTrue(self.w.close_project())
        self.assertEqual(self.w.mdi.subWindowList(),[])
        with patch.object(self.w,'_error'):
            self.assertFalse(self.w.load_path(self.root/'missing.bc3'))
        self.assertFalse(self.w.project_open)
        self.assertEqual(self.w.mdi.subWindowList(),[])


class EntryPointTests(unittest.TestCase):
    def test_process_exits_cleanly_after_opening_mdi_windows(self):
        import subprocess, sys
        script = '''
from pathlib import Path
from PySide6.QtWidgets import QApplication
from openpresto.presto_workspace import PrestoWorkspace
app = QApplication([])
window = PrestoWorkspace()
window.show()
assert window.load_path(Path('openpresto/data/presupuesto-demo.bc3'))
app.processEvents()
assert len(window.mdi.subWindowList()) == 4
window.dirty = False
window.close()
'''
        result = subprocess.run([sys.executable,'-X','faulthandler','-c',script],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_module_enters_event_loop_with_visible_window(self):
        import subprocess, sys
        script = '''
import runpy
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app = QApplication([])
def verify():
    windows = [w for w in app.topLevelWidgets() if w.isVisible() and w.inherits('QMainWindow')]
    print('VISIBLE_EMPTY_MDI' if len(windows)==1 and not windows[0].mdi.subWindowList() else 'FAILED',flush=True)
    app.quit()
QTimer.singleShot(250,verify)
runpy.run_module('openpresto',run_name='__main__')
'''
        result = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('VISIBLE_EMPTY_MDI',result.stdout)


if __name__ == '__main__':
    unittest.main()

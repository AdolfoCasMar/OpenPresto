"""Entrada del paquete de escritorio y comprobación del binario construido."""
import sys


def startup_check():
    """Small deployment check: Python/Qt, bundled resources and main panels."""
    import json
    from pathlib import Path
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from openpresto import __version__
    from openpresto.mdi_workspace import PrestoWorkspace
    from openpresto.calculations import calculator_for
    report=Path(sys.argv[2]);app=QApplication([sys.argv[0]])
    app.setOrganizationName('OpenPrestoPackageCheck');app.setApplicationName('StartupCheck')
    class CheckedWorkspace(PrestoWorkspace):
        def _error(self,error): raise RuntimeError(str(error))
    window=CheckedWorkspace();window.show()
    def verify():
        try:
            import openpresto
            sample=Path(openpresto.__file__).parent/'data'/'presupuesto-demo.bc3'
            assert window.load_path(sample)
            app.processEvents()
            assert all(key in window.windows for key in ('precios','conceptos','mediciones','texto'))
            assert str(calculator_for(window.budget).total())=='3.02'
            result=dict(ok=True,version=__version__,frozen=bool(getattr(sys,'frozen',False)),
                        qt_platform=app.platformName(),panels=4,total='3.02')
            code=0
        except Exception:
            import traceback
            result=dict(ok=False,error=traceback.format_exc());code=1
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        window.dirty=False;window.close();app.exit(code)
    QTimer.singleShot(200,verify)
    return app.exec()


def smoke_test():
    import json
    import tempfile
    from pathlib import Path
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox, QLineEdit
    import openpresto
    from openpresto.presto_workspace import PrestoWorkspace
    from openpresto.storage import save_budget, load_budget
    from openpresto.calculations import BudgetCalculator
    from openpresto.bc3_exporter import save_bc3

    report = Path(sys.argv[2])
    # Headless checks must expose Qt dialogs to the test driver. Native macOS
    # alert sheets do not appear as QMessageBox widgets in offscreen mode.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs,True)
    app = QApplication([sys.argv[0]])
    app.setOrganizationName('OpenPrestoPackageCheck')
    app.setApplicationName('SmokeTest')
    from PySide6.QtCore import QSettings
    QSettings().setValue('numbers/decimal_separator','.')
    window = PrestoWorkspace()
    window.show()

    def verify():
        try:
            assert window.isVisible()
            assert not window.mdi.subWindowList()
            sample = Path(openpresto.__file__).parent / 'data' / 'presupuesto-demo.bc3'
            assert window.load_path(sample)
            assert len(window.mdi.subWindowList()) == 4
            total = BudgetCalculator(window.budget).total()
            assert str(total) == '3.02'
            with tempfile.TemporaryDirectory() as folder:
                project = Path(folder) / 'prueba.json'
                save_budget(window.budget, project)
                assert BudgetCalculator(load_budget(project)).total() == total
                observed_totals = {}
                cases = Path(openpresto.__file__).parent / 'data' / 'alpha-cases'
                for name, expected in [('simple','25.00'), ('reuse','21.00'),
                                       ('dimensions','80.00'), ('rounding','4.00'), ('factor_text','17.00')]:
                    assert window.load_path(cases / (name + '.bc3'), observed_presto88=True)
                    value = BudgetCalculator(window.budget).total()
                    assert str(value) == expected, (name, str(value))
                    save_budget(window.budget, project)
                    assert window.load_path(project)
                    assert BudgetCalculator(window.budget).total() == value
                    exchange = Path(folder) / (name + '.bc3')
                    save_bc3(window.budget, exchange)
                    assert window.load_path(exchange, observed_presto88=True)
                    assert BudgetCalculator(window.budget).total() == value
                    observed_totals[name] = str(value)
                formula_sample = Path(openpresto.__file__).parent / 'data' / 'medicion-formula-demo.openpresto.json'
                assert window.load_path(formula_sample)
                assert str(BudgetCalculator(window.budget).total()) == '64.00'
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert str(BudgetCalculator(window.budget).total()) == '64.00'
                annul_sample = Path(openpresto.__file__).parent / 'data' / 'medicion-anulada-demo.openpresto.json'
                assert window.load_path(annul_sample)
                assert str(BudgetCalculator(window.budget).total()) == '48.00'
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert window.budget.measurements[0].annulled_dimensions == ('height',)
                assert str(BudgetCalculator(window.budget).total()) == '48.00'
                precision_sample = Path(openpresto.__file__).parent / 'data' / 'medicion-precision-demo.openpresto.json'
                assert window.load_path(precision_sample)
                assert str(BudgetCalculator(window.budget).total()) == '4.04'
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert str(window.budget.measurements[0].length) == '1.005'
                assert window.budget.concepts['ITEM'].measurement_decimals == 2
                assert str(BudgetCalculator(window.budget).total()) == '4.04'
                certification_sample = Path(openpresto.__file__).parent / 'data' / 'certificacion-demo.openpresto.json'
                assert window.load_path(certification_sample)
                window.show_panel('certificacion')
                assert window.certification_table.rowCount() == 1
                assert window.certification_table.item(0,6).text() == '50.00'
                window.certification_table.item(0,4).setText('5')
                assert window.certification_table.item(0,6).text() == '62.50'
                window.undo()
                assert window.certification_table.item(0,6).text() == '50.00'
                assert str(BudgetCalculator(window.budget).total()) == '125.00'
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert window.certification_table.item(0,6).text() == '50.00'
                phase_sample = Path(openpresto.__file__).parent / 'data' / 'certificacion-fases-demo.openpresto.json'
                from openpresto.certification_phases import CertificationSchedule
                window._transaction(lambda: setattr(window.budget, 'certification_schedule',
                    CertificationSchedule('2026-10-15', ('2026-11-30',), 1)))
                window.show_panel('certificacion-fases')
                window.certification_phase_panel.table.item(0,3).setText('2')
                assert not window.budget.certified_quantities
                assert window.certification_phase_panel.table.item(0,7).text() == '25.00'
                window.undo()
                assert window.certification_table.item(0,6).text() == '50.00'
                assert window.load_path(phase_sample)
                window.show_panel('certificacion-fases')
                panel = window.certification_phase_panel
                assert panel.table.item(0,7).text() == '62.50'
                from openpresto.budget import Budget, BudgetConcept, BudgetError
                unsupported = Budget('M%10')
                unsupported.add_concept(BudgetConcept('M%10', base_price=10))
                try:
                    BudgetCalculator(unsupported).total()
                except BudgetError:
                    pass
                else:
                    raise AssertionError('Se ha valorado un porcentaje como precio ordinario')
                panel.phase.setCurrentIndex(2)
                panel.table.item(0,3).setText('200')
                assert panel.table.item(0,7).text() == '62.50'
                window.undo()
                assert window.budget.phase_certified_quantities[3]['cert-line'] == 100
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert panel.table.item(0,7).text() == '62.50'
                percentage_sample = Path(openpresto.__file__).parent / 'data' / 'porcentajes-demo.openpresto.json'
                from openpresto.calculations import calculator_for
                assert window.load_path(percentage_sample)
                assert str(calculator_for(window.budget).total()) == '840.73'
                window.current_code = 'PCTD'
                window.refresh()
                window.prices.item(3,6).setText('20')
                assert window.prices.item(3,7).text() == '14.02'
                assert window.prices.item(4,7).text() == '8.41'
                percentage_export = Path(folder) / 'porcentajes-editados.bc3'
                save_bc3(window.budget, percentage_export)
                window.undo()
                assert str(calculator_for(window.budget).total()) == '840.73'
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert str(calculator_for(window.budget).total()) == '840.73'
                assert window.load_path(percentage_export, observed_presto88=True)
                assert str(calculator_for(window.budget).total()) == '848.44'
                window.current_code = 'PCTD'
                window.refresh()
                assert window.prices.item(3,7).text() == '14.02'
                assert window.prices.item(4,7).text() == '8.41'
                indirect_sample = Path(openpresto.__file__).parent / 'data' / 'indirectos-demo.openpresto.json'
                window.dirty = False
                assert window.load_path(indirect_sample)
                assert str(calculator_for(window.budget).total()) == '390.22'
                indirect_export = Path(folder) / 'indirectos.bc3'
                save_bc3(window.budget, indirect_export)
                assert b'~K|' in indirect_export.read_bytes()
                assert b'390.22' in indirect_export.read_bytes()
                assert window.load_path(indirect_export, observed_presto88=True)
                assert str(calculator_for(window.budget).total()) == '390.22'
                save_budget(window.budget, project)
                assert window.load_path(project)
                assert str(calculator_for(window.budget).total()) == '390.22'
                from openpresto.bc3_importer import import_bc3, BC3ImportError
                lock_sample = Path(openpresto.__file__).parent / 'data' / 'precio-bloqueado-demo.openpresto.json'
                assert window.load_path(lock_sample)
                assert str(calculator_for(window.budget).total()) == '140.00'
                save_budget(window.budget, project)
                assert window.load_path(project)
                window.current_code = 'OVITEM'
                window.refresh()
                window.prices.item(0,6).setText('5')
                assert str(calculator_for(window.budget).total()) == '140.00'
                window.current_code = 'OVA#'
                window.refresh()
                assert window.prices.item(0,6).foreground().color().name() == '#ef7777'
                window.unlock_selected_price()
                assert str(calculator_for(window.budget).total()) == '98.00'
                window.undo()
                assert str(calculator_for(window.budget).total()) == '140.00'
                lock_export = save_bc3(window.budget, Path(folder) / 'bloqueo.bc3')
                assert any('JSON' in warning for warning in lock_export.warnings)
                lock_import = import_bc3(Path(folder) / 'bloqueo.bc3', observed_presto88=True)
                assert str(lock_import.declared_prices['OVITEM']) == '20.00'
                assert str(calculator_for(lock_import.budget).total()) == '98.00'
                assert str(calculator_for(window.budget).total()) == '140.00'
                window.unlock_selected_price()
                assert str(calculator_for(window.budget).total()) == '98.00'
                replies = []
                def reply_to_price_dialog(accept):
                    dialog = app.activeModalWidget()
                    if isinstance(dialog, QInputDialog) and dialog.windowTitle() == 'Precio calculado':
                        replies.append(dialog.textValue())
                        dialog.accept() if accept else dialog.reject()
                    else:
                        replies.append('unexpected dialog')
                        app.exit(1)
                for accept, expected in [(False, '98.00'), (True, '140.00')]:
                    QTimer.singleShot(0, lambda accepted=accept: reply_to_price_dialog(accepted))
                    window.prices.item(0,6).setText('20')
                    assert str(calculator_for(window.budget).total()) == expected
                assert replies == ['Precio bloqueado', 'Precio bloqueado']
                window.undo()
                assert str(calculator_for(window.budget).total()) == '98.00'
                window.redo()
                assert str(calculator_for(window.budget).total()) == '140.00'
                popup_actions = []
                def cancel_price_menu():
                    menu = app.activePopupWidget()
                    if isinstance(menu, QMenu):
                        popup_actions.extend(action.text() for action in menu.actions())
                        menu.close()
                    else:
                        app.exit(1)
                QTimer.singleShot(0, cancel_price_menu)
                window.show_panel('precios')
                position = window.prices.visualItemRect(window.prices.item(0,6)).center()
                window.price_context_menu(position)
                assert window.commands['desbloquear-precio'][0].text() in popup_actions
                assert str(calculator_for(window.budget).total()) == '140.00'
                adjustment_sample = Path(openpresto.__file__).parent / 'data' / 'ajuste-precio-demo.openpresto.json'
                window.dirty = False
                assert window.load_path(adjustment_sample)
                window.current_code = 'OVA#'
                window.refresh()
                adjustment_dialogs = []
                def confirm_adjustment(accept,attempt=0):
                    dialog = app.activeModalWidget()
                    if not isinstance(dialog,QMessageBox):
                        dialog=next((widget for widget in app.topLevelWidgets()
                                     if isinstance(widget,QMessageBox) and widget.isVisible()
                                     and 'Resultado: 20.02' in widget.text()),None)
                    # QMessageBox deliberately ignores window titles on macOS.
                    if isinstance(dialog, QMessageBox) and 'Resultado: 20.02' in dialog.text():
                        assert 'Resultado: 20.02' in dialog.text()
                        adjustment_dialogs.append(accept)
                        dialog.button(QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No).click()
                    elif attempt<20:
                        QTimer.singleShot(25,lambda:confirm_adjustment(accept,attempt+1))
                    else:
                        adjustment_dialogs.append('confirmation_not_visible')
                        app.exit(1)
                def enter_adjustment(accept):
                    dialog = app.activeModalWidget()
                    if isinstance(dialog, QInputDialog) and dialog.windowTitle() == 'Ajustar precio':
                        dialog.setTextValue('20')
                        QTimer.singleShot(25, lambda: confirm_adjustment(accept))
                        dialog.accept()
                    else:
                        app.exit(1)
                for accept, expected in [(False, '98.00'), (True, '140.14')]:
                    QTimer.singleShot(25, lambda accepted=accept: enter_adjustment(accepted))
                    window.commands['ajustar-precio'][0].trigger()
                    actual=str(calculator_for(window.budget).total())
                    assert actual == expected, (expected,actual,adjustment_dialogs)
                assert adjustment_dialogs == [False, True]
                window.undo()
                assert str(calculator_for(window.budget).total()) == '98.00'
                window.redo()
                assert str(calculator_for(window.budget).total()) == '140.14'
                save_budget(window.budget, project)
                window.dirty = False
                assert window.load_path(project)
                assert str(calculator_for(window.budget).total()) == '140.14'
                save_bc3(window.budget, Path(folder) / 'ajuste.bc3')
                assert str(calculator_for(import_bc3(Path(folder) / 'ajuste.bc3', observed_presto88=True).budget).total()) == '140.14'
                guarded = Path(folder) / 'configuracion-no-aplicada.bc3'
                guarded.write_bytes(percentage_export.read_bytes() + b'~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|5|\r\n')
                for profile in (False, True):
                    try:
                        import_bc3(guarded, observed_presto88=profile)
                    except BC3ImportError:
                        pass
                    else:
                        raise AssertionError('Configuración ~K no aplicada aceptada')
            from openpresto import resource_hours
            from openpresto.commands import ProjectSession
            from openpresto.storage import loads, dumps
            hours_demo = Path(openpresto.__file__).parent / 'data' / 'resource-hours-demo.openpresto.json'
            hours_budget = loads(hours_demo.read_text(encoding='utf-8'))
            hours_view = resource_hours.snapshot(hours_budget, '2026-10-31')
            assert hours_view['total'] == 435 and hours_view['unassigned'] == 75
            production_before = hours_budget.project_metadata['production_v1']
            hours_session = ProjectSession(hours_budget)
            posted_hours = next(row for row in resource_hours.validate(hours_budget) if row['status'] == 'posted')
            hours_session.execute('resource.hours.status', dict(entry_id=posted_hours['id'], status='cancelled', cancellation_date='2026-10-20', reason='Package check'))
            assert resource_hours.snapshot(hours_session.budget, '2026-10-31')['total'] == 235
            assert hours_session.budget.project_metadata['production_v1'] == production_before
            assert resource_hours.snapshot(hours_session.undo(), '2026-10-31')['total'] == 435
            assert resource_hours.validate(loads(dumps(hours_session.budget)))
            from openpresto import site_issues
            issue_demo = Path(openpresto.__file__).parent / 'data' / 'site-issues-demo.openpresto.json'
            issue_budget = loads(issue_demo.read_text(encoding='utf-8'))
            assert len(site_issues.listing(issue_budget, '2026-10-20', pending_only=True)) == 2
            assert len(site_issues.listing(issue_budget, '2026-10-20', overdue_only=True)) == 1
            issue_session = ProjectSession(issue_budget)
            issue_id = next(r['id'] for r in site_issues.validate(issue_budget) if r['reference'] == 'INC-001')
            issue_session.execute('site.issue.status', dict(issue_id=issue_id, status='resolved', date='2026-10-20', note='Package check'))
            assert not site_issues.listing(issue_session.budget, '2026-10-20', overdue_only=True)
            assert len(site_issues.listing(issue_session.undo(), '2026-10-20', overdue_only=True)) == 1
            from openpresto import quality_control
            quality_demo = Path(openpresto.__file__).parent / 'data' / 'quality-control-demo.openpresto.json'
            quality_budget = loads(quality_demo.read_text(encoding='utf-8'))
            assert [quality_control.verdict(r) for r in quality_control.entries(quality_budget)] == ['Conforme', 'No conforme', 'Pendiente de revisión', 'Anulado']
            quality_session = ProjectSession(quality_budget)
            quality_id = next(r['id'] for r in quality_control.validate(quality_budget) if r['reference'] == 'CC-001')
            quality_session.execute('quality.inspection.status', dict(inspection_id=quality_id, status='cancelled', date='2026-10-20', reason='Package check'))
            assert quality_control.verdict(quality_control.entries(quality_session.budget)[0]) == 'Anulado'
            assert quality_control.verdict(quality_control.entries(quality_session.undo())[0]) == 'Conforme'
            from openpresto.productivity import snapshot as productivity_snapshot
            productivity_demo = Path(openpresto.__file__).parent / 'data' / 'productivity-demo.openpresto.json'
            productivity_budget = loads(productivity_demo.read_text(encoding='utf-8'))
            productivity_before = dumps(productivity_budget)
            productivity_view = productivity_snapshot(productivity_budget, '2026-10-01', '2026-10-31')
            assert str(productivity_view['work_items'][0][7]) == '3.200000'
            assert productivity_view['work_items'][0][8] == 80
            assert productivity_view['work_items'][1][8] == 128
            assert productivity_view['unassigned_cost'] == 75
            assert dumps(productivity_budget) == productivity_before
            from openpresto import budget_baselines
            baseline_demo = Path(openpresto.__file__).parent / 'data' / 'budget-baselines-demo.openpresto.json'
            baseline_budget = loads(baseline_demo.read_text(encoding='utf-8'))
            baseline_id = budget_baselines.validate(baseline_budget)[0]['id']
            baseline_view = budget_baselines.comparison(baseline_budget, baseline_id, True)
            assert baseline_view['base_total'] == 500 and baseline_view['current_total'] == 570
            assert baseline_view['delta_total'] == 70 and len(baseline_view['rows']) == 1
            baseline_session = ProjectSession(baseline_budget)
            baseline_session.execute('budget.baseline.remove', dict(baseline_id=baseline_id))
            assert not budget_baselines.validate(baseline_session.budget)
            assert budget_baselines.validate(baseline_session.undo())[0]['id'] == baseline_id
            from openpresto import nonconformities, inventory_control
            integrated_demo = Path(openpresto.__file__).parent / 'data' / 'inventory-demo.openpresto.json'
            integrated_budget = loads(integrated_demo.read_text(encoding='utf-8'))
            assert len(nonconformities.validate(integrated_budget)) == 1
            linked_id = nonconformities.listing(integrated_budget)[0]['issue_id']
            integrated_session = ProjectSession(integrated_budget)
            integrated_session.execute('site.issue.status', dict(issue_id=linked_id, status='resolved', date='2026-10-20', note='Package check'))
            assert not nonconformities.listing(integrated_session.budget, pending_only=True)
            assert nonconformities.listing(integrated_session.undo(), pending_only=True)
            stock_view = inventory_control.snapshot(integrated_budget, '2026-10-20')
            assert stock_view['rows'][0][5] == 6 and stock_view['total_value'] == 600
            assert len(stock_view['movements']) == 2
            from openpresto.pzh_archive import pzh_source_bytes
            from openpresto.pzh_importer import _Reader, _import
            encoded_demo = Path(openpresto.__file__).parent / 'data' / 'pzh-header-demo.openpresto.json'
            encoded_budget = loads(encoded_demo.read_text(encoding='utf-8'))
            encoded_source = pzh_source_bytes(encoded_budget)
            encoded_reader = _Reader(encoded_source)
            assert encoded_reader.encoded_header and encoded_reader.reference_only
            assert encoded_reader.approved_phase is None
            encoded_reopened = _import(encoded_source, 'synthetic-reference.pzh').budget
            assert pzh_source_bytes(encoded_reopened) == encoded_source
            from openpresto import technical_documents, pzh_entity_texts
            technical_demo = Path(openpresto.__file__).parent / 'data' / 'technical-documents-demo.openpresto.json'
            technical_budget = loads(technical_demo.read_text(encoding='utf-8'))
            technical_entries = pzh_entity_texts.catalogue(technical_budget)
            assert len(technical_entries) == 1
            source_text = pzh_entity_texts.read(technical_budget, technical_entries[0]['code'])['text']
            assert 'Hello' in source_text and 'World' in source_text
            technical_session = ProjectSession(technical_budget)
            technical_row = technical_documents.validate(technical_session.budget)[0]
            technical_session.execute('technical.document.attach_original',dict(document_id=technical_row['id']))
            assert technical_documents.original_payload(technical_session.budget,technical_row['id'])==pzh_entity_texts.read_payload(technical_budget,technical_entries[0]['code'])['payload']
            technical_session.execute('technical.document.set', dict(document_id=technical_row['id'], reference=technical_row['reference'], title='Reviewed text', text='Native edit'))
            technical_session.execute('technical.document.copy_pzh', dict(code=technical_entries[0]['code']))
            assert technical_documents.validate(technical_session.budget)[0]['text'] == 'Native edit'
            technical_session.undo()
            assert technical_documents.validate(technical_session.budget)[0]['text'] == source_text
            from decimal import Decimal
            from openpresto import budget_phase_measurements
            phase_demo = Path(openpresto.__file__).parent / 'data' / 'budget-phases-demo.openpresto.json'
            phase_session = ProjectSession(loads(phase_demo.read_text(encoding='utf-8')))
            assert len(budget_phase_measurements.state(phase_session.budget)['lines']) == 2
            assert calculator_for(phase_session.budget).total() == Decimal('10.43')
            phase_preview = budget_phase_measurements.preview(phase_session.budget, 2)
            assert phase_preview['delta_total'] == Decimal('20.86')
            assert phase_preview['changed_relations'] == 1
            assert calculator_for(phase_session.budget).total() == Decimal('10.43')
            phase_session.execute('budget.phases.apply', dict(phase=2))
            assert calculator_for(phase_session.budget).total() == Decimal('31.29')
            phase_session.undo()
            assert calculator_for(phase_session.budget).total() == Decimal('10.43')
            window.budget = loads(phase_demo.read_text(encoding='utf-8'))
            window.current_code = window.budget.root_code
            window._reset_history()
            window._open_views()
            window.search.setText('NO_VISIBLE_MATCH')
            def accept_new_concept():
                dialog = QApplication.activeModalWidget()
                dialog.code.setText('SMOKE_NEW')
                dialog.summary.setText('Own new concept')
                dialog.price.setText('2,50')
                dialog.accept()
            QTimer.singleShot(0, accept_new_concept)
            window.add_concept()
            assert window.active_concept == 'SMOKE_NEW'
            assert window.prices.item(window.prices.currentRow(), 0).text() == 'SMOKE_NEW'
            assert not window.prices.isRowHidden(window.prices.currentRow())
            assert window.budget.concepts['SMOKE_NEW'].base_price == Decimal('2.50')
            window.undo()
            assert 'SMOKE_NEW' not in window.budget.concepts
            window.redo()
            assert 'SMOKE_NEW' in window.budget.concepts
            new_relation = next(r for r in window.budget.relations if r.child_code == 'SMOKE_NEW')
            window._reveal_relation(new_relation.id)
            old_measurements = {m.id for m in window.budget.measurements}
            def accept_new_measurement():
                dialog = QApplication.activeModalWidget()
                dialog.comment.setText('Own new measurement')
                dialog.n.setText('2,5')
                dialog.length.setText('3,2')
                dialog.accept()
            QTimer.singleShot(0, accept_new_measurement)
            window.add_measurement()
            current_key = window._measurement_keys[window.measurements_table.currentRow()]
            assert current_key[0] == 'native' and current_key[1] not in old_measurements
            assert not window.measurements_table.isRowHidden(window.measurements_table.currentRow())
            assert window.budget.relation_quantity(new_relation.id) == Decimal('8.00')
            window.undo()
            assert {m.id for m in window.budget.measurements} == old_measurements
            window.redo()
            window._reveal_measurement(current_key, new_relation.id)
            window.delete_selected()
            assert {m.id for m in window.budget.measurements} == old_measurements
            assert window.measurements_table.currentRow() == -1
            window.undo()
            assert current_key[1] in {m.id for m in window.budget.measurements}
            assert window._measurement_keys[window.measurements_table.currentRow()] == current_key
            assert window.mdi.activeSubWindow() is window.windows['mediciones']
            window.redo()
            assert {m.id for m in window.budget.measurements} == old_measurements
            window._reveal_relation(new_relation.id)
            def accept_duplicate_concept():
                dialog=QApplication.activeModalWidget()
                assert isinstance(dialog,QInputDialog)
                dialog.setTextValue('SMOKE_COPY');dialog.accept()
            QTimer.singleShot(0,accept_duplicate_concept)
            window.duplicate_active_concept()
            assert window.active_concept=='SMOKE_COPY'
            assert window.mdi.activeSubWindow() is window.windows['conceptos']
            assert not any(r.child_code=='SMOKE_COPY' for r in window.budget.relations)
            window.undo()
            assert 'SMOKE_COPY' not in window.budget.concepts
            window.redo()
            assert window.active_concept=='SMOKE_COPY'
            retention_demo=Path(openpresto.__file__).parent/'data'/'retenciones-demo.openpresto.json'
            assert window.load_path(retention_demo)
            window.section_ui.ribbon.show_view('gestion:retention_openings')
            retention_panel=window.panels['gestion'][1].retention_openings
            from openpresto.retention_openings import opening_balances
            from openpresto.management_advanced import state as payment_state
            retention_id=retention_panel.rows[0][0]
            assert opening_balances(window.budget)[retention_id] is None
            def accept_retention_review():
                dialog=QApplication.activeModalWidget()
                dialog.findChild(QLineEdit,'retention-date').setText('2020-01-10')
                dialog.findChild(QLineEdit,'retention-note').setText('Own synthetic opening review')
                dialog.accept()
            QTimer.singleShot(0,accept_retention_review)
            retention_panel.edit()
            assert opening_balances(window.budget)[retention_id]=={'guarantee':Decimal('3'),'fiscal':Decimal('2')}
            assert payment_state(window.budget)['payments']==[]
            window.undo()
            assert opening_balances(window.budget)[retention_id] is None
            window.redo()
            assert opening_balances(window.budget)[retention_id]['guarantee']==Decimal('3')
            issued_demo=Path(openpresto.__file__).parent/'data'/'retenciones-emitidas-demo.openpresto.json'
            assert window.load_path(issued_demo)
            window.section_ui.ribbon.show_view('gestion:9')
            issued_panel=window.panels['gestion'][1].issued
            retention_panel=issued_panel.retention_openings
            issued_panel.tabs.setCurrentWidget(retention_panel)
            from openpresto.issued_retention_openings import opening_balances as issued_retention_balances
            from openpresto.issued_management import state as sales_state
            retention_id=retention_panel.rows[0][0]
            assert issued_retention_balances(window.budget)[retention_id] is None
            QTimer.singleShot(0,accept_retention_review)
            retention_panel.edit()
            assert issued_retention_balances(window.budget)[retention_id]=={'guarantee':Decimal('3'),'fiscal':Decimal('2')}
            assert sales_state(window.budget)['receipts']==[]
            window.undo()
            assert issued_retention_balances(window.budget)[retention_id] is None
            window.redo()
            assert issued_retention_balances(window.budget)[retention_id]['fiscal']==Decimal('2')
            auxiliary_demo=Path(openpresto.__file__).parent/'data'/'auxiliares-demo.openpresto.json'
            assert window.load_path(auxiliary_demo)
            from openpresto import agenda,concept_keywords,project_assets,planning
            assert concept_keywords.validate(window.budget)['ITEM']['terms']==['hiddenword','secondword']
            assert len(agenda.validate(window.budget))==1
            assert len(project_assets.validate(window.budget))==5
            window.section_ui.ribbon.show_view('gestion:technical_documents')
            technical_panel=window.panels['gestion'][1].technical_documents
            technical_panel.tabs.setCurrentWidget(technical_panel.assets)
            asset_panel=technical_panel.assets
            image_row=next(i for i,row in enumerate(project_assets.validate(window.budget)) if row['source']['table']==21)
            asset_panel.table.setCurrentCell(image_row,1);asset_panel.select();asset_panel.pool.waitForDone(5000);app.processEvents()
            assert asset_panel.current is not None and asset_panel.current['original']['format']=='bmp'
            assert asset_panel.current['image'] is not None and not asset_panel.current['image'].isNull()
            from openpresto import rich_documents
            from openpresto.rich_text_editor import set_runs
            from openpresto.pzh_text import rtf_rich_runs
            text_row=next(i for i,row in enumerate(project_assets.validate(window.budget)) if row['source']['table']==12)
            asset_panel.table.setCurrentCell(text_row,1);asset_panel.select();asset_panel.pool.waitForDone(5000);app.processEvents()
            assert asset_panel.current is not None and asset_panel.current['runs'] is not None
            rich_id=asset_panel.current['id'];original_text=asset_panel.current['original']['payload'];own_runs=rich_documents.from_plain('Own formatted note ñ 😀');own_runs[0].update(bold=True,underline=True,size=13.5)
            def accept_rich_text():
                dialog=QApplication.activeModalWidget();set_runs(dialog.editor,own_runs);dialog.accept()
            QTimer.singleShot(0,accept_rich_text);asset_panel.edit_rich()
            assert project_assets.read(window.budget,rich_id)['rich_text']==own_runs
            assert project_assets.read(window.budget,rich_id)['original']['payload']==original_text
            assert rtf_rich_runs(rich_documents.to_rtf(own_runs))==own_runs
            window.undo();assert 'rich_text' not in project_assets.read(window.budget,rich_id)
            window._execute('agenda.holidays.add')
            assert planning.state(window.budget)['holidays']==['2020-01-06']
            window.undo()
            assert planning.state(window.budget)['holidays']==[]
            vector_demo=Path(openpresto.__file__).parent/'data'/'dibujos-vectoriales-demo.openpresto.json'
            assert window.load_path(vector_demo)
            window.section_ui.ribbon.show_view('gestion:technical_documents')
            asset_panel=window.panels['gestion'][1].technical_documents.assets
            window.panels['gestion'][1].technical_documents.tabs.setCurrentWidget(asset_panel)
            vector_row=next(i for i,row in enumerate(project_assets.validate(window.budget)) if row['source']['table']==22)
            asset_panel.table.setCurrentCell(vector_row,1);asset_panel.select();asset_panel.pool.waitForDone(5000);app.processEvents()
            assert asset_panel.current is not None and asset_panel.current['vector']['elements']==1
            assert asset_panel.current['image'] is not None and not asset_panel.current['image'].isNull()
            assert asset_panel.current['image'].pixelColor(600,120).green()==0
            history_before=len(window._undo)
            vector_checks=[]
            def accept_vector_preview():
                from PySide6.QtWidgets import QGraphicsView,QPushButton
                dialog=QApplication.activeModalWidget()
                try:
                    view=dialog.findChild(QGraphicsView,'vector-view');before=view.transform().m11();dialog.findChild(QPushButton,'vector-zoom-in').click();vector_checks.append(view.transform().m11()>before)
                finally:dialog.accept()
            QTimer.singleShot(0,accept_vector_preview);asset_panel.open_vector()
            assert vector_checks==[True] and len(window._undo)==history_before
            picture_demo=Path(openpresto.__file__).parent/'data'/'imagenes-rtf-demo.openpresto.json'
            assert window.load_path(picture_demo)
            window.section_ui.ribbon.show_view('gestion:technical_documents')
            asset_panel=window.panels['gestion'][1].technical_documents.assets
            window.panels['gestion'][1].technical_documents.tabs.setCurrentWidget(asset_panel)
            picture_row=next(i for i,row in enumerate(project_assets.validate(window.budget)) if row['source']['table']==23)
            asset_panel.table.setCurrentCell(picture_row,1);asset_panel.select();asset_panel.pool.waitForDone(5000);app.processEvents()
            assert asset_panel.current is not None and len(asset_panel.current['rtf_pictures']['pictures'])==1
            picture_checks=[];picture_history=len(window._undo)
            def accept_rtf_picture_browser():
                dialog=QApplication.activeModalWidget()
                try:
                    dialog.pool.waitForDone(5000);app.processEvents();image=dialog.current['image'];picture_checks.append(image is not None and image.pixelColor(0,0).getRgb()==(255,0,0,255))
                finally:dialog.accept()
            QTimer.singleShot(0,accept_rtf_picture_browser);asset_panel.open_pictures()
            assert picture_checks==[True] and len(window._undo)==picture_history
            settlement_demo=Path(openpresto.__file__).parent/'data'/'liquidaciones-retenciones-demo.openpresto.json'
            assert window.load_path(settlement_demo)
            window.section_ui.ribbon.show_view('gestion:retention_settlements')
            from openpresto import retention_settlements,treasury
            from PySide6.QtWidgets import QComboBox
            def accept_settlement():
                dialog=QApplication.activeModalWidget()
                dialog.findChild(QComboBox,'retention-settlement-kind').setCurrentIndex(1)
                dialog.findChild(QLineEdit,'retention-settlement-date').setText('2020-01-12')
                dialog.findChild(QLineEdit,'retention-settlement-amount').setText('1')
                dialog.findChild(QLineEdit,'retention-settlement-reference').setText('OWN-PACKAGE-RET')
                dialog.accept()
            QTimer.singleShot(0,accept_settlement)
            window.panels['gestion'][1].retention_settlements.record()
            assert len(retention_settlements.validate(window.budget))==2
            assert sum(e['amount'] for e in treasury.snapshot(window.budget,'2020-01-12')['events'] if e['category']=='actual')==Decimal(2)
            window.undo()
            assert len(retention_settlements.validate(window.budget))==1
            from PySide6.QtCore import QPoint,QEvent,Qt
            from PySide6.QtGui import QMouseEvent
            window.section_ui.tabs.setCurrentIndex(0)
            window.default_layout()
            for key,pane in window.windows.items():
                if key not in ('precios','conceptos'):pane.hide()
            moving=window.windows['precios'];neighbor=window.windows['conceptos'];moving.setGeometry(20,30,240,200);neighbor.setGeometry(400,30,240,240);window.window_snapping=True
            def mouse(kind,point,buttons):
                button=Qt.MouseButton.LeftButton if kind!=QEvent.Type.MouseMove else Qt.MouseButton.NoButton
                app.sendEvent(moving,QMouseEvent(kind,point,moving.mapToGlobal(point),button,buttons,Qt.KeyboardModifier.NoModifier))
            mouse(QEvent.Type.MouseButtonPress,QPoint(80,15),Qt.MouseButton.LeftButton)
            mouse(QEvent.Type.MouseMove,QPoint(212,15),Qt.MouseButton.LeftButton)
            assert moving.x()+moving.width()==neighbor.x()
            mouse(QEvent.Type.MouseButtonRelease,QPoint(80,15),Qt.MouseButton.NoButton)
            report.write_text(json.dumps({'ok': True, 'version': openpresto.__version__,
                'rtf_source_picture_browser_no_history':True,'wmf_vector_preview_zoom_no_history':True,'native_rich_text_dialog_rtf_export_undo':True,'auxiliary_assets_preview_keywords_agenda':True,'actual_retention_dialog_treasury_undo':True,
                'live_window_magnet':True,'original_rtf_payload_preserved':True,
                'issued_retention_native_dialog_undo_no_cash': True,
                'retention_opening_native_dialog_undo_no_cash': True, 'duplicate_catalogue_result_visible_undo_redo': True, 'history_restores_measurement_selection_and_pane': True, 'measurement_delete_visible_selection_undo': True, 'new_measurement_visible_undo': True, 'new_concept_visible_single_undo': True, 'budget_phase_preview_read_only': True, 'budget_phase_apply_undo': True, 'technical_document_source_copy_undo': True, 'pzh_encoded_header_original_preserved': True, 'nonconformity_issue_link_undo': True, 'inventory_cutoff_value': '600', 'budget_baseline_comparison_undo': True, 'productivity_read_only_ratios': True, 'quality_review_cancellation_undo': True, 'site_issues_resolution_undo': True, 'resource_hours_cost': '435.00', 'resource_hours_undo': True,
                'platform': app.platformName(), 'mdi_windows': 3, 'total': str(total),
                'observed_profile_totals': observed_totals, 'native_formula_total': '64.00',
                'annulled_dimension_total': '48.00', 'measurement_precision_total': '4.04',
                'certified_line_amount': '50.00', 'phased_certified_amount': '62.50',
                'unsupported_price_codes_rejected': True, 'percentage_total': '840.73',
                'edited_percentage_export_reimport_total': '848.44',
                'indirect_total_reopened': '390.22', 'indirect_export_created': True,
                'indirect_bc3_reimport_total': '390.22',
                'unapplied_K_rejected': True, 'locked_price_reopened_total': '140.00',
                'unlocked_after_resource_edit_total': '98.00',
                'locked_price_bc3_partial_export': True,
                'real_price_dialog_cancel_accept_undo_redo': True,
                'real_price_context_menu_cancel': True,
                'real_adjustment_preview_cancel_accept_undo_redo': True,
                'adjustment_json_bc3_reopened_total': '140.14'}), encoding='utf-8')
            code = 0
        except Exception as error:
            import traceback
            report.write_text(json.dumps({'ok': False, 'error': repr(error), 'traceback': traceback.format_exc()}), encoding='utf-8')
            code = 1
        window.dirty = False
        window.close()
        app.exit(code)

    QTimer.singleShot(300, verify)
    return app.exec()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] in ('--smoke-test','--startup-check'):
        try:
            result = startup_check() if sys.argv[1] == '--startup-check' else smoke_test()
        except Exception:
            import traceback
            from pathlib import Path
            Path(sys.argv[2]).write_text(traceback.format_exc(), encoding='utf-8')
            result = 1
        raise SystemExit(result)
    from openpresto.presto_workspace import main
    raise SystemExit(main())

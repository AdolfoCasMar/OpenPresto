import json,unittest
from openpresto.pzh_importer import _import
from openpresto.pzh_native_modules import KEY,results,convert_supported
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads
from openpresto.pzh_archive import pzh_source_bytes
from test_pzh_contract_offers import fixture


def entry(module,item,status='pending',detail='Previous conversion needs review'):
    return dict(module=module,item=item,status=status,detail=detail)


class PZHSelectiveConversionTests(unittest.TestCase):
    def imported(self,**options):return _import(fixture(**options),'own-selective.pzh').budget
    def seed(self,b,rows):b.project_metadata[KEY]=json.dumps(rows,ensure_ascii=False)
    def test_management_retry_retains_planning_pending_and_unknown_module_rows(self):
        b=self.imported();kept=[entry('Planificación','Plan por fases'),entry('Mediciones presupuestarias','Todas las fases','available'),entry('Future module','Original record')];self.seed(b,kept+[entry('Compras','old')]);convert_supported(b,modules=['management']);r=results(b)
        self.assertEqual([row for row in r if row['module'] in {'Planificación','Mediciones presupuestarias','Future module'}],kept);self.assertFalse(any(row['item']=='old' for row in r));self.assertTrue(any(row['module']=='Contratos y ofertas' and row['item']=='2' for row in r));self.assertEqual(results(loads(dumps(b))),r)
    def test_planning_retry_retains_management_pending_rows(self):
        b=self.imported(missing=True);convert_supported(b,modules=['management']);before=results(b);self.assertTrue(any(row['status']=='pending' for row in before));convert_supported(b,modules=['planning']);self.assertEqual([r for r in results(b) if r['module'] in {'Entidades','Contratos y ofertas'}],before)
    def test_empty_selection_is_noop_for_model_and_history(self):
        b=self.imported();self.seed(b,[entry('Planificación','Plan por fases'),entry('Compras','1')]);session=ProjectSession(b);before=dumps(session.budget);session.execute('pzh.native.convert',dict(modules=[]));self.assertEqual(dumps(session.budget),before)
    def test_retries_replace_selected_results_without_duplicate_rows(self):
        b=self.imported(missing=True);self.seed(b,[entry('Planificación','Plan por fases')]);convert_supported(b,modules=['management']);first=results(b);convert_supported(b,modules=['management']);second=results(b);self.assertEqual(first,second);keys=[(r['module'],r['item']) for r in second];self.assertEqual(len(keys),len(set(keys)))
    def test_selected_previous_success_can_be_replaced_by_pending(self):
        b=self.imported(missing=True);self.seed(b,[entry('Contratos y ofertas','2','available','Old result'),entry('Planificación','Plan por fases')]);convert_supported(b,modules=['management']);row=next(r for r in results(b) if r['module']=='Contratos y ofertas' and r['item']=='2');self.assertEqual(row['status'],'pending');self.assertIn('plantilla',row['detail'])
    def test_undo_redo_retains_all_module_results_and_exact_source(self):
        b=self.imported();self.seed(b,[entry('Planificación','Plan por fases')]);before=results(b);session=ProjectSession(b);session.execute('pzh.native.convert',dict(modules=['management']));after=results(session.budget);self.assertGreater(len(after),len(before));session.undo();self.assertEqual(results(session.budget),before);session.redo();self.assertEqual(results(session.budget),after);self.assertEqual(pzh_source_bytes(loads(dumps(session.budget))),fixture())


class PZHSelectiveConversionPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('PZHSelectiveConversion')
    def test_actual_native_copy_button_keeps_a_budget_and_supports_undo(self):
        from PySide6.QtWidgets import QPushButton
        from openpresto.mdi_workspace import PrestoWorkspace
        from openpresto.budget import Budget
        from openpresto import management
        from unittest.mock import patch
        h=PrestoWorkspace()
        try:
            h.budget=_import(fixture(),'own-selective.pzh').budget;h._reset_history();h._open_views();panel=h.panels['gestion'][1].source;button=next(b for b in panel.findChildren(QPushButton) if b.text()=='Crear copias editables de los módulos compatibles')
            with patch.object(h,'_error') as error:button.click();error.assert_not_called()
            self.assertIsInstance(h.budget,Budget);self.assertEqual(len(management.validate(h.budget)['contracts']),1);self.assertEqual(len(h._undo),1);h.undo();self.assertEqual(management.validate(h.budget)['contracts'],[]);h.redo();self.assertEqual(len(management.validate(h.budget)['contracts']),1)
        finally:h.dirty=False;h.close()

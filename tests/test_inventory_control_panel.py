import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.storage import dumps
from test_procurement_tracking import chain
from unittest.mock import patch

class InventoryPanelTests(unittest.TestCase):
    def test_period_view_export_and_date_clamping_preserve_project(self):
        app=QApplication.instance() or QApplication([]);app.setOrganizationName('OpenPrestoTests');app.setApplicationName('InventoryPeriod');host=PrestoWorkspace()
        try:
            host.budget=chain();host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3);panel=host.panels['gestion'][1].inventory_control;before=dumps(host.budget)
            panel.cut.setDate(QDate(2020,1,4));panel.start.setDate(QDate(2020,1,3));panel.tabs.setCurrentIndex(2)
            self.assertEqual(panel.period_table.item(0,3).text(),'6');self.assertEqual(panel.period_table.item(0,5).text(),'2');self.assertEqual(panel.period_table.item(0,9).text(),'8')
            with patch('openpresto.report_actions.export_report') as export:
                panel.export();self.assertEqual(export.call_args.args[1],'inventario_periodo:2020-01-03:2020-01-04:saldos')
                panel.tabs.setCurrentIndex(3);panel.export();self.assertEqual(export.call_args.args[1],'inventario_periodo:2020-01-03:2020-01-04:movimientos')
            panel.tabs.setCurrentIndex(4);self.assertEqual(panel.abc_table.item(0,0).text(),'A');self.assertEqual(panel.abc_table.item(0,5).text(),'800.00')
            with patch('openpresto.report_actions.export_report') as export:
                panel.export();self.assertEqual(export.call_args.args[1],'inventario_abc:2020-01-04:detalle:saldos')
                panel.tabs.setCurrentIndex(5);panel.zero.setChecked(True);panel.export();self.assertEqual(export.call_args.args[1],'inventario_abc:2020-01-04:resumen:todos')
            self.assertEqual(panel.abc_summary.item(0,1).text(),'1')
            panel.cut.setDate(QDate(2020,1,2));self.assertLessEqual(panel.start.date(),panel.cut.date());self.assertEqual(dumps(host.budget),before);self.assertEqual(host._undo,[])
        finally:host.dirty=False;host.close()
    def test_cutoff_refresh_preserves_model(self):
        app=QApplication.instance() or QApplication([]);app.setOrganizationName('OpenPrestoTests');app.setApplicationName('InventoryPanel');host=PrestoWorkspace()
        try:
            host.budget=chain();host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3);panel=host.panels['gestion'][1].inventory_control;before=dumps(host.budget);panel.cut.setDate(QDate(2020,1,3));self.assertEqual(panel.table.item(0,5).text(),'6');panel.cut.setDate(QDate(2020,1,1));self.assertEqual(panel.table.rowCount(),0);self.assertEqual(dumps(host.budget),before)
        finally:host.dirty=False;host.close()

if __name__=='__main__':unittest.main()

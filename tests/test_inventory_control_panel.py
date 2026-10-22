import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.storage import dumps
from test_procurement_tracking import chain

class InventoryPanelTests(unittest.TestCase):
    def test_cutoff_refresh_preserves_model(self):
        app=QApplication.instance() or QApplication([]);app.setOrganizationName('OpenPrestoTests');app.setApplicationName('InventoryPanel');host=PrestoWorkspace()
        try:
            host.budget=chain();host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3);panel=host.panels['gestion'][1].inventory_control;before=dumps(host.budget);panel.cut.setDate(QDate(2020,1,3));self.assertEqual(panel.table.item(0,5).text(),'6');panel.cut.setDate(QDate(2020,1,1));self.assertEqual(panel.table.rowCount(),0);self.assertEqual(dumps(host.budget),before)
        finally:host.dirty=False;host.close()

if __name__=='__main__':unittest.main()

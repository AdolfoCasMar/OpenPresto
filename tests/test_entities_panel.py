"""Native directory dialogs use commands and refresh the existing workspace."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QSpinBox
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.pzh_importer import _import
from openpresto.entities import validate
from openpresto.storage import dumps
from test_pzh_control import control_fixture


class EntitiesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('EntitiesPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=_import(control_fixture(),'synthetic.pzh',native_modules=True).budget
        self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3)
        self.panel=self.host.panels['gestion'][1].entities
    def tearDown(self):
        self.host.dirty=False;self.host.close()
    def test_dialog_creates_entity_through_history(self):
        def accept():
            dialog=self.app.activeModalWidget()
            if not isinstance(dialog,QDialog):return
            dialog.findChild(QLineEdit,'entity-code').setText('NEW')
            dialog.findChild(QLineEdit,'entity-name').setText('Engineer')
            dialog.findChild(QSpinBox,'entity-role').setValue(13)
            dialog.accept()
        QTimer.singleShot(0,accept);self.panel.edit(True)
        self.assertEqual(len(validate(self.host.budget)),2)
        self.assertEqual(validate(self.host.budget)[1]['name'],'Engineer')
        self.assertEqual(self.panel.table.rowCount(),2)
        self.host.undo();self.assertEqual(len(validate(self.host.budget)),1)
    def test_search_and_cancel_do_not_modify_entities(self):
        before=dumps(self.host.budget)
        self.panel.search.setText('Title');self.assertFalse(self.panel.table.isRowHidden(0))
        self.panel.search.setText('absent query');self.assertTrue(self.panel.table.isRowHidden(0))
        self.panel.search.clear();self.panel.table.setCurrentCell(0,1)
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());self.panel.edit()
        self.assertEqual(dumps(self.host.budget),before)


if __name__=='__main__':unittest.main()

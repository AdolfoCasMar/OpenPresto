"""Control views export the selected date and table without changing data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.reports import report_table,report_csv
from openpresto.storage import dumps
from test_cost_control import project
from test_treasury import invoice


class CostControlPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('CostControlPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();invoice(self.host.budget)
        self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3)
        self.panel=self.host.panels['gestion'][1].cost_control
    def tearDown(self):
        self.host.dirty=False;self.host.close()
    def test_cut_updates_document_selection_without_changes(self):
        before=dumps(self.host.budget);self.panel.cut.setDate(QDate(2020,1,31))
        self.assertEqual(self.panel.documents.rowCount(),1);self.assertEqual(self.panel.concepts.rowCount(),1)
        self.panel.cut.setDate(QDate(2019,12,31));self.assertEqual(self.panel.documents.rowCount(),0)
        self.assertEqual(dumps(self.host.budget),before)
    def test_each_view_exports_the_same_date_and_rows(self):
        self.panel.cut.setDate(QDate(2020,1,31))
        for index,suffix in ((0,''),(1,':conceptos'),(2,':documentos')):
            self.panel.tabs.setCurrentIndex(index);kind='control_economico:2020-01-31'+suffix
            with patch('openpresto.report_actions.export_report') as export:self.panel.export()
            export.assert_called_once_with(self.host,kind)
            headers,rows=report_table(self.host.budget,kind)
            self.assertTrue(rows);self.assertEqual(len(headers),len(rows[0]));self.assertTrue(report_csv(self.host.budget,kind))
        with self.assertRaises(ValueError):report_table(self.host.budget,'control_economico:2020-01-31:unknown')


if __name__=='__main__':unittest.main()

"""Treasury filters and export preserve the selected scenario without edits."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.storage import dumps
from openpresto.reports import report_table,report_csv
from test_treasury import budget,invoice


class TreasuryPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('TreasuryPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=budget();invoice(self.host.budget,kind='proforma')
        self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3)
        self.panel=self.host.panels['gestion'][1].treasury
    def tearDown(self):
        self.host.dirty=False;self.host.close()
    def test_proforma_filter_and_date_cut_are_read_only(self):
        before=dumps(self.host.budget);self.panel.cut.setDate(QDate(2020,1,31))
        self.assertEqual(self.panel.details.rowCount(),0)
        self.panel.proformas.setChecked(True);self.assertEqual(self.panel.details.rowCount(),2)
        self.panel.cut.setDate(QDate(2019,12,31));self.assertEqual(self.panel.details.rowCount(),0)
        self.assertEqual(dumps(self.host.budget),before)
    def test_export_uses_selected_cut_and_scenario(self):
        self.panel.cut.setDate(QDate(2020,1,31));self.panel.proformas.setChecked(True)
        with patch('openpresto.report_actions.export_report') as export:
            self.panel.export()
        export.assert_called_once_with(self.host,'tesoreria:2020-01-31:+proformas')
        headers,rows=report_table(self.host.budget,'tesoreria:2020-01-31:+proformas')
        self.assertEqual(len(headers),len(rows[0]));self.assertIn('105',report_csv(self.host.budget,'tesoreria:2020-01-31:+proformas'))
        with self.assertRaises(ValueError):report_table(self.host.budget,'tesoreria:2020-01-31:unknown')

    def test_aging_filters_and_selected_export_do_not_mutate_project(self):
        before=dumps(self.host.budget);self.panel.cut.setDate(QDate(2020,3,2));self.assertEqual(self.panel.aging.rowCount(),0)
        self.panel.proformas.setChecked(True);self.assertEqual(self.panel.aging.rowCount(),2)
        ordinary=next(i for i in range(2) if self.panel.aging.item(i,4).text()=='Ordinario');self.assertEqual(self.panel.aging.item(ordinary,6).text(),'105.00')
        self.panel.tabs.setCurrentIndex(2)
        with patch('openpresto.report_actions.export_report') as export:
            self.panel.export();export.assert_called_with(self.host,'antiguedad:2020-03-02:resumen:+proformas')
            self.panel.tabs.setCurrentIndex(3);self.panel.export();export.assert_called_with(self.host,'antiguedad:2020-03-02:detalle:+proformas')
        self.assertEqual(dumps(self.host.budget),before);self.assertEqual(self.host._undo,[])


if __name__=='__main__':unittest.main()

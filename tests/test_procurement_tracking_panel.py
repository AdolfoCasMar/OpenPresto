"""The active tracking view and filters are preserved in export."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.storage import dumps
from openpresto.reports import report_table
from test_procurement_tracking import chain


class ProcurementTrackingPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('ProcurementTrackingPanel')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=chain(via=6,direct=4);self.host._reset_history();self.host._open_views();self.host.section_ui.tabs.setCurrentIndex(3)
        self.panel=self.host.panels['gestion'][1].procurement_tracking
    def tearDown(self):
        self.host.dirty=False;self.host.close()
    def test_pending_filter_does_not_change_data_or_hide_traceability(self):
        before=dumps(self.host.budget);self.panel.cut.setDate(QDate(2020,1,31))
        self.assertEqual(self.panel.orders.rowCount(),0);self.assertEqual(self.panel.links.rowCount(),3)
        self.panel.pending.setChecked(False);self.assertEqual(self.panel.orders.rowCount(),1)
        self.panel.cut.setDate(QDate(2020,1,1));self.assertEqual(self.panel.deliveries.rowCount(),0)
        self.assertEqual(dumps(self.host.budget),before)
    def test_export_uses_active_view_and_pending_filter(self):
        self.panel.cut.setDate(QDate(2020,1,31))
        for index,suffix in ((0,'pedidos:pendientes'),(1,'albaranes:pendientes'),(2,'trazabilidad')):
            self.panel.tabs.setCurrentIndex(index);kind='seguimiento_compras:2020-01-31:'+suffix
            with patch('openpresto.report_actions.export_report') as export:self.panel.export()
            export.assert_called_once_with(self.host,kind)
            headers,rows=report_table(self.host.budget,kind)
            if rows:self.assertEqual(len(headers),len(rows[0]))
        with self.assertRaises(ValueError):report_table(self.host.budget,'seguimiento_compras:2020-01-31:trazabilidad:pendientes')


if __name__=='__main__':unittest.main()

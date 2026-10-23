import os,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QToolBar,QDialog,QComboBox,QLineEdit
from openpresto.storage import dumps
from test_procurement_tracking import chain


class ReferenceWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('ReferenceWorkspace')
    def setUp(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        self.host=PrestoWorkspace();self.host.budget=chain();self.host._reset_history();self.host.show();self.host._open_views();self.app.processEvents()
    def tearDown(self):self.host.dirty=False;self.host.close();self.host.deleteLater();self.app.processEvents()
    def test_compact_ribbon_and_four_pane_geometry_preserve_model(self):
        host=self.host;before=dumps(host.budget)
        self.assertEqual(host.toolBarArea(host.section_ui.context),Qt.ToolBarArea.BottomToolBarArea)
        self.assertEqual(len(host.mdi.subWindowList()),4);self.assertIs(host.budget_stack.currentWidget(),host.budget_structure)
        left=host.windows['precios'].geometry();right=host.windows['conceptos'].geometry();measure=host.windows['mediciones'].geometry();text=host.windows['texto'].geometry()
        self.assertEqual(right.x(),left.width());self.assertEqual(measure.y(),left.height());self.assertEqual(text.y(),measure.y());self.assertEqual(measure.width()+text.width(),left.width())
        self.assertEqual(dumps(host.budget),before)
    def test_purchase_buttons_filter_by_kind_without_posting_or_reindexing(self):
        host=self.host;panel=host.management_panel;before=dumps(host.budget)
        for kind in ('order','delivery','invoice'):
            host.section_ui.ribbon.show_view('purchase:'+kind);table=panel.tables['documents']
            self.assertEqual(panel.document_filter.currentData(),kind)
            visible=[i for i in range(table.rowCount()) if not table.isRowHidden(i)]
            self.assertTrue(visible);self.assertTrue(all(panel._document_kinds[i]==kind for i in visible));self.assertIn(table.currentRow(),visible)
        panel.set_document_filter(None);self.assertTrue(all(not table.isRowHidden(i) for i in range(table.rowCount())))
        self.assertEqual(dumps(host.budget),before);self.assertEqual(host._undo,[])
    def test_nested_attachment_route_selects_actual_panel(self):
        host=self.host;host.section_ui.ribbon.show_view('gestion:technical_documents:assets');parent=host.management_panel.technical_documents
        self.assertIs(host.management_panel.tabs.currentWidget(),parent);self.assertIs(parent.tabs.currentWidget(),parent.assets)

    def test_new_document_is_visible_when_its_type_changes_from_the_filter(self):
        host=self.host;host.section_ui.ribbon.show_view('purchase:order');panel=host.management_panel
        def accept(dialog):
            kind=dialog.findChild(QComboBox,'document-kind');self.assertEqual(kind.currentData(),'order');kind.setCurrentIndex(kind.findData('invoice'))
            dialog.findChild(QLineEdit,'document-reference').setText('OWN NEW INVOICE');return QDialog.DialogCode.Accepted
        with patch('openpresto.management_panel.QDialog.exec',new=accept):
            panel.document(supplier_id='sup',rows=[dict(code='MAT',quantity='1',unit_price='10',source_document=None,source_index=None)])
        self.assertEqual(panel.document_filter.currentData(),'invoice');table=panel.tables['documents'];self.assertFalse(table.isRowHidden(table.currentRow()));self.assertEqual(table.item(table.currentRow(),1).text(),'OWN NEW INVOICE')
        self.assertEqual(len(host._undo),1);host.undo();self.assertFalse(any(table.item(i,1).text()=='OWN NEW INVOICE' for i in range(table.rowCount())))

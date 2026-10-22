import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from openpresto.app import MainWindow


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.open_demo()

    def tearDown(self):
        self.window.close()

    def test_open_search_selection_and_numeric_sort(self):
        self.assertEqual(self.window.proxy.rowCount(), 7)
        self.window.search.setText('pintura')
        self.assertEqual(self.window.proxy.rowCount(), 1)
        self.window.table.setCurrentIndex(self.window.proxy.index(0, 0))
        self.assertIn('dos manos', self.window.details.toPlainText())
        self.window.search.clear()
        self.window.table.sortByColumn(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(self.window.proxy.index(0, 0).data(), '03.01')

    def test_copy_preserves_all_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'copia.bc3'
            self.assertTrue(self.window.write_export(str(target), self.window.document.raw))
            self.assertEqual(target.read_bytes(), self.window.document.raw)

    def test_failed_open_keeps_previous_document(self):
        previous = self.window.document
        with patch.object(QMessageBox, 'warning'):
            self.assertFalse(self.window.load_path('/does/not/exist.bc3'))
        self.assertIs(self.window.document, previous)

    def test_source_cannot_be_overwritten(self):
        with patch.object(QMessageBox, 'warning'):
            self.assertFalse(self.window.write_export(str(self.window.source_path), b'changed'))


if __name__ == '__main__':
    unittest.main()

"""Navigation reuses tables; edits and undo/redo must invalidate them."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from openpresto.pzh_importer import _import
from openpresto.calculations import calculator_for
from openpresto.percentage_calculations import set_percentage_rate
from test_pzh_percentages import fixture


class WorkspaceRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('OpenPrestoTests')
        cls.app.setApplicationName('WorkspaceRefresh')

    def setUp(self):
        self.host=PrestoWorkspace()
        self.host.budget=_import(fixture(),'synthetic.pzh').budget
        self.host._reset_history()
        self.host._open_views()

    def tearDown(self):
        self.host.dirty=False
        self.host.close()

    def test_enter_and_up_reuse_global_tables_and_restore_selection(self):
        h=self.host
        first=h.concepts_table.item(0,0)
        with patch.object(h,'_render_measurements',wraps=h._render_measurements) as measurements, patch.object(h,'_render_certification',wraps=h._render_certification) as certification:
            h.enter_concept(0,0)
            self.assertEqual(h.current_code,'ITEM')
            h.go_up()
            self.assertEqual(h.current_code,'ROOT')
            self.assertEqual(h.selected_relation,h._visible_relations[0].id)
        measurements.assert_not_called()
        certification.assert_not_called()
        self.assertIs(h.concepts_table.item(0,0),first)

    def test_edit_undo_and_redo_refresh_data_and_amounts(self):
        h=self.host
        with patch.object(h,'_render_measurements',wraps=h._render_measurements) as measurements:
            set_percentage_rate(h.budget,'M%10','20')
            h._changed()
            self.assertEqual(calculator_for(h.budget).total(),Decimal('84.07'))
            h.undo()
            self.assertEqual(calculator_for(h.budget).total(),Decimal('77.06'))
            h.redo()
            self.assertEqual(calculator_for(h.budget).total(),Decimal('84.07'))
            self.assertEqual(measurements.call_count,3)
        from openpresto.number_format import display
        self.assertEqual(h.prices.item(0,7).text(),display(Decimal('84.07')))

    def test_decimal_preference_invalidates_display(self):
        from PySide6.QtCore import QSettings
        settings=QSettings()
        previous=settings.value('numbers/decimal_separator','.',type=str)
        try:
            settings.setValue('numbers/decimal_separator',',')
            self.host.refresh()
            self.assertEqual(self.host.concepts_table.item(0,4).text(),'77,06')
            settings.setValue('numbers/decimal_separator','.')
            self.host.refresh()
            self.assertEqual(self.host.concepts_table.item(0,4).text(),'77.06')
        finally:
            settings.setValue('numbers/decimal_separator',previous)

    def test_reopening_unchanged_section_does_not_rebuild_panel(self):
        h=self.host
        panel=h.panels['gestion'][1]
        with patch.object(panel,'render',wraps=panel.render) as render:
            h.section_ui.activate(3)
            h.section_ui.activate(0)
            h.section_ui.activate(3)
            self.assertEqual(render.call_count,1)
            set_percentage_rate(h.budget,'M%10','20')
            h._changed()
            self.assertEqual(render.call_count,2)


if __name__=='__main__':unittest.main()

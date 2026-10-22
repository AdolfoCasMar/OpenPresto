import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from openpresto.mdi_workspace import PrestoWorkspace
from test_production import project

class WorkflowNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('WorkflowNavigation')
    def setUp(self):
        self.host=PrestoWorkspace();self.host.budget=project();self.host._reset_history();self.host._open_views()
    def tearDown(self):self.host.dirty=False;self.host.close()
    def test_named_routes_open_real_module_panels(self):
        manager=self.host.panels['gestion'][1]
        for name in ('production','resource_hours','productivity','quality_control','nonconformities','site_issues','budget_baselines','cost_control','inventory_control','treasury','procurement_tracking','technical_documents','budget_phase_measurements'):
            self.host.section_ui.ribbon.show_view('gestion:'+name);self.assertIs(manager.tabs.currentWidget(),getattr(manager,name))
    def test_calculation_menu_shortcuts_and_original_page_indexes(self):
        self.assertEqual([self.host.section_ui.ribbon.pages.tabText(i) for i in range(4)],['Inicio','Ver','Herramientas','Seguimiento'])
        self.host.commands['Horas y equipos'][0].trigger();self.assertIs(self.host.panels['gestion'][1].tabs.currentWidget(),self.host.panels['gestion'][1].resource_hours)
        self.host.section_ui.ribbon.show_view('gestion:1');self.assertEqual(self.host.panels['gestion'][1].tabs.currentIndex(),1)

if __name__=='__main__':unittest.main()

import os,unittest
from decimal import Decimal
from dataclasses import replace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from openpresto.budget import BudgetMeasurement,BudgetError
from openpresto.measurement_operations import native_display,native_displays
from openpresto.reports import report_table
from openpresto.storage import dumps,loads
from test_production import project


def fixture():
    b=project();b.concepts['A']=replace(b.concepts['A'],measurement_decimals=2)
    for m in (BudgetMeasurement('A',n_lines='2',length='1.235',id='a1'),BudgetMeasurement('B',n_lines='3',id='b1'),BudgetMeasurement('A',n_lines='0',id='s1'),BudgetMeasurement('A',n_lines='-1',length='.50',id='a2'),BudgetMeasurement('B',n_lines='0',id='bs'),BudgetMeasurement('A',n_lines='0',id='s2'),BudgetMeasurement('A',n_lines='2',length='4',formula='a*b',annulled_dimensions=('length',),id='a3'),BudgetMeasurement('A',n_lines='0',id='s3')):b.add_measurement(m)
    for mid,kind in (('s1','1'),('s2','2'),('bs','2'),('s3','1')):b.project_metadata['measurement_kind:'+mid]=kind
    return b


class MeasurementDisplayBatchTests(unittest.TestCase):
    def test_interleaved_relations_partial_and_accumulated_subtotals(self):
        b=fixture();before=dumps(b);v=native_displays(b)
        self.assertEqual(v,{'a1':(Decimal('2.48'),'','Normal'),'b1':(Decimal('3'),'','Normal'),'s1':('',Decimal('2.48'),'Subtotal parcial'),'a2':(Decimal('-.50'),'','Normal'),'bs':('',Decimal('3'),'Subtotal acumulado'),'s2':('',Decimal('1.98'),'Subtotal acumulado'),'a3':(Decimal('2'),'','Fórmula'),'s3':('',Decimal('2'),'Subtotal parcial')})
        self.assertEqual(dumps(b),before);self.assertEqual(native_displays(loads(before)),v)
        for identity,value in v.items():self.assertEqual(native_display(b,identity),value)
    def test_each_normal_line_calculated_once_and_no_cross_call_cache(self):
        b=fixture()
        with patch.object(b,'measurement_partial',wraps=b.measurement_partial) as calc:
            first=native_displays(b);self.assertEqual(calc.call_count,4)
        b.measurements[0]=replace(b.measurements[0],n_lines='4');second=native_displays(b);self.assertEqual(second['a1'][0],Decimal('4.96'));self.assertEqual(second['s1'][1],Decimal('4.96'));self.assertEqual(first['a1'][0],Decimal('2.48'))
    def test_report_keeps_relationship_order_and_calculates_each_line_once(self):
        b=fixture()
        with patch.object(b,'measurement_partial',wraps=b.measurement_partial) as calc:headers,rows=report_table(b,'mediciones');self.assertEqual(calc.call_count,4)
        self.assertEqual([r[-1] for r in rows],['Normal','Subtotal parcial','Normal','Subtotal acumulado','Fórmula','Subtotal parcial','Normal','Subtotal acumulado']);self.assertEqual(rows[1][8],'2.48');self.assertEqual(rows[-1][8],'3');self.assertEqual(len(headers),10)
    def test_empty_and_unknown_measurement(self):
        self.assertEqual(native_displays(project()),{})
        with self.assertRaises(BudgetError):native_display(project(),'missing')
    def test_work_grows_with_lines_instead_of_repeating_previous_lines(self):
        b=project()
        for i in range(2000):b.add_measurement(BudgetMeasurement('A' if i%2==0 else 'B',n_lines='1',id=str(i)))
        with patch.object(b,'measurement_partial',wraps=b.measurement_partial) as calc:values=native_displays(b);self.assertEqual(calc.call_count,2000)
        self.assertEqual(len(values),2000)


class MeasurementDisplayBatchPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('MeasurementDisplayBatch')
    def test_panel_calculates_each_normal_line_once(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        h=PrestoWorkspace()
        try:
            h.budget=fixture();h._reset_history();h._open_views();h._refreshing=True
            with patch.object(h.budget,'measurement_partial',wraps=h.budget.measurement_partial) as calc:h._render_measurements();self.assertEqual(calc.call_count,4)
            row=h._measurement_keys.index(('native','s1'));self.assertEqual(h.measurements_table.item(row,7).text(),'2.48')
        finally:h._refreshing=False;h.dirty=False;h.close()

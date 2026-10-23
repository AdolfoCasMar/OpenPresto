import unittest
from decimal import Decimal
from copy import deepcopy
from unittest.mock import patch
from openpresto import inventory_control,management
from openpresto.reports import report_table,report_csv,report_html
from openpresto.storage import dumps
from test_procurement_tracking import chain


def view(values):
    return dict(as_of='2020-01-31',rows=[(code,'Resource '+code,'ud',Decimal(1),Decimal(0),Decimal(1),Decimal(value),'') for code,value in values])


class InventoryABCTests(unittest.TestCase):
    def test_exact_thresholds_and_summary_reconcile(self):
        source=view([('C','5'),('B','15'),('A','80')]);before=deepcopy(source)
        result=inventory_control.abc_from_snapshot(source)
        self.assertEqual([r[:2] for r in result['rows']],[('A','A'),('B','B'),('C','C')])
        self.assertEqual(result['summary'],[('A',1,Decimal(80),Decimal('80.00')),('B',1,Decimal(15),Decimal('15.00')),('C',1,Decimal(5),Decimal('5.00'))])
        self.assertEqual(sum(r[2] for r in result['summary']),result['total_value']);self.assertEqual(source,before)

    def test_threshold_crossing_stays_in_band_and_ties_use_code(self):
        result=inventory_control.abc_from_snapshot(view([('B','50'),('A','50')]))
        self.assertEqual([r[:2] for r in result['rows']],[('A','A'),('A','B')])
        result=inventory_control.abc_from_snapshot(view([('A','96'),('B','4')]))
        self.assertEqual([r[0] for r in result['rows']],['A','C'])
        self.assertEqual(result['summary'][1][1],0)

    def test_empty_and_zero_values_are_safe(self):
        result=inventory_control.abc_from_snapshot(view([]))
        self.assertEqual(result['rows'],[]);self.assertEqual(result['total_value'],0)
        result=inventory_control.abc_from_snapshot(view([('X','0')]))
        self.assertEqual(result['rows'][0][0],'C');self.assertEqual(result['rows'][0][-2:],(0,0))

    def test_display_rounding_does_not_move_threshold(self):
        result=inventory_control.abc_from_snapshot(view([('A','79.9999'),('B','15'),('C','5.0001')]))
        self.assertEqual(result['rows'][0][-1],Decimal('80.00'))
        self.assertEqual(result['rows'][1][0],'A')

    def test_native_ledger_reports_export_and_readonly_state(self):
        b=chain();before=dumps(b)
        with patch.object(management,'ledger',wraps=management.ledger) as ledger:
            result=inventory_control.abc(b,'2020-01-31');self.assertEqual(ledger.call_count,1)
        self.assertEqual(result['rows'][0][5],800)
        self.assertEqual(report_table(b,'inventario_abc:2020-01-31:detalle:saldos')[1],result['rows'])
        self.assertEqual(report_table(b,'inventario_abc:2020-01-31:resumen:saldos')[1],result['summary'])
        self.assertIn('MAT',report_csv(b,'inventario_abc:2020-01-31:detalle:saldos'))
        self.assertIn('MAT',report_html(b,'inventario_abc:2020-01-31:detalle:saldos'))
        self.assertEqual(dumps(b),before)
        management.consume(b,'MAT','2020-01-05','8','Site')
        self.assertEqual(inventory_control.abc(b,'2020-01-31')['rows'],[])
        self.assertEqual(inventory_control.abc(b,'2020-01-31',True)['rows'][0][0],'C')
        self.assertEqual(inventory_control.abc(b,'2020-01-03')['total_value'],600)

    def test_invalid_report_parameters_fail_explicitly(self):
        for kind in ('inventario_abc:bad:detalle:saldos','inventario_abc:2020-01-01:invalid:saldos','inventario_abc:2020-01-01:detalle:bad','inventario_abc:2020-01-01'):
            with self.assertRaises(ValueError):report_table(chain(),kind)


if __name__=='__main__':unittest.main()

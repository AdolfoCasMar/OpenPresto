import unittest
from decimal import Decimal
from dataclasses import replace
from openpresto import management
from openpresto.inventory_control import snapshot
from openpresto.storage import dumps,loads
from openpresto.reports import report_table
from test_procurement_tracking import chain,document

class InventoryControlTests(unittest.TestCase):
    def test_linked_invoice_never_doubles_delivery_stock(self):
        b=chain();v=snapshot(b,'2020-01-31');self.assertEqual(v['rows'][0][3:7],(Decimal(8),Decimal(0),Decimal(8),Decimal(800)));self.assertEqual(len(v['movements']),2)
        self.assertEqual(snapshot(b,'2020-01-01')['rows'],[]);self.assertEqual(snapshot(b,'2020-01-03')['rows'][0][5],6)
    def test_consumption_uses_weighted_average_and_cutoff(self):
        b=chain();management.set_document(b,'invoice','MORE','sup','2020-01-05',[dict(code='MAT',quantity='2',unit_price='200',source_document=None,source_index=None)],status='posted')
        management.consume(b,'MAT','2020-01-06','5','Site');v=snapshot(b,'2020-01-31');self.assertEqual(v['rows'][0][3:8],(Decimal(10),Decimal(5),Decimal(5),Decimal(600),Decimal('120.000000')))
        self.assertEqual(snapshot(b,'2020-01-05')['total_value'],1200)
    def test_zero_balances_optional_and_missing_records_not_invented(self):
        b=chain();management.consume(b,'MAT','2020-01-05','8','Site');self.assertEqual(snapshot(b,'2020-01-31')['rows'],[])
        row=snapshot(b,'2020-01-31',True)['rows'][0];self.assertEqual(row[5:8],(Decimal(0),Decimal(0),''))
    def test_future_drafts_and_proformas_are_not_receipts(self):
        b=chain();document(b,'invoice','DRAFT',5,date='2020-01-05',status='draft');document(b,'proforma','PF',5,date='2020-01-05');document(b,'delivery','FUTURE',5,date='2021-01-01')
        self.assertEqual(snapshot(b,'2020-01-31')['rows'][0][5],8)
    def test_current_budget_prices_do_not_replace_entry_values(self):
        b=chain();b.concepts['MAT']=replace(b.concepts['MAT'],base_price=Decimal(999));self.assertEqual(snapshot(b,'2020-01-31')['total_value'],800)
    def test_readonly_persistence_reports_and_invalid_cut(self):
        b=chain();before=dumps(b);v=snapshot(b,'2020-01-31');self.assertEqual(dumps(b),before);self.assertEqual(snapshot(loads(before),'2020-01-31'),v)
        self.assertEqual(report_table(b,'inventario:2020-01-31:movimientos')[1],v['movements'])
        for kind in ('inventario:bad:saldos','inventario:2020-01-31:bad'):
            with self.assertRaises(ValueError):report_table(b,kind)

if __name__=='__main__':unittest.main()

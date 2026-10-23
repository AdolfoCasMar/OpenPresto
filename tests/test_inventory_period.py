import unittest
from decimal import Decimal,localcontext
from openpresto import management
from openpresto.budget import BudgetError
from openpresto.inventory_control import period,PERIOD_HEADERS,MOVEMENT_HEADERS,snapshot
from openpresto.reports import report_table,report_csv,report_html
from openpresto.storage import dumps,loads
from test_procurement_tracking import chain,document


class InventoryPeriodTests(unittest.TestCase):
    def project(self):
        b=chain()
        management.set_document(b,'invoice','MORE','sup','2020-01-05',[dict(code='MAT',quantity='2',unit_price='200',source_document=None,source_index=None)],status='posted')
        management.consume(b,'MAT','2020-01-06','5','Own site')
        return b

    def test_opening_entries_consumption_and_closing_reconcile(self):
        b=self.project();view=period(b,'2020-01-05','2020-01-06')
        self.assertEqual(view['rows'][0][3:],tuple(map(Decimal,('8','800','2','400','5','600','5','600'))))
        self.assertEqual(view['totals'],dict(opening_value=Decimal(800),incoming_value=Decimal(400),consumed_value=Decimal(600),closing_value=Decimal(600)))
        self.assertEqual(view['cutoff'],snapshot(b,'2020-01-06'))
        self.assertEqual([r[0] for r in view['movements']],['2020-01-05','2020-01-06'])

    def test_inclusive_boundaries_and_linked_invoice_not_double_counted(self):
        view=period(chain(),'2020-01-03','2020-01-04')
        self.assertEqual(view['rows'][0][3:],tuple(map(Decimal,('6','600','2','200','0','0','8','800'))))
        self.assertEqual(len(view['movements']),1)
        self.assertEqual(period(chain(),'2020-01-02','2020-01-02')['rows'][0][5],Decimal(6))

    def test_exhausted_in_period_remains_visible_and_inactive_zero_is_optional(self):
        b=chain();management.consume(b,'MAT','2020-01-05','8','Own site')
        self.assertEqual(period(b,'2020-01-05','2020-01-05')['rows'][0][9:],(Decimal(0),Decimal(0)))
        self.assertEqual(period(b,'2020-01-06','2020-01-07')['rows'],[])
        self.assertEqual(len(period(b,'2020-01-06','2020-01-07',True)['rows']),1)

    def test_future_drafts_proformas_and_unrecorded_stock_are_not_invented(self):
        b=chain();document(b,'invoice','DRAFT',5,date='2020-01-05',status='draft');document(b,'proforma','PF',5,date='2020-01-05');document(b,'delivery','FUTURE',5,date='2021-01-01')
        self.assertEqual(period(b,'2020-01-05','2020-01-31')['totals']['closing_value'],Decimal(800))
        self.assertEqual(period(b,'0001-01-01','0001-01-01',True)['rows'],[])

    def test_low_decimal_precision_does_not_change_valuation(self):
        b=self.project();expected=period(b,'2020-01-05','2020-01-06')
        with localcontext() as context:
            context.prec=3
            self.assertEqual(period(b,'2020-01-05','2020-01-06'),expected)

    def test_readonly_save_reopen_and_reports(self):
        b=self.project();before=dumps(b);view=period(b,'2020-01-05','2020-01-06')
        self.assertEqual(dumps(b),before);self.assertEqual(period(loads(before),'2020-01-05','2020-01-06'),view)
        key='inventario_periodo:2020-01-05:2020-01-06:'
        self.assertEqual(report_table(b,key+'saldos'),(PERIOD_HEADERS,view['rows']))
        self.assertEqual(report_table(b,key+'movimientos'),(MOVEMENT_HEADERS,view['movements']))
        self.assertIn('MAT',report_csv(b,key+'saldos'));self.assertIn('Valor inicial',report_html(b,key+'saldos'))

    def test_invalid_intervals_and_report_selectors(self):
        b=chain()
        for start,end,zero in [('2020-02-01','2020-01-01',False),('bad','2020-01-01',False),('2020-01-01','2020-01-02',1)]:
            with self.assertRaises(BudgetError):period(b,start,end,zero)
        for kind in ['inventario_periodo:2020-01-01','inventario_periodo:2020-01-01:2020-01-02:bad']:
            with self.assertRaises(ValueError):report_table(b,kind)

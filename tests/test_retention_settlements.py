import unittest
from decimal import Decimal
from openpresto import retention_settlements as r,retention_openings as received,issued_retention_openings as issued,management,management_schedule,issued_management
from openpresto.budget import BudgetError
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads,to_dict
from openpresto.treasury import snapshot
from test_retention_openings import imported as received_budget
from test_issued_retention_openings import imported as issued_budget


def fixture(direction):
    b,rid=(received_budget if direction=='out' else issued_budget)()
    if direction=='out':management_schedule.set_opening(b,rid,'2020-01-10','30','Normal opening reviewed');received.set_opening(b,rid,'2020-01-10','1','0','Retention opening reviewed')
    else:issued_management.accept_opening(b,rid,'2020-01-10');issued.set_opening(b,rid,'2020-01-10','1','0','Retention opening reviewed')
    return b,rid


class RetentionSettlementTests(unittest.TestCase):
    def test_payments_and_receipts_reduce_only_retention_forecasts(self):
        for direction in ('out','in'):
            with self.subTest(direction=direction):
                b,rid=fixture(direction);r.record(b,direction,rid,'guarantee','2020-01-11','1','Own transfer');view=snapshot(b,'2020-01-11');actual=[e for e in view['events'] if e['category']=='actual'];self.assertEqual([(e['direction'],e['amount']) for e in actual],[(direction,Decimal(1))]);self.assertEqual(sum(e['amount'] for e in view['events'] if e['category']=='forecast'),78);self.assertEqual(issued_management.state(b)['receipts'],[]);self.assertEqual(to_dict(b)['version'],45);self.assertEqual(r.validate(loads(dumps(b))),r.validate(b))
    def test_cancellation_retains_historical_event_and_reverses_on_its_own_date(self):
        b,rid=fixture('out');r.record(b,'out',rid,'guarantee','2020-01-11','1','Transfer');entry=r.validate(b)[0];r.cancel(b,entry['id'],'2020-01-12','Transfer reversed')
        before=snapshot(b,'2020-01-11');after=snapshot(b,'2020-01-12');self.assertEqual(sum(e['amount'] for e in before['events'] if e['category']=='actual'),1);self.assertEqual(sum(e['amount'] for e in after['events'] if e['category']=='actual'),0);self.assertEqual(len([e for e in after['events'] if e['category']=='actual']),2);self.assertEqual(sum(e['amount'] for e in after['events'] if e['category']=='forecast'),79)
    def test_cancellation_and_replacement_on_same_day_reuse_available_capacity(self):
        b,rid=fixture('in');r.record(b,'in',rid,'guarantee','2020-01-11','1','First');r.cancel(b,r.validate(b)[0]['id'],'2020-01-12','Replaced');r.record(b,'in',rid,'guarantee','2020-01-12','2','Replacement');self.assertEqual(sum(e['value'] for e in r.events(b,'2020-01-12')),2)
    def test_unreviewed_source_balance_blocks_new_settlement(self):
        b,rid=received_budget();before=dumps(b)
        with self.assertRaisesRegex(BudgetError,'apertura'):r.record(b,'out',rid,'guarantee','2020-01-11','1','Transfer')
        self.assertEqual(dumps(b),before)
    def test_duplicate_reference_and_early_cancellation_are_atomic(self):
        b,rid=fixture('out');r.record(b,'out',rid,'guarantee','2020-01-11','1','Own transfer');before=dumps(b)
        with self.assertRaises(BudgetError):r.record(b,'out',rid,'guarantee','2020-01-11','1',' OWN TRANSFER ')
        self.assertEqual(dumps(b),before)
        with self.assertRaises(BudgetError):r.cancel(b,r.validate(b)[0]['id'],'2020-01-10','Too early')
        self.assertEqual(dumps(b),before)
    def test_bad_dates_amounts_types_and_precision_are_atomic(self):
        b,rid=fixture('out');before=dumps(b)
        for direction,kind,date,amount,reference in (('out','guarantee','2020-01-09','1','Before opening'),('out','guarantee','2020-01-11','2.01','Over'),('out','guarantee','2020-01-11','0.001','Precision'),('out','guarantee','2020-01-11','0','Zero'),('in','guarantee','2020-01-11','1','Wrong circuit'),('out','other','2020-01-11','1','Wrong type'),('out','fiscal','2020-01-11','1','')):
            with self.subTest(case=(direction,kind,date,amount)),self.assertRaises(BudgetError):r.record(b,direction,rid,kind,date,amount,reference)
            self.assertEqual(dumps(b),before)
    def test_opening_review_cannot_be_removed_or_overallocated_after_payment(self):
        b,rid=fixture('out');r.record(b,'out',rid,'guarantee','2020-01-11','1','Transfer');before=dumps(b)
        with self.assertRaises(BudgetError):received.clear_opening(b,rid)
        self.assertEqual(dumps(b),before)
        with self.assertRaises(BudgetError):received.set_opening(b,rid,'2020-01-10','3','0','Overallocated')
        self.assertEqual(dumps(b),before)
    def test_issued_opening_review_cannot_be_removed_after_receipt(self):
        b,rid=fixture('in');r.record(b,'in',rid,'guarantee','2020-01-11','1','Receipt');before=dumps(b)
        with self.assertRaises(BudgetError):issued.clear_opening(b,rid)
        self.assertEqual(dumps(b),before)
    def test_history_and_source_paid_flags_do_not_create_ordinary_payments(self):
        b,rid=fixture('out');s=ProjectSession(b);s.execute('retention.settlement.record',dict(direction='out',document_id=rid,kind='fiscal',date='2020-01-11',amount='1',reference='Fiscal transfer'));self.assertEqual(len(r.validate(s.budget)),1);s.undo();self.assertEqual(r.validate(s.budget),[]);s.redo();self.assertEqual(len(r.validate(s.budget)),1);self.assertEqual(sum(row[3] for row in management_schedule.forecast_rows(s.budget)),78)
    def test_schedule_edit_without_opening_module_cannot_orphan_a_payment(self):
        from test_treasury import budget,scheduled
        b=budget();scheduled(b);r.record(b,'out','inv','guarantee','2020-01-11','1','Native transfer');before=dumps(b);dues=management_schedule.state(b)['inv']['dues'];dues[-1]['kind']='fiscal'
        with self.assertRaises(BudgetError):management_schedule.set_schedule(b,'inv',dues)
        self.assertEqual(dumps(b),before)
    def test_invoice_cancellation_requires_settlement_reversal(self):
        from test_treasury import budget,scheduled
        b=budget();scheduled(b);r.record(b,'out','inv','guarantee','2020-01-11','1','Native transfer');before=dumps(b)
        with self.assertRaises(BudgetError):management.set_document_status(b,'inv','cancelled')
        self.assertEqual(dumps(b),before);r.cancel(b,r.validate(b)[0]['id'],'2020-01-12','Reversed');management.set_document_status(b,'inv','cancelled');self.assertEqual(r.validate(b)[0]['status'],'cancelled')


class RetentionSettlementPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('RetentionSettlements')
    def test_record_cancel_and_undo_through_real_dialogs(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog,QLineEdit
        from openpresto.mdi_workspace import PrestoWorkspace
        h=PrestoWorkspace()
        try:
            h.budget,rid=fixture('out');h._reset_history();h._open_views();h.section_ui.ribbon.show_view('gestion:retention_settlements');panel=h.panels['gestion'][1].retention_settlements
            self.assertIs(h.panels['gestion'][1].tabs.currentWidget(),panel)
            def accept(dialog):
                self.assertEqual(dialog.findChild(QLineEdit,'retention-settlement-date').text(),'');dialog.findChild(QLineEdit,'retention-settlement-date').setText('2020-01-11');dialog.findChild(QLineEdit,'retention-settlement-amount').setText('1,25');dialog.findChild(QLineEdit,'retention-settlement-reference').setText('Own transfer');return QDialog.DialogCode.Accepted
            with patch('openpresto.retention_settlements_panel.QDialog.exec',new=accept):panel.record()
            self.assertEqual(len(h._undo),1);self.assertEqual(r.validate(h.budget)[0]['amount'],'1.25');panel.table.setCurrentCell(0,1)
            def cancel(dialog):
                dialog.findChild(QLineEdit,'retention-cancellation-date').setText('2020-01-12');dialog.findChild(QLineEdit,'retention-cancellation-reason').setText('Own reversal');return QDialog.DialogCode.Accepted
            with patch('openpresto.retention_settlements_panel.QDialog.exec',new=cancel):panel.cancel()
            self.assertEqual(r.validate(h.budget)[0]['status'],'cancelled');h.undo();self.assertEqual(r.validate(h.budget)[0]['status'],'posted');h.undo();self.assertEqual(r.validate(h.budget),[])
        finally:h.dirty=False;h.close()

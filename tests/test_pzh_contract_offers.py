import struct,unittest
from datetime import date
from decimal import Decimal
from openpresto.pzh_importer import _import,_Reader,HEADER_BYTES
from openpresto.pzh_native_management import copy_contract,contract_proposal
from openpresto.pzh_native_modules import results
from openpresto.pzh_archive import pzh_source_bytes
from openpresto import management
from openpresto.commands import ProjectSession
from openpresto.storage import dumps,loads
from openpresto.budget import BudgetError
from test_pzh_percentages import fixture as base_fixture


def fixture(missing=False,ambiguous=False,issued=False):
    raw=base_fixture();reader=_Reader(raw)
    def code(s):return s.encode().ljust(13,b' ')
    def field(tag,fmt,value):return bytes([tag])+struct.pack('<'+fmt,value)
    def record(body,overhead,identifier):return struct.pack('<II',len(body),identifier)+bytes(overhead-8)+body
    serial=(date(2020,1,1)-date(1979,12,31)).days
    entity=record(code('SUP')+b'\x03Own supplier\0',8,1)
    def document(identifier,party,total,emit=False):return record(struct.pack('<H',serial)+code('QUOTE')+code(party)+field(2,'B',1)+field(4,'B',int(emit))+field(5,'B',1)+field(8,'d',total),20,identifier)
    def supply(identifier,party,price,explicit=False):return record(b''.join(code(s) for s in ('',party,'ITEM','QUOTE','','',''))+(field(11,'d',2) if explicit else b'')+field(14,'d',price),32,identifier)
    docs=[document(2,'SUP',24,issued)];supplies=[supply(2,'SUP',12,missing)]
    if not missing:docs.insert(0,document(1,'',0));supplies.insert(0,supply(1,'',0,True))
    if ambiguous:docs.append(document(3,'',0))
    replacements={10:(1,entity),13:(len(docs),b''.join(docs)),14:(len(supplies),b''.join(supplies)),15:(0,b'')}
    boundary=HEADER_BYTES+4+struct.unpack_from('<I',raw,HEADER_BYTES)[0];output=bytearray(raw[:boundary])
    for table in range(24):
        count,start,end=reader.tables[table];count,payload=replacements.get(table,(count,raw[start:end]));begin=len(output);output+=payload;struct.pack_into('<III',output,0x22+table*88,count,begin,len(output))
    return bytes(output)


class PZHContractOfferTests(unittest.TestCase):
    def imported(self,**options):return _import(fixture(**options),'own-contract.pzh').budget
    def test_copying_supplier_offer_uses_the_template_identity_and_exact_prices(self):
        b=self.imported();before=b.total();copy_contract(b,2);state=management.validate(b);self.assertEqual(len(state['contracts']),1);contract=state['contracts'][0];self.assertTrue(contract['id'].endswith(':contract:1'));self.assertEqual(len(contract['offers']),1);prices=next(iter(contract['offers'].values()));self.assertEqual(Decimal(prices['ITEM']),12);self.assertEqual(management.contract_amount(b,contract,prices),24);self.assertEqual(b.total(),before);self.assertEqual(management.ledger(b),[]);self.assertEqual(state['documents'],[])
        restored=loads(dumps(b));self.assertEqual(management.validate(restored),state);self.assertEqual(pzh_source_bytes(restored),fixture())
    def test_template_and_offer_copy_are_idempotent(self):
        b=self.imported();copy_contract(b,2);before=dumps(b);copy_contract(b,1);copy_contract(b,2);self.assertEqual(dumps(b),before)
    def test_automatic_conversion_reports_supplier_offer_as_available(self):
        b=_import(fixture(),'own-contract.pzh',native_modules=True).budget;rows=[r for r in results(b) if r['module']=='Contratos y ofertas'];self.assertEqual({r['item'] for r in rows},{'1','2'});self.assertTrue(all(r['status']=='available' for r in rows));self.assertEqual(len(management.validate(b)['contracts']),1)
    def test_missing_or_ambiguous_template_is_pending_without_native_contract(self):
        for options in ({'missing':True},{'ambiguous':True}):
            with self.subTest(options=options):
                b=_import(fixture(**options),'own-contract.pzh',native_modules=True).budget;offer=next(r for r in results(b) if r['module']=='Contratos y ofertas' and r['item']=='2');self.assertEqual(offer['status'],'pending');self.assertIn('plantilla',offer['detail']);self.assertEqual(management.validate(b)['contracts'],[])
    def test_issued_quotation_cannot_be_used_as_received_offer(self):
        b=self.imported(issued=True)
        with self.assertRaises(BudgetError):contract_proposal(b,2)
        contract,offers,_,_=contract_proposal(b,1);self.assertEqual(offers,{})
    def test_edited_native_contract_is_not_overwritten_when_offer_is_missing(self):
        b=self.imported();copy_contract(b,1);contract=management.validate(b)['contracts'][0];management.set_contract(b,title='Own edit',lines=contract['lines'],rounding='total',contract_id=contract['id']);data=management.state(b);data['contracts'][0]['offers']={};management.write(b,data);before=dumps(b)
        with self.assertRaisesRegex(BudgetError,'sobrescribir'):copy_contract(b,2)
        self.assertEqual(dumps(b),before)
    def test_existing_offer_edit_is_preserved(self):
        b=self.imported();copy_contract(b,2);contract=management.validate(b)['contracts'][0];supplier=next(iter(contract['offers']));management.set_offer(b,contract['id'],supplier,{'ITEM':'99'});before=dumps(b);copy_contract(b,2);self.assertEqual(dumps(b),before)
    def test_conversion_report_lists_templates_and_supplier_offers(self):
        from openpresto.reports import report_table
        b=self.imported();headers,rows=report_table(b,'pzh_native_contracts');self.assertEqual(len(headers),8);self.assertEqual({r[0] for r in rows},{1,2});offer=next(r for r in rows if r[0]==2);self.assertEqual(offer[2],'Own supplier');self.assertEqual(offer[-1],'Oferta disponible');copy_contract(b,2);_,rows=report_table(b,'pzh_native_contracts');self.assertTrue(all(r[-1]=='Ya copiado' for r in rows))
    def test_command_copy_undo_redo(self):
        session=ProjectSession(self.imported());session.execute('pzh.management.contract.copy',dict(source_id=2));self.assertEqual(len(management.validate(session.budget)['contracts']),1);session.undo();self.assertEqual(management.validate(session.budget)['contracts'],[]);session.redo();self.assertEqual(len(management.validate(session.budget)['contracts']),1)


class PZHContractOfferPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('PZHContractOffers')
    def test_source_panel_copies_selected_supplier_offer_with_undo(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        h=PrestoWorkspace()
        try:
            h.budget=_import(fixture(),'own-contract.pzh').budget;h._reset_history();h._open_views();panel=h.panels['gestion'][1].source;panel.render();grid=panel.tables['pzh_native_contracts'];row=next(i for i in range(grid.rowCount()) if grid.item(i,0).text()=='2');grid.setCurrentCell(row,0);panel.copy_contract();self.assertEqual(len(management.validate(h.budget)['contracts']),1);self.assertEqual(len(h._undo),1);h.undo();self.assertEqual(management.validate(h.budget)['contracts'],[])
        finally:h.dirty=False;h.close()

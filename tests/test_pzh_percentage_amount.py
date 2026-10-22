"""Own synthetic records: complete percentage bases and absent catalogue caches."""
import struct
import unittest
from decimal import Decimal
from dataclasses import replace
from openpresto.pzh_importer import _import, _Reader, PZHImportError, HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.calculations import calculator_for
from openpresto.storage import dumps, loads, to_dict, StorageError
from openpresto.commands import ProjectSession
from openpresto.bc3_exporter import render_bc3, BC3ExportError
from test_pzh_percentages import fixture as legacy_fixture


def fixture(orphan=False, explicit_zero=False, wrong_total=False, wrong_base=False, cascading=False):
    code=lambda text:text.encode().ljust(13,b' ')
    field=lambda tag,fmt,value:bytes([tag])+struct.pack('<'+fmt,value)
    concepts=[]
    total=114.76 if cascading else 10.43
    for name,nature,price in [('ROOT',4,total-0.01 if wrong_total else total),('ITEM',5,total),('RES',8,9.75),('%CI',9,1000 if cascading else 7)]+([('%NEXT',9,7)] if cascading else [])+([('ORPHAN',5,0 if explicit_zero else None)] if orphan else []):
        body=code(name)+field(2,'B',nature)
        if price is not None:body+=field(9,'d',price)
        concepts.append(struct.pack('<II',len(body),len(concepts))+body)
    relations=[]
    for parent,child,quantity in [('ROOT','ITEM',1),('ITEM','RES',1),('ITEM','%CI',.2 if wrong_base else .0975)]+([('ITEM','%NEXT',1.0725)] if cascading else [])+([('ORPHAN','RES',1)] if orphan else []):
        body=code(parent)+code(child)+b'  '+field(14,'d',quantity)
        i=len(relations);relations.append(struct.pack('<IIII',len(body),i,i,i)+body)
    config=_Reader(legacy_fixture()).config
    data=bytearray(HEADER_BYTES)+struct.pack('<I',len(config))+config
    for table in range(24):
        rows=concepts if table==0 else relations if table==1 else []
        start=len(data);data+=b''.join(rows)
        struct.pack_into('<III',data,34+table*88,len(rows),start,len(data))
    return bytes(data)


class PercentageAmountTests(unittest.TestCase):
    def test_exact_amount_policy_verified_against_all_source_prices(self):
        raw=fixture();b=_import(raw,'own.pzh').budget
        self.assertEqual(b.project_metadata['percentage_base_mode'],'exact-amount-v1')
        self.assertEqual(calculator_for(b).total(),Decimal('10.43'))
        percent=next(r for r in b.relations if r.child_code=='%CI')
        value=calculator_for(b).relation(percent.id)
        self.assertEqual(value.quantity,Decimal('.098'))
        self.assertEqual(value.amount,Decimal('.68'))
        self.assertEqual(pzh_source_bytes(b),raw)
        self.assertEqual(to_dict(b)['version'],36)
        self.assertEqual(calculator_for(loads(dumps(b))).total(),Decimal('10.43'))

    def test_existing_profile_retains_previous_rounding(self):
        b=_import(legacy_fixture(),'old.pzh').budget
        self.assertNotIn('percentage_base_mode',b.project_metadata)
        self.assertEqual(calculator_for(b).total(),Decimal('77.06'))

    def test_absent_unreferenced_cache_is_not_explicit_zero(self):
        b=_import(fixture(orphan=True),'own.pzh').budget
        self.assertEqual(calculator_for(b).price('ORPHAN'),Decimal('9.75'))
        self.assertIn('ORPHAN',b.project_metadata['pzh_uncached_catalog_prices'])
        with self.assertRaises(PZHImportError):_import(fixture(orphan=True,explicit_zero=True),'bad.pzh')

    def test_bad_base_or_saved_price_still_rejects(self):
        for params in ({'wrong_total':True},{'wrong_base':True}):
            with self.subTest(params=params),self.assertRaises(PZHImportError):_import(fixture(**params),'bad.pzh')

    def test_edits_undo_redo_keep_percentage_policy(self):
        session=ProjectSession(_import(fixture(),'own.pzh').budget)
        session.execute('budget.concept.edit',{'code':'RES','changes':{'base_price':'10.05'}})
        self.assertEqual(calculator_for(session.budget).total(),Decimal('10.75'))
        self.assertEqual(calculator_for(session.undo()).total(),Decimal('10.43'))
        self.assertEqual(calculator_for(session.redo()).total(),Decimal('10.75'))

    def test_invalid_policy_and_unsafe_exchange_are_rejected(self):
        b=_import(fixture(),'own.pzh').budget
        with self.assertRaises(BC3ExportError):render_bc3(b)
        b.project_metadata['percentage_base_mode']='unknown'
        with self.assertRaises(StorageError):dumps(b)

    def test_complete_policy_can_reconcile_cascading_visible_bases(self):
        b=_import(fixture(cascading=True),'own-cascade.pzh').budget
        self.assertEqual(b.project_metadata['percentage_base_mode'],'exact-amount-v1')
        self.assertEqual(calculator_for(b).total(),Decimal('114.76'))
        next_row=next(r for r in b.relations if r.child_code=='%NEXT')
        self.assertEqual(calculator_for(b).relation(next_row.id).quantity,Decimal('1.073'))
        self.assertEqual(calculator_for(loads(dumps(b))).total(),Decimal('114.76'))

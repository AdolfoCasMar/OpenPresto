"""Synthetic PZH bytes: percentage rates, displayed bases and line order."""
import struct
import json
import unittest
from decimal import Decimal
from openpresto.pzh_importer import _import, PZHImportError, HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.calculations import calculator_for
from openpresto.commands import execute
from openpresto.storage import dumps, loads


def fixture(*, wrong_base=False, wrong_total=False, factor=False, successive=False, concept_field3=False, indirect_rate=0, derived_bases=False, compressed_text=False, option4=False, root_decimals=None, quantity_decimals=3, price_decimals=2, locked=False, occurrence=False, unresolved=False, certification=None, budget_phase=False):
    def code(value):return value.encode().ljust(13,b' ')
    def field(tag,fmt,value):return bytes([tag])+struct.pack('<'+fmt,value)
    def concept(name,nature,price):
        body=code(name)+field(2,'B',nature)
        if concept_field3 and name=='ROOT':body+=b'\x03OTHER_CODE\x00'
        body+=field(9,'d',price)
        if certification and name in ('ROOT','ITEM'):
            certprice=12.34 if certification=='manual' else 999
            body+=field(10,'d',(24.68 if certification=='manual' else 154.12) if name=='ROOT' else certprice)
        if locked and name=='ITEM':body+=field(14,'B',1)
        if certification and name=='ITEM':body+=field(15,'B',1 if certification=='manual' else 3)
        return struct.pack('<II',len(body),len(concepts))+body
    total=20 if locked else 88.07 if occurrence else 92.48 if successive else 77.06
    concepts=[]
    for name,nature,price in [('ROOT',4,round(total*(1+indirect_rate/100),2)+1 if wrong_total else round(total*(1+indirect_rate/100),2)),('ITEM',5,total),('M01',8,20.01),('M02',8,10.02),('M%10',9,10)]+([('M%20',9,20)] if successive else []):
        concepts.append(concept(name,nature,price))
    relations=[]
    # Deliberately misleading index ranks: economic order is the record sequence.
    for parent,child,quantity,index in [('ROOT','ITEM',1,0),('ITEM','M01',3,3),('ITEM','M02',1,4)]+([('ITEM','M01',.5,9)] if occurrence else [])+[('ITEM','M%10',.8 if wrong_base else .8006 if occurrence else .7005,1)]+([('ITEM','M%20',.7706,2)] if successive else [])+([('GHOST','M01',1,10)] if unresolved else []):
        body=code(parent)+code(child)+(b' 0' if index==9 else b'  ')
        if factor and '%' in child:body+=field(13,'d',2)
        if not (derived_bases and '%' in child):body+=field(14,'d',quantity)
        if certification and parent=='ROOT':body+=field(15,'d',2)
        relations.append(struct.pack('<IIII',len(body),len(relations),index,len(relations))+body)
    config=b'\x018.0\x00\x02\x00\x03ROOT\x00'+(b'\x04\x01' if option4 else b'')+(b'\x06'+struct.pack('<H',root_decimals) if root_decimals is not None else b'')+bytes.fromhex('07 02 00 08 03 00 09 02 00 0a 02 00 0b 02 00 0c 02 00')+(b'\x10'+struct.pack('<d',indirect_rate) if indirect_rate else b'')+b''.join(bytes([tag,1]) for tag in range(0xef,0xf8))
    config=config.replace(b'\x08\x03\x00',b'\x08'+struct.pack('<H',quantity_decimals)).replace(b'\x0a\x02\x00',b'\x0a'+struct.pack('<H',price_decimals))
    data=bytearray(HEADER_BYTES)+struct.pack('<I',len(config))+config
    for table in range(24):
        payload=bytes.fromhex('01000000e680')  # synthetic size-prefixed LZHUF literal A
        text=struct.pack('<IIBII',17+len(payload),0,1,1,len(payload))+payload
        phase=code('ROOT')+code('ITEM')+b'  '+b'\x01'+field(2,'d',1)+field(7,'d',1)
        phase_record=struct.pack('<III',len(phase),0,0)+phase
        rows=concepts if table==0 else relations if table==1 else [text] if table==2 and compressed_text else [phase_record] if table==18 and budget_phase else []
        start=len(data);data+=b''.join(rows)
        struct.pack_into('<III',data,0x22+table*88,len(rows),start,len(data))
        if table==2 and compressed_text:data+=code('ROOT')+struct.pack('<I',start)
    return bytes(data)


class PZHPercentageTests(unittest.TestCase):
    def test_budget_only_skips_optional_converters(self):
        from unittest.mock import patch
        raw = fixture()
        with patch('openpresto.pzh_certifications.import_certifications') as cert, patch('openpresto.pzh_operations.import_operations') as operations:
            budget = _import(raw, 'synthetic.pzh', modules=set()).budget
        cert.assert_not_called()
        operations.assert_not_called()
        self.assertEqual(pzh_source_bytes(budget), raw)
        self.assertEqual(calculator_for(budget).total(), Decimal('77.06'))
        self.assertTrue(any('no seleccionado' in w for w in budget.import_warnings))

    def test_optional_failure_is_atomic_and_visible(self):
        from unittest.mock import patch
        def fail(budget, *args):
            budget.project_metadata['incomplete_change'] = 'must roll back'
            raise PZHImportError('synthetic failure')
        with patch('openpresto.pzh_certifications.import_certifications', side_effect=fail):
            result = _import(fixture(), 'synthetic.pzh', modules={'certifications'})
        self.assertNotIn('incomplete_change', result.budget.project_metadata)
        self.assertTrue(any('Certificaciones no convertido' in w for w in result.warnings))

    def test_planning_selection_excludes_management(self):
        from openpresto.pzh_operations import state
        stages = []
        result = _import(fixture(budget_phase=True), 'synthetic.pzh', modules={'planning'},
                         progress=lambda value, label: stages.append(value))
        self.assertTrue(state(result.budget)['phases'])
        self.assertEqual(state(result.budget)['documents'], [])
        self.assertEqual(stages, sorted(stages))
        self.assertEqual(stages[-1], 100)

    def test_rate_and_displayed_base_have_distinct_meanings(self):
        raw=fixture();b=_import(raw,'synthetic.pzh').budget;calc=calculator_for(b)
        r=next(r for r in b.relations if r.child_code=='M%10');row=calc.relation(r.id)
        self.assertEqual(r.quantity,Decimal('.1'))
        self.assertEqual((row.quantity,row.unit_price,row.amount),(Decimal('.701'),Decimal('10'),Decimal('7.01')))
        self.assertEqual(calc.total(),Decimal('77.06'));self.assertEqual(pzh_source_bytes(b),raw)
        self.assertEqual(calculator_for(loads(dumps(b))).total(),calc.total())

    def test_successive_percentage_uses_preceding_percentage(self):
        b=_import(fixture(successive=True),'synthetic.pzh').budget
        self.assertEqual(calculator_for(b).total(),Decimal('92.48'))
        children=[r.child_code for r in sorted((r for r in b.relations if r.parent_code=='ITEM'),key=lambda r:r.position)]
        self.assertEqual(children,['M01','M02','M%10','M%20'])

    def test_wrong_base_and_wrong_total_still_fail(self):
        for values in (dict(wrong_base=True),dict(wrong_total=True),dict(factor=True)):
            with self.subTest(values=values), self.assertRaises(PZHImportError):_import(fixture(**values),'bad.pzh')

    def test_optional_text_field_is_preserved(self):
        b=_import(fixture(concept_field3=True),'synthetic.pzh').budget
        self.assertEqual(b.project_metadata['pzh_concept_field3:ROOT'],'OTHER_CODE')
        self.assertEqual(loads(dumps(b)).project_metadata['pzh_concept_field3:ROOT'],'OTHER_CODE')

    def test_lzhuf_with_flag_one(self):
        b=_import(fixture(compressed_text=True),'synthetic.pzh').budget
        self.assertEqual(b.concepts['ROOT'].text,'A')

    def test_derived_base_and_global_indirect_costs(self):
        b=_import(fixture(derived_bases=True,indirect_rate=20),'synthetic.pzh').budget
        self.assertEqual(calculator_for(b).total(),Decimal('92.47'))
        self.assertEqual(b.indirect_config['rate'],'20.0')
        self.assertEqual(calculator_for(b).price('ITEM'),Decimal('77.06'))

    def test_reused_calculator_observes_edits(self):
        b=_import(fixture(),'synthetic.pzh').budget;calc=calculator_for(b)
        self.assertEqual(calc.total(),Decimal('77.06'))
        from openpresto.percentage_calculations import set_percentage_rate
        set_percentage_rate(b,'M%10','20')
        self.assertEqual(calc.total(),Decimal('84.07'))

    def test_optional_configuration_and_precisions(self):
        b=_import(fixture(option4=True,root_decimals=2,quantity_decimals=4,price_decimals=3),'synthetic.pzh').budget
        self.assertEqual(calculator_for(b).total(),Decimal('77.06'))
        self.assertEqual(b.root_quantity_decimals,2)
        self.assertEqual(calculator_for(b).policy.quantity_decimals,4)
        self.assertEqual(calculator_for(b).policy.price_decimals,3)

    def test_repeated_source_occurrences_are_distinct(self):
        b=_import(fixture(occurrence=True),'synthetic.pzh').budget
        self.assertEqual(len([r for r in b.relations if r.parent_code=='ITEM' and r.child_code=='M01']),2)
        self.assertEqual(calculator_for(b).total(),Decimal('88.07'))
        copied=execute(b,'pzh.operations.convert')
        self.assertEqual(calculator_for(copied).total(),Decimal('88.07'))

    def test_locked_price_is_explicit(self):
        b=_import(fixture(locked=True),'synthetic.pzh').budget
        self.assertEqual(b.locked_prices['ITEM'],Decimal('20'))
        self.assertEqual(calculator_for(b).total(),Decimal('20'))

    def test_unresolved_reference_is_archived_and_reported(self):
        result=_import(fixture(unresolved=True),'synthetic.pzh');b=result.budget
        self.assertNotIn('GHOST',b.concepts)
        self.assertEqual(json.loads(b.project_metadata['pzh_unresolved_relations'])[0]['parent'],'GHOST')
        self.assertTrue(any('REFERENCIAS SIN RESOLVER' in warning for warning in result.warnings))
        self.assertEqual(calculator_for(b).total(),Decimal('77.06'))

    def test_automatic_certification_price_ignores_stale_cache(self):
        b=_import(fixture(certification='automatic',budget_phase=True),'synthetic.pzh').budget
        self.assertEqual(b.certified_quantities['pzh-r0'],Decimal('2'))
        self.assertEqual(b.project_metadata['certification_price:pzh-r0'],'77.06')
        self.assertIsNone(b.certification_schedule)

    def test_manual_certification_price_is_preserved(self):
        b=_import(fixture(certification='manual'),'synthetic.pzh').budget
        self.assertEqual(b.project_metadata['certification_price:pzh-r0'],'12.34')

    def test_percentage_remains_editable(self):
        b=_import(fixture(),'synthetic.pzh').budget
        from openpresto.percentage_calculations import set_percentage_rate
        set_percentage_rate(b,'M%10','20')
        self.assertEqual(calculator_for(b).total(),Decimal('84.07'))


if __name__=='__main__':unittest.main()

"""Independent fixtures for populated subtotals and unphased planning."""
import struct
import unittest
from decimal import Decimal
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES,PZHImportError
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.calculations import calculator_for
from openpresto.storage import dumps,loads,to_dict
from openpresto import planning_phases
from openpresto.pzh_operations import state,rejected_records
from test_pzh_percentages import fixture


def extended_fixture(duration=1,subtotal=False):
    raw=fixture();reader=_Reader(raw)
    def code(s):return s.encode().ljust(13,b' ')
    def field(tag,fmt,value):return bytes([tag])+struct.pack('<'+fmt,value)
    replacements={}
    for table,overhead in ((0,8),(1,16)):
        rows=[]
        for offset,identifier,body in reader.records(table,overhead):
            if table==0 and body[:13]==code('ITEM'):body+=field(12,'d',10)
            if table==1 and body[:26]==code('ROOT')+code('ITEM'):
                body=body[:28]+field(2,'H',10000)+body[28:]+field(17,'d',3)+field(30,'B',duration)
            header=bytearray(raw[offset:offset+overhead]);struct.pack_into('<I',header,0,len(body));rows.append(bytes(header)+body)
        replacements[table]=(len(rows),b''.join(rows))
    body=code('ITEM')+code('SUPPLIER')+b'\x03B02\0'+field(5,'H',10000)+b'\x08Synthetic classification\0'
    replacements[11]=(1,struct.pack('<III',len(body),1,0)+body)
    if subtotal:
        rows=[]
        for identifier,quantity,kind in ((1,1,0),(2,2,2)):
            body=b'\0'+code('ITEM')+code('M01')+b'  '+b'\1'
            if kind:body+=field(1,'B',kind)
            body+=field(12,'d',quantity)
            rows.append(struct.pack('<III',len(body),identifier,identifier)+body)
        replacements[4]=(len(rows),b''.join(rows))
    boundary=HEADER_BYTES+4+struct.unpack_from('<I',raw,HEADER_BYTES)[0];output=bytearray(raw[:boundary])
    for table in range(24):
        count,start,end=reader.tables[table];count,payload=replacements.get(table,(count,raw[start:end]));begin=len(output);output+=payload
        struct.pack_into('<III',output,0x22+table*88,count,begin,len(output))
    return bytes(output)


class CompatibilityCasesTests(unittest.TestCase):
    def test_duration_mode_is_preserved_and_validated(self):
        b=_import(extended_fixture(),'synthetic.pzh').budget
        self.assertEqual(b.project_metadata['pzh_duration_locked:pzh-r0'],'1')
        self.assertEqual(calculator_for(b).total(),Decimal('77.06'))
        with self.assertRaisesRegex(PZHImportError,'duración'):_import(extended_fixture(duration=2),'synthetic.pzh')

    def test_offer_classification_is_text_not_a_byte(self):
        b=_import(extended_fixture(),'synthetic.pzh').budget
        self.assertEqual(state(b)['offers'][0]['fields']['3'],'B02')
        self.assertEqual(rejected_records(b),[])
        self.assertEqual(state(loads(dumps(b)))['offers'],state(b)['offers'])

    def test_populated_subtotal_retains_its_own_quantity(self):
        raw=extended_fixture(subtotal=True);b=_import(raw,'synthetic.pzh').budget
        self.assertEqual(len(b.measurements),3)
        self.assertEqual(calculator_for(b).total(),Decimal('77.06'))
        self.assertEqual(calculator_for(loads(dumps(b))).total(),Decimal('77.06'))
        self.assertEqual(pzh_source_bytes(b),raw)

    def test_unphased_plan_preserves_dates_and_objective_without_invented_phases(self):
        raw=extended_fixture();b=_import(raw,'synthetic.pzh',native_modules=True).budget
        data=planning_phases.validate(b)
        self.assertEqual(data['end_dates'],[]);self.assertIsNone(data['approved'])
        task=data['tasks'][0];self.assertIsNotNone(task['start']);self.assertEqual(task['phases'],{})
        self.assertEqual(Decimal(task['objective_quantity']),3)
        self.assertEqual(Decimal(task['objective_price']),10)
        self.assertEqual(to_dict(b)['version'],27)
        self.assertEqual(planning_phases.state(loads(dumps(b))),data)
        planning_phases.set_task(b,task['relation_id'],start=task['start'],objective_quantity='4',objective_price='12',phases={})
        self.assertEqual(Decimal(planning_phases.state(b)['tasks'][0]['objective_quantity']),4)
        self.assertEqual(pzh_source_bytes(b),raw)
        self.assertEqual(calculator_for(b).total(),Decimal('77.06'))


if __name__=='__main__':unittest.main()

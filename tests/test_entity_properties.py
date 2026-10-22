"""Independent synthetic cases for the examined entity field contracts."""
import struct,json,unittest
from datetime import date
from openpresto import entities,management,issued_management
from openpresto.pzh_importer import _Reader,_import,HEADER_BYTES
from openpresto.pzh_archive import pzh_source_bytes
from openpresto.pzh_operations import validate as source_state,rejected_records
from openpresto.storage import dumps,loads,to_dict,StorageError
from openpresto.commands import ProjectSession
from openpresto.budget import BudgetError
from test_pzh_control import control_fixture


def fixture(extra=b''):
    raw=control_fixture();reader=_Reader(raw);entity=next(reader.records(10,8))[2]
    serial=(date(2020,1,10)-date(1979,12,31)).days
    from openpresto.pzh_importer import _fields
    from openpresto.pzh_operations import SCHEMAS
    fields=_fields(entity[13:],SCHEMAS[10],'Own fixture');fields.update({27:123.5,29:'C:\\Reference\\own-project.pzh',30:0,36:serial,40:0});entity=entity[:13]
    for tag,value in sorted(fields.items()):
        fmt=SCHEMAS[10][tag];entity+=bytes([tag])+(value.encode()+b'\0' if fmt=='s' else struct.pack('<'+fmt,float(value) if fmt=='d' else value))
    entity+=extra
    replacement=struct.pack('<II',len(entity),1)+entity;boundary=HEADER_BYTES+4+len(reader.config);out=bytearray(raw[:boundary])
    for table in range(24):
        count,start,end=reader.tables[table];payload=replacement if table==10 else raw[start:end];begin=len(out);out+=payload;struct.pack_into('<III',out,34+table*88,count,begin,len(out))
    return bytes(out)


class EntityPropertyTests(unittest.TestCase):
    def test_source_types_dates_path_and_explicit_zero_are_native(self):
        raw=fixture();b=_import(raw,'own-properties.pzh',native_modules=True).budget;fields=source_state(b)['entities'][0]['fields'];row=entities.validate(b)[0]
        self.assertEqual(fields['29'],'C:\\Reference\\own-project.pzh');self.assertEqual(fields['30'],0);self.assertEqual(row['properties'],dict(quantity='0.0',gross_area='123.5',path=fields['29'],active=False,date='2020-01-10'))
        self.assertEqual(to_dict(b)['version'],41);self.assertEqual(entities.validate(loads(dumps(b))),entities.validate(b));self.assertEqual(pzh_source_bytes(b),raw);self.assertEqual(rejected_records(b),[])
        self.assertEqual(management.state(b)['documents'],[]);self.assertEqual(issued_management.state(b)['receipts'],[])
    def test_legacy_copy_gains_properties_without_overwriting_contact_edits(self):
        b=_import(fixture(),'own.pzh',native_modules=True).budget;data=entities.validate(b);rid=data[0]['id'];data[0].pop('properties');data[0]['name']='Own reviewed contact';entities._save(b,data);self.assertEqual(to_dict(b)['version'],28);entities.copy_pzh(b);row=entities.validate(b)[0];self.assertEqual(row['name'],'Own reviewed contact');self.assertEqual(row['id'],rid);self.assertEqual(row['properties']['date'],'2020-01-10')
    def test_property_edit_is_atomic_undoable_and_does_not_change_source_totals(self):
        b=_import(fixture(),'own.pzh',native_modules=True).budget;row=entities.validate(b)[0];original=entities.source_total_rows(b);s=ProjectSession(b);values=dict(row['properties'],quantity='2.5',gross_area='150',date=None)
        s.execute('entities.set',dict(values={'properties':values},entity_id=row['id']));self.assertEqual(entities.validate(s.budget)[0]['properties'],values);self.assertEqual(entities.source_total_rows(s.budget),original);s.undo();self.assertEqual(entities.validate(s.budget)[0]['properties'],row['properties']);s.redo();self.assertEqual(entities.validate(s.budget)[0]['properties'],values)
    def test_bad_values_rejected_without_changes(self):
        b=_import(fixture(),'own.pzh',native_modules=True).budget;row=entities.validate(b)[0];before=dumps(b)
        for key,value in (('gross_area','-1'),('quantity','NaN'),('quantity',2),('active',1),('date','2020-13-01'),('path',False)):
            with self.subTest(key=key),self.assertRaises(BudgetError):entities.set_entity(b,{'properties':dict(row['properties'],**{key:value})},row['id'])
            self.assertEqual(dumps(b),before)
    def test_unknown_nonserialized_field_does_not_get_a_guessed_type(self):
        b=_import(fixture(b'\x2a\x01'),'unknown-property.pzh',native_modules=True).budget;self.assertEqual(entities.validate(b),[]);self.assertTrue(any(r['table']==10 for r in rejected_records(b)));self.assertEqual(pzh_source_bytes(b),fixture(b'\x2a\x01'))
    def test_source_aggregate_has_explicit_label_and_never_becomes_payment(self):
        from openpresto.reports import report_table
        b=_import(fixture(),'own.pzh',native_modules=True).budget;headers,rows=report_table(b,'entity_source_totals');self.assertIn('no es movimiento nativo',headers[3]);self.assertIn('Certificación de obra',rows[0]);self.assertEqual(management.ledger(b),[])
    def test_native_properties_tamper_rejected_on_load(self):
        b=_import(fixture(),'own.pzh',native_modules=True).budget;rows=entities.validate(b);rows[0]['properties']['active']=7;b.project_metadata[entities.KEY]=json.dumps(rows)
        with self.assertRaises(StorageError):dumps(b)

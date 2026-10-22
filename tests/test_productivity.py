import unittest
from decimal import Decimal,localcontext
from dataclasses import replace
from openpresto import production,resource_hours
from openpresto.productivity import snapshot
from openpresto.storage import dumps,loads
from openpresto.reports import report_table
from test_resource_hours import project,create as hours
from test_production import create as produce


def sample():
    b=project();production.set_status(b,produce(b),'posted');resource_hours.set_status(b,hours(b),'posted');return b


class ProductivityTests(unittest.TestCase):
    def test_ratios_use_explicit_hours_and_production(self):
        b=sample();view=snapshot(b,'2026-10-01','2026-10-01');row=view['work_items'][0]
        self.assertEqual(row[4:],(Decimal('2.5'),Decimal(8),Decimal(200),Decimal('3.200000'),Decimal('80.000000'),'Comparable'))
        self.assertEqual(view['resources'][0][4],'L')
    def test_multiple_resources_share_denominator_without_double_counting_production(self):
        b=sample();resource_hours.set_status(b,hours(b,'H2','M','1','80'),'posted');v=snapshot(b,'2026-10-01','2026-10-31')
        self.assertEqual(v['work_items'][0][4:7],(Decimal('2.5'),Decimal(9),Decimal(280)))
        self.assertEqual([r[6] for r in v['resources']],[Decimal('2.5')]*2)
        self.assertEqual([r[9] for r in v['resources']],[Decimal('3.2'),Decimal('.4')])
    def test_missing_production_and_missing_hours_are_unknown_not_zero(self):
        b=sample();resource_hours.set_status(b,hours(b,'H2',relation='B'),'posted')
        produce(b,'P2',date='2026-10-02')
        v=snapshot(b,'2026-10-01','2026-10-31');row=v['work_items'][1]
        self.assertEqual(row[4],'');self.assertEqual(row[7:9],('',''));self.assertEqual(row[-1],'Sin producción registrada')
        b=project();production.set_status(b,produce(b),'posted');row=snapshot(b,'2026-10-01','2026-10-31')['work_items'][0]
        self.assertEqual(row[5:9],('','','',''));self.assertEqual(row[-1],'Sin horas registradas')
    def test_drafts_and_cancellations_excluded(self):
        b=sample();production.set_status(b,production.validate(b)[0]['id'],'cancelled','2026-10-02','Correction')
        self.assertEqual(snapshot(b,'2026-10-01','2026-10-31')['work_items'][0][-1],'Sin producción registrada')
        resource_hours.set_status(b,resource_hours.validate(b)[0]['id'],'cancelled','2026-10-02','Correction')
        produce(b,'DRAFT');hours(b,'DRAFT');self.assertEqual(snapshot(b,'2026-10-01','2026-10-31')['work_items'],[])
    def test_inclusive_same_date_window_and_outside_records(self):
        b=sample();self.assertEqual(len(snapshot(b,'2026-10-01','2026-10-01')['work_items']),1)
        self.assertEqual(snapshot(b,'2026-10-02','2026-10-31')['work_items'],[])
        for start,end in [('bad','2026-10-31'),('2026-10-02','2026-10-01')]:
            with self.assertRaises(ValueError):snapshot(b,start,end)
    def test_unassigned_costs_not_spread_into_work_items(self):
        b=sample();resource_hours.set_status(b,hours(b,'H2',hours='3',rate='25',relation=None),'posted');v=snapshot(b,'2026-10-01','2026-10-31')
        self.assertEqual(v['unassigned_cost'],75);self.assertEqual(v['unassigned'][0][-2:],(Decimal(3),Decimal(75)));self.assertEqual(v['work_items'][0][6],200)
    def test_saved_rates_and_no_factor_reapplication(self):
        b=sample();b.concepts['L']=replace(b.concepts['L'],base_price=Decimal(999));b.relations=[replace(r,factor=Decimal(3)) if r.id=='A' else r for r in b.relations]
        self.assertEqual(snapshot(b,'2026-10-01','2026-10-31')['work_items'][0][8],Decimal(80))
    def test_zero_cost_is_known_and_rounding_sums_stored_entry_costs(self):
        b=project();production.set_status(b,produce(b,quantity='1'),'posted')
        for ref,rate in [('H1','.005'),('H2','.005'),('H3','0')]:resource_hours.set_status(b,hours(b,ref,hours='1',rate=rate),'posted')
        with localcontext() as context:
            context.prec=3
            row=snapshot(b,'2026-10-01','2026-10-31')['work_items'][0];self.assertEqual(row[6],Decimal('.02'));self.assertEqual(row[8],Decimal('.020000'))
    def test_read_only_roundtrip_and_reports(self):
        b=sample();before=dumps(b);v=snapshot(b,'2026-10-01','2026-10-31');self.assertEqual(dumps(b),before);self.assertEqual(snapshot(loads(before),'2026-10-01','2026-10-31'),v)
        self.assertEqual(report_table(b,'rendimientos:2026-10-01:2026-10-31:partidas')[1],v['work_items'])
        self.assertEqual(report_table(b,'rendimientos:2026-10-01:2026-10-31:recursos')[1],v['resources'])
        self.assertEqual(report_table(b,'rendimientos:2026-10-01:2026-10-31:sin_asignar')[1],v['unassigned'])
        for kind in ('rendimientos:2026-10-01','rendimientos:a:b:bad','rendimientos:2026-10-02:2026-10-01:partidas'):
            with self.assertRaises(ValueError):report_table(b,kind)

if __name__=='__main__':unittest.main()

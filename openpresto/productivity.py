"""Read-only resource input ratios from explicit production and hourly entries."""
from decimal import Decimal,localcontext,ROUND_HALF_UP
from .budget import BudgetError
from .planning import iso
from . import production,resource_hours

WORK_HEADERS=('Relación','Partida','Resumen','Unidad producida','Producción registrada','Horas de recursos','Coste de horas','Horas / unidad','Coste / unidad','Disponibilidad')
RESOURCE_HEADERS=('Relación','Partida','Resumen','Unidad producida','Recurso','Descripción del recurso','Producción registrada','Horas','Coste de horas','Horas / unidad','Coste / unidad','Disponibilidad')
UNASSIGNED_HEADERS=('Recurso','Descripción','Horas sin partida','Coste sin partida')


def snapshot(budget,start,end):
    iso(start);iso(end)
    if start>end:raise BudgetError('El inicio debe ser anterior o igual al fin')
    with localcontext() as context:
        context.prec=160
        produced={};allocated={};unassigned={}
        for report in production.validate(budget):
            if report['status']!='posted' or not start<=report['date']<=end:continue
            for line in report['lines']:
                rid=line['relation_id'];produced[rid]=produced.get(rid,Decimal(0))+Decimal(line['quantity'])
        for entry in resource_hours.validate(budget):
            if entry['status']!='posted' or not start<=entry['date']<=end:continue
            code=entry['resource_code'];rid=entry['relation_id'];mapping=unassigned if rid is None else allocated;key=code if rid is None else (rid,code)
            before=mapping.get(key,(Decimal(0),Decimal(0)));mapping[key]=(before[0]+Decimal(entry['hours']),before[1]+resource_hours.cost(entry))
        totals={}
        for (rid,code),(hours,cost) in allocated.items():
            old=totals.get(rid,(Decimal(0),Decimal(0)));totals[rid]=(old[0]+hours,old[1]+cost)
        def ratios(quantity,values):
            hours,cost=values if values is not None else ('','')
            comparable=quantity is not None and values is not None
            status='Comparable' if comparable else 'Sin producción registrada' if quantity is None else 'Sin horas registradas'
            return (quantity if quantity is not None else '',hours,cost,(hours/quantity).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP) if comparable else '',(cost/quantity).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP) if comparable else '',status)
        work=[];resources=[]
        for rid in sorted(set(produced)|set(totals)):
            relation=budget._relation(rid);concept=budget.concepts[relation.child_code];common=(rid,concept.code,concept.summary,concept.unit)
            work.append(common+ratios(produced.get(rid),totals.get(rid)))
        for (rid,code),values in sorted(allocated.items()):
            relation=budget._relation(rid);concept=budget.concepts[relation.child_code];resource=budget.concepts[code]
            resources.append((rid,concept.code,concept.summary,concept.unit,code,resource.summary)+ratios(produced.get(rid),values))
        unassigned_rows=[(code,budget.concepts[code].summary,hours,cost) for code,(hours,cost) in sorted(unassigned.items())]
        return dict(start=start,end=end,work_items=work,resources=resources,unassigned=unassigned_rows,unassigned_cost=sum((v[1] for v in unassigned.values()),Decimal(0)))

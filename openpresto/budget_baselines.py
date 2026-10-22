"""Frozen economic graph references, independent of current graph existence."""
import json
from uuid import uuid4
from decimal import Decimal,localcontext
from .budget import BudgetError,_decimal
from .planning import iso
from .calculations import calculator_for,calculation_batch

KEY='budget_baselines_v1'
ROW_FIELDS={'relation_id','parent','child','summary','unit','quantity','price','factor','amount'}
HEADERS=('Relación','Padre base','Padre actual','Código base','Código actual','Resumen','Unidad base','Unidad actual','Cantidad base','Cantidad actual','Precio base','Precio actual','Factor base','Factor actual','Importe base','Importe actual','Variación importe','Estado')
BASE_HEADERS=('ID','Referencia','Fecha','Raíz','Total guardado','Relaciones','Nota')


def number(value):
    if not isinstance(value,str) or len(value)>256:raise BudgetError('Valor de línea base inválido')
    n=_decimal(value,'Valor de línea base')
    if n.copy_abs()>Decimal('1e60') or n.as_tuple().exponent < -24:raise BudgetError('Valor de línea base fuera de límites')
    return n


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>20:raise BudgetError('Máximo de 20 líneas base')
        ids=set();refs=set();total=0
        for base in data:
            if not isinstance(base,dict) or set(base)!={'id','reference','date','root','total','rows','note'}:raise BudgetError('Columnas de línea base inválidas')
            for key in ('id','reference','root','note'):
                if not isinstance(base[key],str) or len(base[key])>10000:raise BudgetError('Texto de línea base inválido')
            if not base['id'] or base['id'] in ids or not base['root'] or not base['reference'].strip():raise BudgetError('Identidad de línea base inválida')
            ids.add(base['id']);ref=base['reference'].strip().casefold()
            if ref in refs:raise BudgetError('Referencia de línea base repetida')
            refs.add(ref);iso(base['date']);number(base['total'])
            rows=base['rows']
            if not isinstance(rows,list):raise BudgetError('Relaciones de línea base inválidas')
            total+=len(rows)
            if total>100000:raise BudgetError('Demasiadas relaciones en líneas base')
            relations=set()
            for row in rows:
                if not isinstance(row,dict) or set(row)!=ROW_FIELDS:raise BudgetError('Relación de línea base inválida')
                for key in ('relation_id','parent','child','summary','unit'):
                    if not isinstance(row[key],str) or len(row[key])>10000:raise BudgetError('Texto de relación guardada inválido')
                if not row['relation_id'] or row['relation_id'] in relations or not row['parent'] or not row['child']:raise BudgetError('Identidad de relación guardada inválida')
                relations.add(row['relation_id'])
                for key in ('quantity','price','factor','amount'):number(row[key])
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Líneas base de presupuesto inválidas: '+str(exc)) from exc


def capture(budget):
    calculator=calculator_for(budget);rows=[]
    with localcontext() as context:
        context.prec=160
        with calculation_batch(calculator):
            total=calculator.total()
            for relation in sorted(budget.relations,key=lambda r:r.id):
                value=calculator.relation(relation.id);concept=budget.concepts[relation.child_code]
                rows.append(dict(relation_id=relation.id,parent=relation.parent_code,child=relation.child_code,summary=concept.summary,unit=concept.unit,quantity=str(value.quantity),price=str(value.unit_price),factor=str(relation.factor),amount=str(value.amount)))
    return dict(root=budget.root_code,total=str(total),rows=rows)


def freeze(budget,reference,date,note=''):
    data=validate(budget);base=dict(capture(budget),id=uuid4().hex,reference=reference,date=date,note=note)
    candidate=data+[base];validate(budget,candidate);budget.project_metadata[KEY]=json.dumps(candidate,ensure_ascii=False)


def remove(budget,baseline_id):
    data=validate(budget)
    if not any(r['id']==baseline_id for r in data):raise BudgetError('Línea base inexistente')
    budget.project_metadata[KEY]=json.dumps([r for r in data if r['id']!=baseline_id],ensure_ascii=False)


def overview(budget):
    return [(r['id'],r['reference'],r['date'],r['root'],Decimal(r['total']),len(r['rows']),r['note']) for r in validate(budget)]


def comparison(budget,baseline_id,changes_only=False):
    if type(changes_only) is not bool:raise BudgetError('Filtro de comparación inválido')
    base=next((r for r in validate(budget) if r['id']==baseline_id),None)
    if base is None:raise BudgetError('Línea base inexistente')
    current=capture(budget);old={r['relation_id']:r for r in base['rows']};new={r['relation_id']:r for r in current['rows']};rows=[]
    with localcontext() as context:
        context.prec=160
        for rid in sorted(set(old)|set(new)):
            before=old.get(rid);after=new.get(rid);status='Alta' if before is None else 'Baja' if after is None else 'Reasignada' if (before['parent'],before['child'])!=(after['parent'],after['child']) else 'Modificada' if any(before[k]!=after[k] for k in ('summary','unit')) or any(Decimal(before[k])!=Decimal(after[k]) for k in ('quantity','price','factor','amount')) else 'Sin cambios'
            if changes_only and status=='Sin cambios':continue
            def value(row,key):return row[key] if row else ''
            def numeric(row,key):return Decimal(row[key]) if row else ''
            delta=(Decimal(after['amount']) if after else Decimal(0))-(Decimal(before['amount']) if before else Decimal(0))
            rows.append((rid,value(before,'parent'),value(after,'parent'),value(before,'child'),value(after,'child'),value(after or before,'summary'),value(before,'unit'),value(after,'unit'),numeric(before,'quantity'),numeric(after,'quantity'),numeric(before,'price'),numeric(after,'price'),numeric(before,'factor'),numeric(after,'factor'),numeric(before,'amount'),numeric(after,'amount'),delta,status))
        return dict(reference=base['reference'],date=base['date'],old_root=base['root'],root=current['root'],base_total=Decimal(base['total']),current_total=Decimal(current['total']),delta_total=Decimal(current['total'])-Decimal(base['total']),rows=rows)

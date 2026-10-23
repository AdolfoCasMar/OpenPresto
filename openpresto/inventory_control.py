"""Dated views of the native weighted-average stock ledger."""
from decimal import Decimal,localcontext,ROUND_HALF_UP
from .planning import iso
from .budget import BudgetError
from . import management

HEADERS=('Recurso','Resumen','Unidad','Entradas','Consumos','Existencias','Valor registrado','Coste medio registrado')
MOVEMENT_HEADERS=('Fecha','Recurso','Movimiento','Documento / destino','Cantidad','Valor','Existencias tras movimiento','Valor restante')
PERIOD_HEADERS=('Recurso','Resumen','Unidad','Existencias iniciales','Valor inicial','Entradas del período','Valor de entradas','Consumos del período','Valor consumido','Existencias finales','Valor final')


def _snapshot(budget,as_of,include_zero,ledger):
    totals={};movements=[]
    with localcontext() as context:
        context.prec=160
        for row in ledger:
            if row[0]>as_of:continue
            movements.append(row);code=row[1];values=totals.setdefault(code,[Decimal(0),Decimal(0),Decimal(0),Decimal(0)])
            values[0 if row[2]=='Entrada' else 1]+=row[4];values[2]=row[6];values[3]=row[7]
        rows=[]
        for code,(incoming,consumed,quantity,value) in sorted(totals.items()):
            if not include_zero and quantity==0 and value==0:continue
            c=budget.concepts[code];average=(value/quantity).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP) if quantity else ''
            rows.append((code,c.summary,c.unit,incoming,consumed,quantity,value,average))
        return dict(as_of=as_of,rows=rows,movements=movements,total_value=sum((v[3] for v in totals.values()),Decimal(0)))


def snapshot(budget,as_of,include_zero=False):
    iso(as_of)
    if type(include_zero) is not bool:raise BudgetError('Filtro de inventario inválido')
    with localcontext() as context:
        context.prec=160
        data,ledger=management.validate_with_ledger(budget)
        return _snapshot(budget,as_of,include_zero,ledger)


def period(budget,start,end,include_zero=False):
    """Inclusive period, reconciled against the current native ledger state."""
    iso(start);iso(end)
    if start>end:raise BudgetError('La fecha inicial no puede ser posterior a la final')
    if type(include_zero) is not bool:raise BudgetError('Filtro de inventario inválido')
    with localcontext() as context:
        context.prec=160
        data,ledger=management.validate_with_ledger(budget)
        groups={};movements=[]
        for movement in ledger:
            day,code,kind,reference,quantity,value,remaining,remaining_value=movement
            if day>end:continue
            row=groups.setdefault(code,[Decimal(0) for _ in range(8)])
            if day<start:
                row[0:2]=remaining,remaining_value
            else:
                index=2 if kind=='Entrada' else 4
                row[index]+=quantity;row[index+1]+=value;movements.append(movement)
            row[6:8]=remaining,remaining_value
        rows=[]
        for code,values in sorted(groups.items()):
            opening,opening_value,incoming,incoming_value,used,used_value,closing,closing_value=values
            if opening+incoming-used!=closing or opening_value+incoming_value-used_value!=closing_value:
                raise BudgetError('El período no concuerda con el libro de existencias: '+code)
            if not include_zero and not any(values):continue
            concept=budget.concepts[code]
            rows.append((code,concept.summary,concept.unit,*values))
        totals={key:sum((row[index] for row in rows),Decimal(0)) for key,index in
                (('opening_value',4),('incoming_value',6),('consumed_value',8),('closing_value',10))}
        return dict(start=start,end=end,rows=rows,movements=movements,totals=totals,
                    cutoff=_snapshot(budget,end,include_zero,ledger))


ABC_HEADERS=('Clase','Recurso','Resumen','Unidad','Existencias','Valor registrado','% del valor','% acumulado')
ABC_SUMMARY_HEADERS=('Clase','Recursos','Valor registrado','% del valor')


def abc_from_snapshot(view):
    """Rank closing stock value, keeping the threshold-crossing item in its band.

    A starts below 80% of cumulative value, B below 95%, C the remainder.
    Zero-valued resources are C. Ties use the resource code for stable results.
    Classification uses exact amounts, not rounded display percentages.
    """
    with localcontext() as context:
        context.prec=160
        ordered=sorted(view['rows'],key=lambda row:(-row[6],row[0]))
        total=sum((row[6] for row in ordered),Decimal(0))
        cumulative=Decimal(0);rows=[]
        groups={key:[0,Decimal(0)] for key in ('A','B','C')}
        def percent(value):
            return (value*100/total).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if total else Decimal('0.00')
        for row in ordered:
            value=row[6]
            band=('A' if cumulative*100<total*80 else 'B' if cumulative*100<total*95 else 'C') if value>0 else 'C'
            cumulative+=value
            rows.append((band,row[0],row[1],row[2],row[5],value,percent(value),percent(cumulative)))
            groups[band][0]+=1;groups[band][1]+=value
        summary=[(band,count,value,percent(value)) for band,(count,value) in groups.items()]
        return dict(as_of=view['as_of'],rows=rows,summary=summary,total_value=total)


def abc(budget,as_of,include_zero=False):
    return abc_from_snapshot(snapshot(budget,as_of,include_zero))

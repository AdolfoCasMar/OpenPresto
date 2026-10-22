"""Dated views of the native weighted-average stock ledger."""
from decimal import Decimal,localcontext,ROUND_HALF_UP
from .planning import iso
from .budget import BudgetError
from . import management

HEADERS=('Recurso','Resumen','Unidad','Entradas','Consumos','Existencias','Valor registrado','Coste medio registrado')
MOVEMENT_HEADERS=('Fecha','Recurso','Movimiento','Documento / destino','Cantidad','Valor','Existencias tras movimiento','Valor restante')


def snapshot(budget,as_of,include_zero=False):
    iso(as_of)
    if type(include_zero) is not bool:raise BudgetError('Filtro de inventario inválido')
    data=management.validate(budget);totals={};movements=[]
    with localcontext() as context:
        context.prec=160
        for row in management.ledger(budget,data):
            if row[0]>as_of:continue
            movements.append(row);code=row[1];values=totals.setdefault(code,[Decimal(0),Decimal(0),Decimal(0),Decimal(0)])
            values[0 if row[2]=='Entrada' else 1]+=row[4];values[2]=row[6];values[3]=row[7]
        rows=[]
        for code,(incoming,consumed,quantity,value) in sorted(totals.items()):
            if not include_zero and quantity==0 and value==0:continue
            c=budget.concepts[code];average=(value/quantity).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP) if quantity else ''
            rows.append((code,c.summary,c.unit,incoming,consumed,quantity,value,average))
        return dict(as_of=as_of,rows=rows,movements=movements,total_value=sum((v[3] for v in totals.values()),Decimal(0)))

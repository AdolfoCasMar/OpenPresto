"""Read-only invoice price comparisons, distinct from physical progress and profit.

Orders, deliveries and invoices remain separate stages and are never added as
if they were independent costs. References use the current native price model.
"""
from decimal import Decimal,localcontext,ROUND_HALF_UP
from .planning import iso
from .calculations import calculator_for,calculation_batch
from . import management,issued_management
from .treasury import snapshot as cash_snapshot


SUMMARY_HEADERS=('Indicador','Importe / número')
CONCEPT_HEADERS=('Código','Unidad','Resumen','Cantidad comparable facturada','Base recibida total','Base comparable','Referencia comparable actual','Diferencia comparable','Diferencia %','Líneas sin cantidad')
DOCUMENT_HEADERS=('Circuito','Tipo','Documento','Fecha','Entidad','Base','Impuestos','Retenciones','Total neto')


def _snapshot(budget,as_of):
    iso(as_of);calculator=calculator_for(budget)
    purchases=management.validate(budget);sales=issued_management.validate(budget)
    totals={side+'_'+kind:Decimal(0) for side in ('purchase','sale') for kind in ('order','delivery','invoice')}
    groups={};documents=[];comparable_actual=Decimal(0);comparable_reference=Decimal(0);comparable_lines=0;unknown=0
    parties={'purchase':{r['id']:r['name'] for r in purchases['suppliers']},'sale':{r['id']:r['name'] for r in sales['customers']}}
    excluded_drafts=0;excluded_proformas=0
    with calculation_batch(calculator):
        budget_total=calculator.total() if budget.root_code is not None else None
        for side,data in (('purchase',purchases),('sale',sales)):
            for doc in data['documents']:
                if doc['date']>as_of:continue
                if doc['status']=='draft':excluded_drafts+=1
                if doc['status']!='posted':continue
                if doc['kind']=='proforma':excluded_proformas+=1;continue
                amounts=management.document_amounts(budget,doc)
                totals[side+'_'+doc['kind']]+=amounts[0]
                party=parties[side][doc['supplier_id'] if side=='purchase' else doc['customer_id']]
                documents.append((side,doc['kind'],doc['reference'],doc['date'],party,*amounts))
                if side!='purchase' or doc['kind']!='invoice':continue
                actual=management.document_line_amounts(budget,doc)
                reference_lines=[]
                for line in doc['lines']:
                    price=calculator.price(line['code']) if line['quantity'] is not None else line['unit_price']
                    reference_lines.append(dict(line,unit_price=str(price)))
                references=management.document_line_amounts(budget,dict(doc,lines=reference_lines))
                for line,amount,reference in zip(doc['lines'],actual,references):
                    code=line['code'];concept=budget.concepts[code]
                    row=groups.setdefault(code,dict(code=code,unit=concept.unit,summary=concept.summary,quantity=Decimal(0),actual=Decimal(0),comparable_actual=Decimal(0),reference=Decimal(0),known_lines=0,unknown_lines=0))
                    row['actual']+=amount
                    if line['quantity'] is None:row['unknown_lines']+=1;unknown+=1;continue
                    row['quantity']+=Decimal(line['quantity']);row['comparable_actual']+=amount;row['reference']+=reference;row['known_lines']+=1
                    comparable_actual+=amount;comparable_reference+=reference;comparable_lines+=1
        cash=cash_snapshot(budget,as_of)
    return dict(as_of=as_of,budget=budget_total,totals=totals,concepts=groups,documents=documents,comparable_actual=comparable_actual,comparable_reference=comparable_reference,comparable_lines=comparable_lines,unknown_lines=unknown,excluded_drafts=excluded_drafts,excluded_proformas=excluded_proformas,
                cash_in=sum((r['amount'] for r in cash['events'] if r['category']=='actual' and r['direction']=='in'),Decimal(0)),cash_out=sum((r['amount'] for r in cash['events'] if r['category']=='actual' and r['direction']=='out'),Decimal(0)),settlement_reviews=sum(r['category']=='review' for r in cash['events']))


def snapshot(budget,as_of):
    with localcontext() as context:
        context.prec=160
        return _snapshot(budget,as_of)


def summary_rows(view):
    t=view['totals'];known=view['comparable_lines']>0
    with localcontext() as context:
        context.prec=160
        return [('Presupuesto actual',view['budget'] if view['budget'] is not None else ''),('Pedidos de compra confirmados · base',t['purchase_order']),('Albaranes recibidos confirmados · base',t['purchase_delivery']),('Facturas recibidas confirmadas · base',t['purchase_invoice']),('Facturas emitidas confirmadas · base',t['sale_invoice']),('Base recibida en líneas comparables',view['comparable_actual'] if known else ''),('Referencia actual para esas cantidades',view['comparable_reference'] if known else ''),('Diferencia comparable · positivo = mayor importe',view['comparable_actual']-view['comparable_reference'] if known else ''),('Líneas sin cantidad comparable',view['unknown_lines']),('Cobros registrados · importe aplicado',view['cash_in']),('Pagos registrados · importe aplicado',view['cash_out']),('Saldos que requieren revisión',view['settlement_reviews'])]


def concept_rows(view):
    rows=[]
    with localcontext() as context:
        context.prec=160
        for code,r in sorted(view['concepts'].items()):
            known=r['known_lines']>0;delta=r['comparable_actual']-r['reference'] if known else None
            percent=(delta/r['reference']*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if known and r['reference']!=0 else None
            rows.append((code,r['unit'],r['summary'],r['quantity'] if known else '',r['actual'],r['comparable_actual'] if known else '',r['reference'] if known else '',delta if delta is not None else '',percent if percent is not None else '',r['unknown_lines']))
    return rows


def document_rows(view):
    sides={'purchase':'Recibido','sale':'Emitido'};kinds={'order':'Pedido','delivery':'Albarán','invoice':'Factura'}
    return [(sides[r[0]],kinds[r[1]],*r[2:]) for r in sorted(view['documents'],key=lambda r:(r[3],r[0],r[2]))]

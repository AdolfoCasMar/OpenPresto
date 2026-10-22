"""Quantity tracking from explicit procurement links, independent of stock/cash.

Direct order invoices fulfil order quantity. Invoices against deliveries bill
those deliveries without fulfilling the same order quantity a second time.
"""
from decimal import Decimal,localcontext
from .planning import iso
from . import management

ORDER_HEADERS=('Pedido','Fecha','Proveedor','Línea','Código','Unidad','Cantidad pedida','En albaranes','Factura directa','Facturado total','Sin albarán ni factura directa','Sin facturar','Estado')
DELIVERY_HEADERS=('Albarán','Fecha','Proveedor','Línea','Código','Unidad','Cantidad entregada','Facturado','Sin facturar','Estado')
LINK_HEADERS=('Documento','Tipo','Fecha','Proveedor','Línea','Código','Cantidad','Documento de origen','Línea de origen')


def _snapshot(budget,as_of):
    iso(as_of);data=management.validate(budget)
    documents={d['id']:d for d in data['documents'] if d['status']=='posted' and d['date']<=as_of and d['kind']!='proforma'}
    names={r['id']:r['name'] for r in data['suppliers']}
    delivered={};direct={};billed_delivery={};via_delivery={};links=[]
    def add(values,key,q):values[key]=values.get(key,Decimal(0))+q
    for doc in documents.values():
        if doc['kind'] not in ('delivery','invoice'):continue
        for index,line in enumerate(doc['lines']):
            source=documents.get(line['source_document']);source_index=line['source_index']
            quantity=Decimal(line['quantity']) if line['quantity'] is not None else None
            links.append((doc['reference'],'Albarán' if doc['kind']=='delivery' else 'Factura',doc['date'],names[doc['supplier_id']],index+1,line['code'],quantity if quantity is not None else '',source['reference'] if source else '',source_index+1 if source else ''))
            if source is None:continue
            key=source['id'],source_index
            if doc['kind']=='delivery':add(delivered,key,quantity)
            elif source['kind']=='order':add(direct,key,quantity)
            elif source['kind']=='delivery':
                add(billed_delivery,key,quantity)
                previous=source['lines'][source_index];order=documents.get(previous['source_document'])
                if order and order['kind']=='order':add(via_delivery,(order['id'],previous['source_index']),quantity)
    orders=[];deliveries=[]
    for doc in sorted(documents.values(),key=lambda d:(d['date'],d['reference'],d['id'])):
        if doc['kind'] not in ('order','delivery'):continue
        for index,line in enumerate(doc['lines']):
            key=doc['id'],index;q=Decimal(line['quantity']) if line['quantity'] is not None else None
            common=dict(reference=doc['reference'],date=doc['date'],supplier=names[doc['supplier_id']],line=index+1,code=line['code'],unit=budget.concepts[line['code']].unit,quantity=q)
            if doc['kind']=='order':
                supplied=delivered.get(key,Decimal(0));immediate=direct.get(key,Decimal(0));billed=immediate+via_delivery.get(key,Decimal(0))
                remaining=None if q is None else q-supplied-immediate;uninvoiced=None if q is None else q-billed
                status='Importe global: sin cantidad' if q is None else 'Completo' if remaining==0 and uninvoiced==0 else 'Pendiente'
                orders.append(dict(common,delivered=supplied,direct=immediate,billed=billed,unfulfilled=remaining,uninvoiced=uninvoiced,status=status))
            else:
                billed=billed_delivery.get(key,Decimal(0));remaining=None if q is None else q-billed
                deliveries.append(dict(common,billed=billed,uninvoiced=remaining,status='Importe global: sin cantidad' if q is None else 'Facturado' if remaining==0 else 'Pendiente'))
    return dict(as_of=as_of,orders=orders,deliveries=deliveries,links=sorted(links,key=lambda r:(r[2],r[0],r[4])),excluded_drafts=sum(d['status']=='draft' and d['date']<=as_of for d in data['documents']),excluded_proformas=sum(d['status']=='posted' and d['kind']=='proforma' and d['date']<=as_of for d in data['documents']))


def snapshot(budget,as_of):
    with localcontext() as context:
        context.prec=160
        return _snapshot(budget,as_of)


def order_rows(view,pending_only=False):
    rows=[]
    for r in view['orders']:
        if pending_only and r['status']=='Completo':continue
        rows.append((r['reference'],r['date'],r['supplier'],r['line'],r['code'],r['unit'],r['quantity'] if r['quantity'] is not None else '',r['delivered'],r['direct'],r['billed'],r['unfulfilled'] if r['unfulfilled'] is not None else '',r['uninvoiced'] if r['uninvoiced'] is not None else '',r['status']))
    return rows


def delivery_rows(view,pending_only=False):
    return [(r['reference'],r['date'],r['supplier'],r['line'],r['code'],r['unit'],r['quantity'] if r['quantity'] is not None else '',r['billed'],r['uninvoiced'] if r['uninvoiced'] is not None else '',r['status']) for r in view['deliveries'] if not pending_only or r['status']!='Facturado']

"""Read-only cash projection from explicit native records, never bank balances.

Opening settlements reduce outstanding documents but are not dated cash events.
Current document/schedule states are used; this is not a historical ledger replay.
"""
from decimal import Decimal,localcontext
from .budget import BudgetError
from .planning import iso
from . import management,management_advanced,management_schedule,issued_management


def _snapshot(budget,as_of,include_proformas=False):
    iso(as_of)
    if type(include_proformas) is not bool:raise BudgetError('Selección de proformas inválida')
    purchases=management.validate(budget);sales=issued_management.validate(budget)
    payments=management_advanced.validate(budget)['payments'];schedules=management_schedule.validate(budget)
    from .retention_openings import opening_balances
    retention_balances=opening_balances(budget,as_of)
    from .issued_retention_openings import opening_balances as issued_openings
    issued_retention_balances=issued_openings(budget,as_of)
    events=[];purchase_paid={};sale_paid={}
    def add(direction,category,day,doc,party,amount,detail=''):
        events.append(dict(direction=direction,category=category,date=day,document_id=doc['id'],reference=doc['reference'],party=party,amount=amount,detail=detail,overdue=bool(category=='forecast' and day and day<as_of)))
    purchase_docs={r['id']:r for r in purchases['documents']}
    supplier_names={r['id']:r['name'] for r in purchases['suppliers']}
    sale_docs={r['id']:r for r in sales['documents']}
    customer_names={r['id']:r['name'] for r in sales['customers']}
    from .retention_settlements import events as retention_events
    for entry in retention_events(budget,as_of):
        direction=entry['direction'];doc=(purchase_docs if direction=='out' else sale_docs)[entry['document_id']];party=supplier_names[doc['supplier_id']] if direction=='out' else customer_names[doc['customer_id']]
        balances=retention_balances if direction=='out' else issued_retention_balances
        paid=balances.setdefault(doc['id'],{'guarantee':Decimal(0),'fiscal':Decimal(0)})
        if paid is not None:paid[entry['kind']]+=entry['value']
        add(direction,'actual',entry['event_date'],doc,party,entry['value'],('Anulación de retención · ' if entry['reversal'] else 'Liquidación de retención · ')+entry['reference'])
    for payment in payments:
        if payment['date']>as_of or (payment['status']=='cancelled' and payment['cancellation_date']<=as_of):continue
        for allocation in payment['allocations']:
            doc=purchase_docs[allocation['document_id']];amount=Decimal(allocation['amount'])
            purchase_paid[doc['id']]=purchase_paid.get(doc['id'],Decimal(0))+amount
            add('out','actual',payment['date'],doc,supplier_names[doc['supplier_id']],amount,'Pago registrado · '+payment['reference'])
    for receipt in sales['receipts']:
        if receipt['date']>as_of:continue
        doc=sale_docs[receipt['document_id']];amount=Decimal(receipt['amount'])
        sale_paid[doc['id']]=sale_paid.get(doc['id'],Decimal(0))+amount
        add('in','actual',receipt['date'],doc,customer_names[doc['customer_id']],amount,'Cobro registrado · '+receipt['reference'])
    def forecast(direction,doc,party,net,retention,settled,dues,issue,retention_paid=None,retention_issue=False):
        normal=[d for d in dues if d['kind']=='normal']
        if normal and sum((Decimal(d['amount']) for d in normal),Decimal(0))!=net:
            issue='El calendario no concilia con el importe nativo actual'
        if settled>net:issue='Liquidación superior al importe del documento'
        if issue:
            add(direction,'review',None,doc,party,None,issue)
        elif normal:
            remaining=settled
            for due in sorted(normal,key=lambda d:(d['date'] or '9999-12-31',d['id'])):
                amount=Decimal(due['amount']);covered=min(amount,remaining);remaining-=covered;amount-=covered
                if amount>0:add(direction,'forecast',due['date'],doc,party,amount,'Vencimiento pendiente · '+{'invoice':'Factura','proforma':'Proforma'}[doc['kind']])
        elif net>settled:
            add(direction,'forecast',doc['due_date'],doc,party,net-settled,'Vencimiento pendiente · '+{'invoice':'Factura','proforma':'Proforma'}[doc['kind']])
        if retention_issue:
            add(direction,'review',None,doc,party,None,'Revisar apertura de retenciones o corte anterior a su seguimiento')
            return
        retention_paid=dict(retention_paid or {'guarantee':Decimal(0),'fiscal':Decimal(0)})
        scheduled_retention=sum((Decimal(d['amount']) for d in dues if d['kind']!='normal'),Decimal(0))
        if scheduled_retention>retention:
            add(direction,'review',None,doc,party,None,'Las retenciones de origen no concilian con el documento nativo')
            return
        if retention>scheduled_retention:
            add(direction,'forecast',None,doc,party,retention-scheduled_retention,'Retención pendiente de programar')
        for due in sorted(dues,key=lambda r:(r['date'] or '9999-12-31',r['id'])):
            if due['kind']=='normal':continue
            amount=Decimal(due['amount'])
            covered=min(amount,retention_paid[due['kind']]);retention_paid[due['kind']]-=covered;amount-=covered
            if amount<=0:continue
            if due.get('paid_in_source',False):
                add(direction,'review',due['date'],doc,party,None,'Retención liquidada en origen; revisar su estado nativo')
            else:add(direction,'forecast',due['date'],doc,party,amount,'Retención prevista · '+{'guarantee':'Garantía','fiscal':'Fiscal'}[due['kind']])
    for doc in purchases['documents']:
        if doc['status']!='posted' or doc['date']>as_of or doc['kind'] not in ('invoice','proforma') or (doc['kind']=='proforma' and not include_proformas):continue
        record=schedules.get(doc['id']);settled=purchase_paid.get(doc['id'],Decimal(0));issue='';dues=[]
        if record:
            dues=record['dues'];opening=record['opening']
            if opening:
                if opening['date']<=as_of:settled+=Decimal(opening['paid'])
                elif Decimal(opening['paid'])>0:issue='Corte anterior a la apertura de seguimiento'
            elif Decimal(record['source_paid'])>0:issue='Saldo pagado de origen pendiente de revisión'
        amounts=management.document_amounts(budget,doc)
        retention_paid=retention_balances.get(doc['id'],{})
        forecast('out',doc,supplier_names[doc['supplier_id']],amounts[3],amounts[2],settled,dues,issue,retention_paid,retention_paid is None)
    for doc in sales['documents']:
        if doc['status']!='posted' or doc['date']>as_of or doc['kind'] not in ('invoice','proforma') or (doc['kind']=='proforma' and not include_proformas):continue
        source=sales['source_states'].get(doc['id']);opening=sales['openings'].get(doc['id']);settled=sale_paid.get(doc['id'],Decimal(0));issue='';dues=[]
        if opening:
            if opening['date']<=as_of:settled+=Decimal(opening['amount'])
            elif Decimal(opening['amount'])>0:issue='Corte anterior a la apertura de seguimiento'
        elif source and Decimal(source['paid'])>0:issue='Saldo cobrado de origen pendiente de revisión'
        if source:
            for i,due in enumerate(source['dues']):
                dues.append(dict(id=str(i),date=due['date'],kind={0:'normal',1:'guarantee',2:'fiscal'}[due['kind']],amount=due['amount'],paid_in_source=due['paid'] and due['kind']!=0 and doc['id'] not in issued_retention_balances))
        amounts=issued_management.amounts(budget,doc)
        retention_paid=issued_retention_balances.get(doc['id'],{})
        forecast('in',doc,customer_names[doc['customer_id']],amounts[3],amounts[2],settled,dues,issue,retention_paid,retention_paid is None)
    events.sort(key=lambda r:(r['date'] or '9999-12-31',r['category'],r['direction'],r['document_id'],r['detail']))
    return dict(as_of=as_of,include_proformas=include_proformas,events=events)


def detail_rows(view):
    directions={'in':'Entrada','out':'Salida'};categories={'actual':'Registrado','forecast':'Previsto','review':'Revisar'}
    return [(r['date'] or '',directions[r['direction']],categories[r['category']],r['reference'],r['party'],r['amount'] if r['amount'] is not None else '','Sí' if r['overdue'] else '',r['detail']) for r in view['events']]


def _month_rows(view):
    periods={}
    for row in view['events']:
        period=row['date'][:7] if row['date'] else 'Sin fecha'
        values=periods.setdefault(period,dict(actual_in=Decimal(0),actual_out=Decimal(0),forecast_in=Decimal(0),forecast_out=Decimal(0),unknown=0))
        if row['amount'] is None:values['unknown']+=1
        else:values[row['category']+'_'+row['direction']]+=row['amount']
    return [(month,v['actual_in'],v['actual_out'],v['actual_in']-v['actual_out'],v['forecast_in'],v['forecast_out'],v['forecast_in']-v['forecast_out'] if not v['unknown'] else '',v['unknown']) for month,v in sorted(periods.items())]


def snapshot(budget,as_of,include_proformas=False):
    with localcontext() as context:
        context.prec=160
        return _snapshot(budget,as_of,include_proformas)


def month_rows(view):
    with localcontext() as context:
        context.prec=160
        return _month_rows(view)

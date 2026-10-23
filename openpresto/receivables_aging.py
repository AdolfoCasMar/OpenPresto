"""Read-only aging of known outstanding treasury events, without netting parties."""
from decimal import Decimal,localcontext
from .planning import iso

HEADERS=('Sentido','Entidad (ID)','Entidad','Documento','Saldo','No vencido','1–30 días','31–60 días','61–90 días','Más de 90 días','Sin fecha','Pendiente conocido','Partidas por revisar')
DETAIL_HEADERS=('Sentido','Documento (ID)','Referencia','Entidad','Tipo','Saldo','Vencimiento','Días de atraso','Tramo','Pendiente conocido','Revisión')
BANDS=('No vencido','1–30 días','31–60 días','61–90 días','Más de 90 días','Sin fecha')
DIRECTIONS={'in':'Cobrar','out':'Pagar'}
KINDS={'invoice':'Factura','proforma':'Proforma'}
OBLIGATIONS={'normal':'Ordinario','retention':'Retención'}


def from_treasury(view):
    """Use the same settled balances and oldest-due allocation as treasury."""
    cutoff=iso(view['as_of']);groups={};details=[]
    totals={direction:dict(known=Decimal(0),overdue=Decimal(0),undated=Decimal(0),reviews=0) for direction in DIRECTIONS}
    with localcontext() as context:
        context.prec=160
        for event in view['events']:
            if event['category']=='actual':continue
            direction=event['direction'];kind=event['document_kind'];obligation=event['obligation']
            key=direction,event['party_id'],kind,obligation
            group=groups.setdefault(key,dict(name=event['party'],amounts=[Decimal(0) for _ in BANDS],reviews=0))
            amount=event['amount'];days='';band='Revisar';review=''
            if event['category']=='review':
                group['reviews']+=1;totals[direction]['reviews']+=1;review=event['detail']
            else:
                if event['date'] is None:index=5
                else:
                    days=max(0,(cutoff-iso(event['date'])).days)
                    index=0 if days==0 else 1 if days<=30 else 2 if days<=60 else 3 if days<=90 else 4
                band=BANDS[index];group['amounts'][index]+=amount;totals[direction]['known']+=amount
                if index==5:totals[direction]['undated']+=amount
                elif index>0:totals[direction]['overdue']+=amount
            details.append((DIRECTIONS[direction],event['document_id'],event['reference'],event['party'],KINDS[kind],OBLIGATIONS[obligation],event['date'] or '',days,band,amount if amount is not None else '',review))
        rows=[]
        for (direction,party,kind,obligation),group in sorted(groups.items()):
            rows.append((DIRECTIONS[direction],party,group['name'],KINDS[kind],OBLIGATIONS[obligation],*group['amounts'],sum(group['amounts'],Decimal(0)),group['reviews']))
        return dict(as_of=view['as_of'],include_proformas=view['include_proformas'],rows=rows,details=details,totals=totals)


def snapshot(budget,as_of,include_proformas=False):
    from .treasury import snapshot as treasury_snapshot
    return from_treasury(treasury_snapshot(budget,as_of,include_proformas))

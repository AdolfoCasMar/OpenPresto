"""Native site issue register with explicit dated status transitions."""
import json
from uuid import uuid4
from .budget import BudgetError
from .planning import iso
from .production import eligible

KEY='site_issues_v1'
STATES={'open':'Abierta','in_progress':'En curso','resolved':'Resuelta','cancelled':'Anulada'}
PRIORITIES={'low':'Baja','normal':'Normal','high':'Alta','critical':'Crítica'}
CATEGORIES={'general':'General','quality':'Calidad','safety':'Seguridad'}
TRANSITIONS={'open':('in_progress','resolved','cancelled'),'in_progress':('open','resolved','cancelled'),'resolved':('open',),'cancelled':()}
HEADERS=('Referencia','Apertura','Vencimiento','Responsable','Prioridad','Categoría','Estado actual','Situación al corte','Relación','Partida','Título','Descripción')
EVENT_HEADERS=('Referencia','Fecha','Estado','Nota')


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>10000:raise BudgetError('Demasiadas incidencias')
        ids=set();refs=set();total=0;relations={r.id for r in eligible(budget)}
        for row in data:
            if not isinstance(row,dict) or set(row)!={'id','reference','opened','due','responsible','priority','category','relation_id','title','description','status','events'}:raise BudgetError('Columnas de incidencia inválidas')
            for key in ('id','reference','responsible','title','description'):
                if not isinstance(row[key],str) or len(row[key])>10000:raise BudgetError('Texto de incidencia inválido')
            if not row['id'] or row['id'] in ids or not row['reference'].strip() or not row['title'].strip():raise BudgetError('Identidad o título de incidencia inválido')
            ids.add(row['id']);iso(row['opened']);ref=(row['opened'][:4],row['reference'].strip().casefold())
            if ref in refs:raise BudgetError('Referencia de incidencia repetida en el año')
            refs.add(ref)
            if row['due'] is not None:
                iso(row['due'])
                if row['due']<row['opened']:raise BudgetError('Vencimiento anterior a la apertura')
            if row['priority'] not in PRIORITIES or row['category'] not in CATEGORIES or row['status'] not in STATES:raise BudgetError('Clasificación de incidencia inválida')
            rid=row['relation_id']
            if rid is not None and (not isinstance(rid,str) or rid not in relations):raise BudgetError('Partida de incidencia inexistente')
            events=row['events']
            if not isinstance(events,list) or not events:raise BudgetError('Incidencia sin historial')
            total+=len(events)
            if total>100000:raise BudgetError('Demasiados eventos de incidencias')
            previous=None;last_date=row['opened']
            for event in events:
                if not isinstance(event,dict) or set(event)!={'date','status','note'}:raise BudgetError('Evento de incidencia inválido')
                iso(event['date'])
                if not isinstance(event['note'],str) or len(event['note'])>10000 or event['status'] not in STATES:raise BudgetError('Datos de evento inválidos')
                if previous is None:
                    if event['date']!=row['opened'] or event['status']!='open':raise BudgetError('Apertura de historial inválida')
                else:
                    if event['date']<last_date or event['status'] not in TRANSITIONS[previous]:raise BudgetError('Secuencia de estados inválida')
                    if (event['status'] in ('resolved','cancelled') or previous=='resolved') and not event['note'].strip():raise BudgetError('Resolución, anulación o reapertura sin motivo')
                previous=event['status'];last_date=event['date']
            if previous!=row['status']:raise BudgetError('Estado e historial incoherentes')
        return data
    except (TypeError,ValueError) as exc:raise BudgetError('Incidencias de obra inválidas: '+str(exc)) from exc


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def set_issue(budget,reference,opened,title,responsible='',priority='normal',category='general',due=None,relation_id=None,description='',issue_id=None):
    data=validate(budget);old=next((r for r in data if r['id']==issue_id),None)
    if issue_id is not None and old is None:raise BudgetError('Incidencia inexistente')
    if old and old['status'] not in ('open','in_progress'):raise BudgetError('Reabre la incidencia antes de editarla')
    if old and (reference!=old['reference'] or opened!=old['opened']):raise BudgetError('La referencia y la apertura se conservan')
    row=dict(id=old['id'] if old else uuid4().hex,reference=reference,opened=opened,title=title,responsible=responsible,priority=priority,category=category,due=due,relation_id=relation_id,description=description,
             status=old['status'] if old else 'open',events=old['events'] if old else [dict(date=opened,status='open',note='')])
    _save(budget,[row if r['id']==row['id'] else r for r in data] if old else data+[row])


def set_status(budget,issue_id,status,date,note=''):
    data=validate(budget);old=next((r for r in data if r['id']==issue_id),None)
    if old is None:raise BudgetError('Incidencia inexistente')
    if status not in TRANSITIONS[old['status']]:raise BudgetError('Cambio de estado de incidencia no permitido')
    row=dict(old,status=status,events=old['events']+[dict(date=date,status=status,note=note)])
    _save(budget,[row if r['id']==issue_id else r for r in data])


def listing(budget,as_of,pending_only=False,overdue_only=False):
    """Filter current states; dates do not reconstruct historical states."""
    iso(as_of)
    if type(pending_only) is not bool or type(overdue_only) is not bool:raise BudgetError('Filtro de incidencias inválido')
    result=[]
    for row in validate(budget):
        if row['opened']>as_of:continue
        pending=row['status'] in ('open','in_progress');overdue=pending and row['due'] is not None and row['due']<as_of
        if pending_only and not pending or overdue_only and not overdue:continue
        result.append(dict(row,overdue=overdue))
    return sorted(result,key=lambda r:(not r['overdue'],r['due'] or '9999-12-31',r['reference'],r['id']))


def report_rows(budget,as_of,pending_only=False,overdue_only=False):
    rows=[]
    for r in listing(budget,as_of,pending_only,overdue_only):
        rid=r['relation_id'];code=budget._relation(rid).child_code if rid else ''
        situation='Vencida' if r['overdue'] else 'Sin fecha' if r['status'] in ('open','in_progress') and r['due'] is None else 'Pendiente' if r['status'] in ('open','in_progress') else 'Cerrada'
        rows.append((r['reference'],r['opened'],r['due'] or '',r['responsible'],PRIORITIES[r['priority']],CATEGORIES[r['category']],STATES[r['status']],situation,rid or '',code,r['title'],r['description']))
    return rows


def event_rows(budget):
    return [(r['reference'],e['date'],STATES[e['status']],e['note']) for r in sorted(validate(budget),key=lambda r:(r['opened'],r['reference'])) for e in r['events']]

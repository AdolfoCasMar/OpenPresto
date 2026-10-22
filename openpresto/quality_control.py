"""Explicit inspection checklists; no inferred technical acceptance criteria."""
import json
from uuid import uuid4
from .budget import BudgetError
from .planning import iso
from .production import eligible

KEY='quality_control_v1'
RESULTS={'pending':'Pendiente','pass':'Cumple','fail':'No cumple','na':'No aplica'}
STATES={'draft':'Borrador','reviewed':'Revisado','cancelled':'Anulado'}
HEADERS=('Referencia','Fecha','Responsable','Relación','Partida','Control','Estado','Resultado','Cumplen','No cumplen','Pendientes','No aplican','Fecha de revisión','Nota','Fecha de anulación','Motivo de anulación')
DETAIL_HEADERS=('Referencia','Nº','Comprobación / criterio','Resultado','Observación')


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>10000:raise BudgetError('Demasiados controles')
        ids=set();refs=set();total=0;allowed={r.id for r in eligible(budget)}
        for row in data:
            if not isinstance(row,dict) or set(row)!={'id','reference','date','inspector','relation_id','title','note','checks','status','reviewed_on','cancelled_on','cancellation_reason'}:raise BudgetError('Columnas de control inválidas')
            for key in ('id','reference','inspector','title','note','cancellation_reason'):
                if not isinstance(row[key],str) or len(row[key])>10000:raise BudgetError('Texto de control inválido')
            if not row['id'] or row['id'] in ids or not row['reference'].strip() or not row['title'].strip():raise BudgetError('Identidad o título de control inválido')
            ids.add(row['id']);iso(row['date']);ref=(row['date'][:4],row['reference'].strip().casefold())
            if ref in refs:raise BudgetError('Referencia de control repetida en el año')
            refs.add(ref);rid=row['relation_id']
            if rid is not None and (not isinstance(rid,str) or rid not in allowed):raise BudgetError('Partida de control inexistente')
            checks=row['checks']
            if not isinstance(checks,list) or not checks:raise BudgetError('El control necesita comprobaciones')
            total+=len(checks)
            if total>100000:raise BudgetError('Demasiadas comprobaciones')
            for check in checks:
                if not isinstance(check,dict) or set(check)!={'criterion','result','note'}:raise BudgetError('Comprobación inválida')
                if any(not isinstance(check[k],str) or len(check[k])>10000 for k in ('criterion','note')) or not check['criterion'].strip() or check['result'] not in RESULTS:raise BudgetError('Criterio o resultado inválido')
            if row['status'] not in STATES:raise BudgetError('Estado de control inválido')
            reviewed=row['reviewed_on']
            if reviewed is not None:
                iso(reviewed)
                if reviewed<row['date'] or not row['inspector'].strip():raise BudgetError('Revisión sin responsable o anterior al control')
                if any(c['result']=='pending' for c in checks) or not any(c['result'] in ('pass','fail') for c in checks):raise BudgetError('Revisión incompleta o sin comprobaciones aplicables')
                if any(c['result']=='fail' and not c['note'].strip() for c in checks):raise BudgetError('Una comprobación no conforme necesita observación')
            if row['status']=='reviewed' and reviewed is None or row['status']=='draft' and reviewed is not None:raise BudgetError('Estado y revisión incoherentes')
            if row['status']=='cancelled':
                iso(row['cancelled_on'])
                if row['cancelled_on']<(reviewed or row['date']) or not row['cancellation_reason'].strip():raise BudgetError('Anulación sin fecha o motivo válido')
            elif row['cancelled_on'] is not None or row['cancellation_reason']:raise BudgetError('Anulación incompatible con estado')
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Controles de calidad inválidos: '+str(exc)) from exc


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def set_inspection(budget,reference,date,title,checks,inspector='',relation_id=None,note='',inspection_id=None):
    data=validate(budget);old=next((r for r in data if r['id']==inspection_id),None)
    if inspection_id is not None and old is None:raise BudgetError('Control inexistente')
    if old and old['status']!='draft':raise BudgetError('Solo se editan borradores; anula y crea otro control para corregirlo')
    row=dict(id=old['id'] if old else uuid4().hex,reference=reference,date=date,title=title,checks=checks,inspector=inspector,relation_id=relation_id,note=note,status='draft',reviewed_on=None,cancelled_on=None,cancellation_reason='')
    _save(budget,[row if r['id']==row['id'] else r for r in data] if old else data+[row])


def set_status(budget,inspection_id,status,date,reason=''):
    data=validate(budget);old=next((r for r in data if r['id']==inspection_id),None)
    if old is None:raise BudgetError('Control inexistente')
    if old['status']=='draft' and status=='reviewed':
        if reason:raise BudgetError('La revisión no admite motivo de anulación')
        row=dict(old,status=status,reviewed_on=date)
    elif old['status'] in ('draft','reviewed') and status=='cancelled':row=dict(old,status=status,cancelled_on=date,cancellation_reason=reason)
    else:raise BudgetError('Transición de control no permitida')
    _save(budget,[row if r['id']==inspection_id else r for r in data])


def entries(budget):
    return sorted(validate(budget),key=lambda r:(r['date'],r['reference'],r['id']))


def verdict(row):
    if row['status']=='cancelled':return 'Anulado'
    if row['status']=='draft':return 'Pendiente de revisión'
    return 'No conforme' if any(c['result']=='fail' for c in row['checks']) else 'Conforme'


def report_rows(budget):
    rows=[]
    for r in entries(budget):
        rid=r['relation_id'];code=budget._relation(rid).child_code if rid else ''
        counts={key:sum(c['result']==key for c in r['checks']) for key in RESULTS}
        rows.append((r['reference'],r['date'],r['inspector'],rid or '',code,r['title'],STATES[r['status']],verdict(r),counts['pass'],counts['fail'],counts['pending'],counts['na'],r['reviewed_on'] or '',r['note'],r['cancelled_on'] or '',r['cancellation_reason']))
    return rows


def detail_rows(budget):
    return [(r['reference'],i+1,c['criterion'],RESULTS[c['result']],c['note']) for r in entries(budget) for i,c in enumerate(r['checks'])]

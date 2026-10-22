"""Explicit provenance links from reviewed failed checks to site issues."""
import json
from .budget import BudgetError
from . import quality_control as quality,site_issues as issues

KEY='quality_issue_links_v1'
HEADERS=('Control','Revisión','Estado del control','Nº','Comprobación','Observación','Relación de origen','Incidencia','Estado de incidencia','Responsable','Vencimiento','Seguimiento')


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>100000:raise BudgetError('Demasiados vínculos de no conformidad')
        inspections={r['id']:r for r in quality.validate(budget)};cases={r['id']:r for r in issues.validate(budget)};sources=set();targets=set()
        for link in data:
            if not isinstance(link,dict) or set(link)!={'inspection_id','check_index','issue_id'}:raise BudgetError('Vínculo de no conformidad inválido')
            if not isinstance(link['inspection_id'],str) or not isinstance(link['issue_id'],str) or type(link['check_index']) is not int:raise BudgetError('Identidad de vínculo inválida')
            inspection=inspections.get(link['inspection_id']);case=cases.get(link['issue_id']);index=link['check_index']
            if inspection is None or case is None or inspection['reviewed_on'] is None or not 0<=index<len(inspection['checks']) or inspection['checks'][index]['result']!='fail':raise BudgetError('Origen o incidencia de no conformidad inexistente')
            if case['opened']<inspection['reviewed_on']:raise BudgetError('Incidencia anterior a la revisión de origen')
            key=inspection['id'],index
            if key in sources or case['id'] in targets:raise BudgetError('Vínculo de no conformidad repetido')
            sources.add(key);targets.add(case['id'])
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Seguimiento de no conformidades inválido: '+str(exc)) from exc


def create_issue(budget,inspection_id,check_index,reference,opened,responsible='',priority='normal',due=None):
    links=validate(budget)
    if not isinstance(inspection_id,str) or type(check_index) is not int:raise BudgetError('Selecciona una comprobación válida')
    inspection=next((r for r in quality.validate(budget) if r['id']==inspection_id),None)
    if inspection is None or inspection['status']!='reviewed' or not 0<=check_index<len(inspection['checks']) or inspection['checks'][check_index]['result']!='fail':raise BudgetError('Solo se crean incidencias desde comprobaciones no conformes de controles revisados vigentes')
    if any(r['inspection_id']==inspection_id and r['check_index']==check_index for r in links):raise BudgetError('Esta comprobación ya tiene una incidencia vinculada')
    if len(links)>=100000:raise BudgetError('Demasiados vínculos de no conformidad')
    # Compose both models privately so direct headless callers also get atomicity.
    from .storage import dumps,loads
    candidate=loads(dumps(budget));before={r['id'] for r in issues.validate(candidate)};check=inspection['checks'][check_index]
    issues.set_issue(candidate,reference,opened,check['criterion'],responsible,priority,'quality',due,inspection['relation_id'],inspection['reference']+' · '+str(check_index+1)+' · '+check['note'])
    created=next(r for r in issues.validate(candidate) if r['id'] not in before)
    updated=links+[dict(inspection_id=inspection_id,check_index=check_index,issue_id=created['id'])]
    validate(candidate,updated);candidate.project_metadata[KEY]=json.dumps(updated,ensure_ascii=False)
    budget.project_metadata[issues.KEY]=candidate.project_metadata[issues.KEY];budget.project_metadata[KEY]=candidate.project_metadata[KEY]


def listing(budget,include_cancelled=False,pending_only=False):
    if type(include_cancelled) is not bool or type(pending_only) is not bool:raise BudgetError('Filtro de no conformidades inválido')
    links={(r['inspection_id'],r['check_index']):r['issue_id'] for r in validate(budget)};cases={r['id']:r for r in issues.validate(budget)};result=[]
    for inspection in quality.entries(budget):
        if inspection['reviewed_on'] is None or inspection['status']=='cancelled' and not include_cancelled:continue
        for index,check in enumerate(inspection['checks']):
            if check['result']!='fail':continue
            case=cases.get(links.get((inspection['id'],index)))
            tracking='Sin incidencia' if case is None else 'Resuelta' if case['status']=='resolved' else 'Revisar incidencia anulada' if case['status']=='cancelled' else 'Pendiente'
            if pending_only and tracking=='Resuelta':continue
            row=(inspection['reference'],inspection['reviewed_on'],quality.STATES[inspection['status']],index+1,check['criterion'],check['note'],inspection['relation_id'] or '',case['reference'] if case else '',issues.STATES[case['status']] if case else '',case['responsible'] if case else '',case['due'] or '' if case else '',tracking)
            result.append(dict(inspection_id=inspection['id'],check_index=index,issue_id=case['id'] if case else None,row=row))
    return result


def report_rows(budget,include_cancelled=False,pending_only=False):
    return [r['row'] for r in listing(budget,include_cancelled,pending_only)]

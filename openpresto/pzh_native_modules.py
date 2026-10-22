"""Convert proven source modules to native editable copies, item by item."""
import json
from .budget import BudgetError

KEY='pzh_native_conversion_v1'
_RESULT_MODULES={
    'planning':frozenset(('Mediciones presupuestarias','Planificación')),
    'management':frozenset(('Entidades','Registros de control','Gestión emitida',
                            'Contratos y ofertas','Compras','Vencimientos recibidos')),
    'certifications':frozenset(),
}


def results(budget):
    try:
        rows=json.loads(budget.project_metadata.get(KEY,'[]'))
        if not isinstance(rows,list) or len(rows)>100000:raise ValueError('lista')
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'module','item','status','detail'} or any(not isinstance(v,str) for v in row.values()) or row['status'] not in ('available','pending'):raise ValueError('fila')
        return rows
    except (ValueError,TypeError) as exc:raise BudgetError('Resultado de conversión nativa PZH inválido') from exc


def convert_supported(budget,modules=None,progress=None):
    from .pzh_operations import validate as source_state
    from .pzh_archive import pzh_source_bytes
    from .pzh_native_management import copy_document,copy_contract,copy_dues
    from .issued_management import copy_source
    from .planning_phases import copy_pzh,KEY as PLAN_KEY
    if pzh_source_bytes(budget) is None:raise BudgetError('Falta el PZH original conservado')
    if modules is not None and not isinstance(modules,(list,tuple,set,frozenset)):raise BudgetError('Selección de módulos inválida')
    selected={'planning','management'} if modules is None else set(modules)
    if selected-{'planning','management','certifications'}:raise BudgetError('Módulo de conversión desconocido')
    refreshed=set().union(*(_RESULT_MODULES[name] for name in selected))
    rows=[row for row in results(budget) if row['module'] not in refreshed]
    source=source_state(budget);jobs=[]
    if 'planning' in selected:
        from .pzh_archive import pzh_archive_inventory
        if pzh_archive_inventory(budget)['inventory'][4]['records']:
            from .budget_phase_measurements import copy_source as copy_measurement_phases
            jobs.append(('Mediciones presupuestarias','Todas las fases',lambda:copy_measurement_phases(budget)))
    if 'planning' in selected and source.get('activities') and (source.get('phases') or source.get('precedences') or any(r['planned_start'] or r['planned_finish'] for r in source['activities'])):
        if PLAN_KEY not in budget.project_metadata:jobs.append(('Planificación','Plan por fases',lambda:copy_pzh(budget)))
        else:rows.append(dict(module='Planificación',item='Plan por fases',status='available',detail='Plan existente conservado sin sobrescribir'))
    if 'management' in selected:
        if source.get('entities'):
            from .entities import copy_pzh as copy_entities
            jobs.append(('Entidades','Directorio de entidades',lambda:copy_entities(budget)))
        for doc in source.get('documents',[]):
            rid=doc['id']
            if doc['kind']==5:
                jobs.append(('Registros de control',str(rid),lambda rid=rid:copy_record(budget,rid)))
            elif doc['issued']:
                jobs.append(('Gestión emitida',str(rid),lambda rid=rid:copy_source(budget,rid)))
            elif doc['kind']==1 and doc['proforma']:
                jobs.append(('Contratos y ofertas',str(rid),lambda rid=rid:copy_contract(budget,rid)))
            else:jobs.append(('Compras',str(rid),lambda rid=rid:copy_document(budget,rid)))
        for doc in source.get('documents',[]):
            if not doc['issued'] and doc['kind']==3 and not doc['proforma'] and any((d['reference'],d['entity'])==(doc['reference'],doc['entity']) for d in source.get('dues',[])):
                jobs.append(('Vencimientos recibidos',str(doc['id']),lambda rid=doc['id']:copy_dues(budget,rid)))
    for index,(module,item,action) in enumerate(jobs):
        if progress is not None:progress(88+int(8*index/max(1,len(jobs))),f'Copias editables: {module} ({index+1}/{len(jobs)})')
        previous=dict(budget.project_metadata)
        try:
            action();unbound=0
            if module=='Mediciones presupuestarias':
                from .budget_phase_measurements import state as phase_state
                phase_copy=phase_state(budget)
                if phase_copy is None:raise BudgetError('No se ha creado una copia nativa de las fases')
                unbound=sum(r['relation_id'] is None for r in phase_copy['lines'])
        except (BudgetError,ValueError,ArithmeticError,RecursionError) as exc:
            budget.project_metadata.clear();budget.project_metadata.update(previous)
            rows.append(dict(module=module,item=item,status='pending',detail=str(exc)))
        else:
            rows.append(dict(module=module,item=item,status='pending' if unbound else 'available',detail=f'{unbound} líneas nativas sin vincular; requieren revisión antes de aplicar cantidades' if unbound else 'Copia nativa disponible; documentos como borradores, sin movimientos históricos'))
    budget.project_metadata[KEY]=json.dumps(rows,ensure_ascii=False)
    return rows


def convert_project(budget,modules=None,progress=None):
    """Command adapter: conversion results stay in metadata, not in the model slot."""
    convert_supported(budget,modules,progress)


RECORDS_KEY='pzh_records_v1'
RECORD_STATES={0:'Indefinido',1:'Conforme',2:'No conforme',3:'Corregido'}


def control_records(budget):
    from .planning import iso
    try:
        rows=json.loads(budget.project_metadata.get(RECORDS_KEY,'[]'))
        if not isinstance(rows,list) or len(rows)>10000:raise ValueError('lista')
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'id','source_id','reference','entity','date','state','note','source_fields'}:raise ValueError('columnas')
            if any(not isinstance(row[k],str) for k in ('id','reference','entity','note')) or not row['id'] or row['id'] in seen:raise ValueError('texto o identidad')
            seen.add(row['id'])
            if type(row['source_id']) is not int or row['source_id']<0 or type(row['state']) is not int or row['state'] not in RECORD_STATES:raise ValueError('identidad o estado')
            if row['date'] is not None:iso(row['date'])
            if not isinstance(row['source_fields'],dict) or any(not isinstance(k,str) or not isinstance(v,(str,int)) for k,v in row['source_fields'].items()):raise ValueError('campos originales')
        return rows
    except (ValueError,TypeError) as exc:raise BudgetError('Registros de control inválidos') from exc


def _write_records(budget,rows):
    from copy import copy
    candidate=copy(budget);candidate.project_metadata=dict(budget.project_metadata)
    candidate.project_metadata[RECORDS_KEY]=json.dumps(rows,ensure_ascii=False)
    control_records(candidate)
    budget.project_metadata[RECORDS_KEY]=candidate.project_metadata[RECORDS_KEY]


def copy_record(budget,source_id):
    import hashlib
    from .pzh_operations import validate as source_state
    from .pzh_archive import pzh_source_bytes
    if type(source_id) is not int:raise BudgetError('Identificador de registro inválido')
    row=next((r for r in source_state(budget).get('documents',[]) if r['id']==source_id),None)
    if row is None or row['kind']!=5:raise BudgetError('Selecciona un registro de control PZH')
    raw=pzh_source_bytes(budget)
    if raw is None:raise BudgetError('Falta el PZH original')
    rid='pzh:'+hashlib.sha256(raw).hexdigest()+':record:'+str(source_id)
    rows=control_records(budget)
    if any(r['id']==rid for r in rows):return
    rows.append(dict(id=rid,source_id=source_id,reference=row['reference'],entity=row['entity'],date=row['date'],state=row['fields'].get('5',0),note=row['note'],source_fields=row['fields']))
    _write_records(budget,rows)


def set_record(budget,record_id,state,note):
    rows=control_records(budget);row=next((r for r in rows if r['id']==record_id),None)
    if row is None:raise BudgetError('Registro de control inexistente')
    row.update(state=state,note=note);_write_records(budget,rows)


def record_rows(budget):
    return [(r['id'],r['source_id'],r['reference'],r['entity'],r['date'] or '',RECORD_STATES[r['state']],r['note']) for r in control_records(budget)]

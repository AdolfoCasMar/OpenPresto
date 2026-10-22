"""Independent editable copies of source budget measurement phases.

The source approval boundary is provenance, never a guessed per-phase approval.
Applying a reviewed boundary is explicit and separate from certification/planning.
"""
import json
from decimal import Decimal
from dataclasses import replace
from .budget import BudgetError, BudgetMeasurement, _decimal,special_price_kind

KEY='budget_phase_measurements_v1'
FIELDS=('comment','n_lines','length','width','height','formula')


def state(budget):
    try:data=json.loads(budget.project_metadata.get(KEY,'null'))
    except (ValueError,TypeError) as exc:raise BudgetError('Mediciones por fases inválidas') from exc
    if data is None:
        if KEY in budget.project_metadata:raise BudgetError('Mediciones por fases vacías no válidas')
        return None
    if not isinstance(data,dict) or set(data)!={'source_sha256','approved_through','active_through','lines'}:raise BudgetError('Estructura de mediciones por fases inválida')
    sha=data['source_sha256']
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise BudgetError('Huella de fases inválida')
    for key in ('approved_through','active_through'):
        v=data[key]
        if v is not None and (type(v) is not int or not 1<=v<=99):raise BudgetError('Límite de fase inválido')
    rows=data['lines']
    if not isinstance(rows,list) or len(rows)>100000:raise BudgetError('Demasiadas líneas de fase')
    ids=set();relation_ids={r.id for r in budget.relations}
    for row in rows:
        columns={'id','relation_id','phase','order','kind',*FIELDS}
        if not isinstance(row,dict) or set(row) not in (columns,columns|{'source_relation'}):raise BudgetError('Línea de fase inválida')
        if not isinstance(row['id'],str) or not row['id'].isdigit() or len(row['id'])>20 or row['id'] in ids:raise BudgetError('Identificador de fase repetido')
        ids.add(row['id'])
        source=row.get('source_relation')
        if 'source_relation' in row:
            if not isinstance(source,dict) or set(source)!={'parent','child','occurrence'} or any(not isinstance(source[k],str) or not source[k] or len(source[k])>13 for k in ('parent','child')) or source['occurrence'] not in ('2020','2030'):raise BudgetError('Procedencia de relación de fase inválida')
        if row['relation_id'] is None:
            if source is None:raise BudgetError('Línea sin vincular y sin relación de origen')
        elif row['relation_id'] not in relation_ids:raise BudgetError('Medición de fase sin relación')
        if type(row['phase']) is not int or not 1<=row['phase']<=99 or type(row['order']) is not int or row['order']<0:raise BudgetError('Fase u orden inválido')
        if type(row['kind']) is not int or row['kind'] not in (0,1,2):raise BudgetError('Tipo de línea inválido')
        if not isinstance(row['comment'],str) or len(row['comment'])>100000 or not isinstance(row['formula'],str):raise BudgetError('Texto de medición inválido')
        if row['kind'] and row['formula']:raise BudgetError('Subtotal y fórmula combinados no admitidos')
        _measurement(row)
    if data['active_through'] is not None and data['active_through'] not in {r['phase'] for r in rows}:raise BudgetError('Límite aplicado sin fase existente')
    if data['active_through'] is not None and any(r['relation_id'] is None for r in rows):raise BudgetError('No se pueden aplicar fases con líneas sin vincular')
    known_sha=budget.project_metadata.get('import_sha256')
    if known_sha is not None and data['source_sha256']!=known_sha:raise BudgetError('La huella de fases no coincide con el origen importado')
    return data


def _measurement(row):
    values=[]
    for key in ('n_lines','length','width','height'):
        v=row[key]
        if v is not None:
            if not isinstance(v,str):raise BudgetError('Dimensión de fase debe ser decimal en texto')
            v=_decimal(v,key)
            if abs(v)>Decimal('1e12') or v.as_tuple().exponent < -100:raise BudgetError('Dimensión de fase fuera de límites')
        if key=='n_lines' and v is None:raise BudgetError('Número de unidades de fase ausente')
        values.append(v)
    return BudgetMeasurement(row['relation_id'] or 'unbound-phase-preview',row['comment'],*values,id='phase-'+row['id'],formula=row['formula'])


def _save(budget,data):
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    old=budget.project_metadata.get(KEY)
    budget.project_metadata[KEY]=raw
    try:state(budget)
    except Exception:
        if old is None:budget.project_metadata.pop(KEY,None)
        else:budget.project_metadata[KEY]=old
        raise


def copy_source(budget):
    if KEY in budget.project_metadata:
        state(budget);return
    from .pzh_archive import pzh_source_bytes
    from .pzh_importer import _Reader,_fields,_code,_relation_key,_unpack,MEASUREMENT_FIELDS
    import hashlib
    raw=pzh_source_bytes(budget)
    if raw is None:raise BudgetError('El proyecto no conserva un PZH original')
    reader=_Reader(raw)
    pairs={_relation_key(r.parent_code,r.child_code,bytes.fromhex(budget.project_metadata.get('pzh_relation_occurrence:'+r.id,'2020'))):r.id for r in budget.relations}
    rows=[]
    excluded=json.loads(budget.project_metadata.get('pzh_excluded_relations','[]'))
    excluded={tuple(k) for k in excluded}
    for offset,identifier,record in reader.records(4,12):
        if len(record)<30 or record[0] not in (0,1):raise BudgetError('Clave de medición por fases no admitida')
        pair=_relation_key(_code(record[1:14]),_code(record[14:27]),record[27:29])
        if pair in excluded:continue
        fields=_fields(record[30:],MEASUREMENT_FIELDS,'Medición por fases')
        formula=fields.get(5,'');dims=[fields.get(i) for i in range(12,16)]
        n=dims[0] if dims[0] is not None else Decimal(1) if formula or any(v is not None for v in dims) else Decimal(0)
        values=[str(n)]+[str(v) if v else None for v in dims[1:]]
        row=dict(id=str(identifier),relation_id=pairs.get(pair),phase=record[29],order=_unpack(raw,offset+8,'I')[0],kind=fields.get(1,0),comment=fields.get(4,''),formula=formula)
        if pair not in pairs:row['source_relation']=dict(parent=pair[0],child=pair[1],occurrence=record[27:29].hex())
        row.update(zip(('n_lines','length','width','height'),values));rows.append(row)
    _save(budget,dict(source_sha256=hashlib.sha256(raw).hexdigest(),approved_through=reader.approved_phase,active_through=None,lines=rows))


def edit_line(budget,line_id,changes):
    data=state(budget)
    if data is None:raise BudgetError('No hay mediciones por fases nativas')
    if not isinstance(changes,dict) or not changes or set(changes)-set(FIELDS):raise BudgetError('Campos de medición por fases no editables')
    row=next((r for r in data['lines'] if r['id']==line_id),None)
    if row is None:raise BudgetError('Línea de fase inexistente')
    row.update(changes);data['active_through']=None;_save(budget,data)


def link_line(budget,line_id,relation_id):
    data=state(budget)
    if data is None:raise BudgetError('No hay mediciones por fases nativas')
    row=next((r for r in data['lines'] if r['id']==line_id),None)
    if row is None or 'source_relation' not in row:raise BudgetError('Selecciona una línea de origen que necesite revisión de vínculo')
    relation=budget._relation(relation_id)
    if special_price_kind(relation.child_code) or '%' in relation.child_code:raise BudgetError('No se vincula una medición a un cargo porcentual')
    row['relation_id']=relation_id;data['active_through']=None;_save(budget,data)


def apply_through(budget,phase):
    from .history_snapshots import capture_snapshot,restore_snapshot
    candidate=restore_snapshot(capture_snapshot(budget))
    _apply(candidate,phase)
    return restore_snapshot(capture_snapshot(candidate))


def _apply(budget,phase):
    data=state(budget)
    if data is None or type(phase) is not int or phase not in {r['phase'] for r in data['lines']}:raise BudgetError('Selecciona una fase de medición existente')
    if any(r['relation_id'] is None for r in data['lines']):raise BudgetError('Vincula las líneas de fase pendientes antes de aplicar cantidades')
    affected={r['relation_id'] for r in data['lines']}
    lines=[];kinds={}
    for row in sorted(data['lines'],key=lambda r:(r['order'],int(r['id']))):
        if row['phase']>phase:continue
        line=_measurement(row);lines.append(line)
        if row['kind']:
            # Source subtotal rows may carry a dimensional contribution. Keep
            # that contribution and a separate zero-contribution marker.
            marker=replace(line,id=line.id+'-subtotal',comment='',n_lines=Decimal(0),length=None,width=None,height=None)
            lines.append(marker);kinds[marker.id]={1:'2',2:'1'}[row['kind']]
    budget.measurements=[m for m in budget.measurements if m.relation_id not in affected]+lines
    for rid in affected:budget.bc3_measurements.pop(rid,None)
    for key in list(budget.project_metadata):
        if key.startswith('measurement_kind:') and key.split(':',1)[1] not in {m.id for m in budget.measurements}:budget.project_metadata.pop(key)
    for identity,kind in kinds.items():budget.project_metadata['measurement_kind:'+identity]=kind
    for rid in affected:
        relation=budget._relation(rid)
        budget.concepts[relation.child_code]=replace(budget.concepts[relation.child_code],measurement_decimals=2)
        # No selected line means a real zero for this reviewed boundary, not
        # fallback to the former manual quantity of the imported relation.
        if not any(m.relation_id==rid for m in lines):
            zero=BudgetMeasurement(rid,n_lines=Decimal(0),id='phase-zero-'+rid);budget.measurements.append(zero)
    data['active_through']=phase;_save(budget,data)


def report_rows(budget):
    data=state(budget)
    if data is None:return []
    return [(r['id'],r['phase'],r['relation_id'] if r['relation_id'] is not None else 'Sin vincular: '+r['source_relation']['parent']+' → '+r['source_relation']['child'],r['comment'],r['n_lines'],r['length'] or '',r['width'] or '',r['height'] or '',r['formula'],_measurement(r).partial(2)) for r in sorted(data['lines'],key=lambda r:(r['phase'],r['order']))]

HEADERS=('Id','Fase','Relación','Comentario','N','Longitud','Anchura','Altura','Fórmula','Parcial')


def preview(budget,phase):
    """Read-only economic comparison; nested relationship amounts are not summed."""
    from .calculations import calculator_for,calculation_batch
    candidate=apply_through(budget,phase)
    affected={r['relation_id'] for r in state(budget)['lines']}
    before=calculator_for(budget);after=calculator_for(candidate);rows=[]
    with calculation_batch(before),calculation_batch(after):
        before_total=before.total() if budget.root_code is not None else None
        after_total=after.total() if candidate.root_code is not None else None
        for relation in budget.relations:
            if relation.id not in affected:continue
            old=before.relation(relation.id);new=after.relation(relation.id)
            rows.append((relation.id,relation.parent_code,relation.child_code,budget.concepts[relation.child_code].unit,old.quantity,new.quantity,new.quantity-old.quantity,old.amount,new.amount,new.amount-old.amount))
    return dict(phase=phase,before_total=before_total,after_total=after_total,
                delta_total=after_total-before_total if before_total is not None else None,
                rows=rows,changed_relations=sum(r[4]!=r[5] or r[7]!=r[8] for r in rows))

PREVIEW_HEADERS=('Relación','Superior','Concepto','Ud','Cantidad actual','Cantidad propuesta','Diferencia','Importe actual','Importe propuesto','Diferencia de importe')


def clear_copy(budget):
    """Remove the editable phase copy, retaining active quantities and source."""
    budget.project_metadata.pop(KEY,None)

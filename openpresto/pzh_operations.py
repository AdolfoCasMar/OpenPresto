"""Typed, read-only source projection; does not invent native stock movements.

Source document totals and independently calculated bases remain separate.
Invalid records remain archived; independently readable records are retained.
Structural table failures still reject the whole table atomically.
"""
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from .budget import BudgetError

KEY = 'pzh_operations_v1'
SCHEMAS = {
    10: {1:'H',2:'B',**{i:'s' for i in range(3,15)},**{i:'d' for i in range(15,29)},29:'s',30:'B',**{i:'d' for i in range(31,36)},36:'H',37:'s',38:'s',39:'s',40:'d'},
    11: {1:'H',2:'s',3:'s',4:'s',5:'H',6:'d',7:'d',8:'s',9:'B',10:'B',11:'s'},
    13: {1:'H',2:'B',3:'s',4:'B',5:'B',6:'B',**{i:'d' for i in range(7,17)},17:'s',18:'s',19:'s',**{i:'d' for i in range(20,24)},24:'s',25:'H',26:'d',27:'s'},
    14: {1:'H',**{i:'B' for i in range(2,9)},9:'H',10:'H',**{i:'d' for i in range(11,15)},15:'s',16:'H',17:'H'},
    15: {1:'B',2:'B',3:'s',4:'d',5:'d'},
}


def convert_archived(budget):
    """Enrich an older imported project without replacing its economic graph."""
    from .pzh_archive import pzh_source_bytes
    from .pzh_importer import _Reader, _fields, _code, CONCEPT_FIELDS, RELATION_FIELDS, _relation_key
    source=pzh_source_bytes(budget)
    if source is None:raise BudgetError('Este proyecto no conserva un archivo PZH')
    reader=_Reader(source)
    concepts={_code(b[:13]):_fields(b[13:],CONCEPT_FIELDS,'Concepto PZH') for _,_,b in reader.records(0,8)}
    relations={_relation_key(_code(b[:13]),_code(b[13:26]),b[26:28]):_fields(b[28:],RELATION_FIELDS,'Relación PZH') for _,_,b in reader.records(1,16)}
    pairs={_relation_key(r.parent_code,r.child_code,bytes.fromhex(budget.project_metadata.get('pzh_relation_occurrence:'+r.id,'2020'))):r for r in budget.relations}
    import_operations(budget,reader,concepts,relations,pairs)
    validate(budget)


def day(serial):
    return (date(1979,12,31)+timedelta(days=serial)).isoformat() if serial else None


def effective_quantities(data):
    """Explicit zero stays zero; only an absent offer quantity can inherit.

    Quotation templates are identified by the same contract reference and an
    empty entity. Ambiguous templates or repeated offer codes are not guessed.
    """
    docs={r['id']:r for r in data.get('documents',[])}
    templates={};quantities={};counts={}
    for doc in docs.values():
        if doc['kind']==1 and not doc['entity']:
            templates.setdefault(doc['reference'],[]).append(doc['id'])
    for row in data.get('supplies',[]):
        docid=row.get('documents',{}).get('1')
        if docid is not None:
            key=(docid,row['code']);counts[key]=counts.get(key,0)+1
            quantities[key]=quantities.get(key,Decimal(0))+Decimal(row['quantity'])
    result={}
    for row in data.get('supplies',[]):
        quantity=Decimal(row['quantity']);inherited=False
        doc=docs.get(row.get('documents',{}).get('1'))
        if doc and doc['entity'] and '11' not in row['fields']:
            template=templates.get(doc['reference'],[])
            if len(template)==1 and counts.get((doc['id'],row['code']))==1 and (template[0],row['code']) in quantities:
                quantity=quantities[template[0],row['code']];inherited=True
        result[row['id']]=(quantity,inherited)
    return result


def reconcile_documents(data):
    documents={};byid={}
    for row in data['documents']:
        key=(row['kind'],row['reference'],row['entity'])
        documents.setdefault(key,[]).append(row);byid[row['id']]=row
        row.update(calculated_base='0.00',base_difference=None,linked_supplies=0)
    notes=[]
    for row in data['supplies']:
        row['documents']={}
        for slot,kind in ((0,3),(3,1),(4,2)):
            reference=row['keys'][slot]
            if not reference:continue
            matches=documents.get((kind,reference,row['keys'][1]),[])
            if len(matches)!=1:
                notes.append(f'Suministro {row["id"]}: enlace documental tipo {kind} sin resolución única; no se imputa.');continue
            row['documents'][str(kind)]=matches[0]['id']
    quantities=effective_quantities(data);sums={}
    for row in data['supplies']:
        f=row['fields'];quantity,inherited=quantities[row['id']]
        raw=quantity*Decimal(f.get('12','1'))*Decimal(f.get('14','0'))*(1-Decimal(f.get('13','0'))/100)
        row['amount']=str(raw.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        for docid in row['documents'].values():
            doc=byid[docid]
            # Supplier quotations carry unrounded extended prices. Operational
            # documents and the quantity template retain per-line rounding.
            value=raw if doc['kind']==1 and doc['entity'] and doc['proforma'] else Decimal(row['amount'])
            sums[docid]=sums.get(docid,Decimal(0))+value
            doc['linked_supplies']+=1
    for row in data['documents']:
        row['calculated_base']=str(sums.get(row['id'],Decimal(0)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        field={1:8,2:9,3:10}.get(row['kind'])
        if field:
            saved=Decimal(row['fields'].get(str(field),'0')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            row['base_difference']=str(Decimal(row['calculated_base'])-saved)
    return notes


def invoice_balances(data):
    """Reconcile payment *states*, never invent an actual payment date.

    Serialised document fields 7 and 16 are VencPag and VencPte. In
    particular, field 7 is NOT the invoice total (it can be a partial payment).
    Guarantee retentions remain separate scheduled dues, not discounts.
    """
    rows=[];counts={}
    for doc in data.get('documents',[]):
        if doc['kind']==3:
            key=(doc['reference'],doc['entity']);counts[key]=counts.get(key,0)+1
    for doc in data.get('documents',[]):
        if doc['kind']!=3:continue
        key=(doc['reference'],doc['entity'])
        dues=[r for r in data.get('dues',[]) if (r['reference'],r['entity'])==key] if counts[key]==1 else []
        paid=sum((Decimal(r['amount']) for r in dues if r['paid']),Decimal(0))
        pending=sum((Decimal(r['amount']) for r in dues if not r['paid']),Decimal(0))
        retained=sum((Decimal(r['amount']) for r in dues if not r['paid'] and r['kind'] in (1,2)),Decimal(0))
        f=doc['fields'];base=Decimal(doc['invoice_base']).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        tax=(base*Decimal(f.get('13','0'))/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        gross=base+tax
        saved_paid=Decimal(f.get('7','0')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        saved_pending=Decimal(f.get('16','0')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        rows.append((doc['reference'],doc['entity'],doc['issued'],doc['proforma'],base,tax,gross,
                     len(dues),paid,pending,retained,paid-saved_paid,pending-saved_pending,
                     gross-paid-pending if dues else '', 'Referencia ambigua' if counts[key]!=1 else 'Sin vencimientos' if not dues else ''))
    return rows


def import_operations(budget, reader, concepts, relations, pairs, *, modules=None, merge=False):
    from .pzh_importer import _fields, _code, _unpack, PZHImportError, _relation_key
    data = {'activities':[], 'phases':[], 'precedences':[], 'entities':[], 'offers':[],
            'documents':[], 'supplies':[], 'dues':[], 'unsupported':[]}
    selected = {'planning', 'management'} if modules is None else set(modules)
    if merge and KEY in budget.project_metadata:
        data = state(budget)
    notes=[]
    rejected = json.loads(budget.project_metadata.get('pzh_operations_rejected', '[]')) if merge else []
    if 'planning' in selected:
        for name in ('activities','phases','precedences'):data[name]=[]
        for pair,r in pairs.items():
            if pair not in relations:continue
            f=relations[pair]
            if concepts[pair[0]].get(2)!=4 or concepts[pair[1]].get(2) not in (5,10): continue
            c=concepts[pair[1]]
            data['activities'].append({'relation_id':r.id,'parent':pair[0],'code':pair[1],
                'planned_start':day(f.get(2,0)),'planned_finish':day(f.get(3,0)),
                'actual_start':day(f.get(4,0)),'actual_finish':day(f.get(5,0)),
                'objective_quantity':str(f.get(17,0)),'planned_quantity':str(f.get(18,0)),
                'objective_price':str(c.get(12,0)),'planned_price':str(c.get(12,0))})
        for _,identifier,b in reader.records(18,12):
            if len(b)<29:raise PZHImportError('Clave de fase planificada PZH incompleta')
            pair=_relation_key(_code(b[:13]),_code(b[13:26]),b[26:28])
            if pair not in pairs: continue
            f=_fields(b[29:],{1:'H',**{i:'d' for i in range(2,12)}},'Fase de planificación')
            data['phases'].append({'id':identifier,'relation_id':pairs[pair].id,'phase':b[28],
                'quantity':str(f.get(6,0)),'cumulative':str(f.get(11,0))})
        cumulative={}
        phase_keys=set()
        for row in sorted(data['phases'],key=lambda r:r['phase']):
            rid=row['relation_id'];key=(rid,row['phase'])
            if row['phase']==0 or key in phase_keys:raise PZHImportError('Fase planificada nula o repetida')
            phase_keys.add(key)
            cumulative[rid]=cumulative.get(rid,Decimal(0))+Decimal(row['quantity'])
            if cumulative[rid].quantize(Decimal('.01'))!=Decimal(row['cumulative']).quantize(Decimal('.01')):
                raise PZHImportError('El acumulado de planificación no coincide con las fases PZH')
        for _,identifier,b in reader.records(19,12):
            if len(b)!=56:
                raise PZHImportError('Precedencia PZH fuera del perfil observado')
            a=_relation_key(_code(b[:13]),_code(b[13:26]),b[26:28]);z=_relation_key(_code(b[28:41]),_code(b[41:54]),b[54:56])
            if a not in pairs or z not in pairs: raise PZHImportError('Precedencia PZH sin relación')
            data['precedences'].append({'id':identifier,'before':pairs[a].id,'after':pairs[z].id})
    for t,h,prefix,target in ((10,8,13,'entities'),(11,12,26,'offers'),(13,20,28,'documents'),(14,32,91,'supplies'),(15,16,28,'dues')):
        if 'management' not in selected: continue
        rejected=[r for r in rejected if r['table']!=t]
        data['unsupported']=[table for table in data['unsupported'] if table!=t]
        data[target]=[]
        rows=[]
        try:
            for _,identifier,b in reader.records(t,h):
                try:
                    if len(b)<prefix: raise PZHImportError('Registro incompleto')
                    schema=SCHEMAS[t]
                    if t==13:
                        at=prefix+3 if len(b)>prefix and b[prefix]==1 else prefix
                        if len(b)>=at+2 and b[at:at+2]==b'\x02\x05':
                            schema={**schema,7:'raw8'}  # Registro: opaque property, not VencPag.
                    f=_fields(b[prefix:],schema,f'Tabla {t}, registro {identifier}')
                    row={'id':identifier,'fields':{str(k):str(v) if isinstance(v,Decimal) else v for k,v in f.items()}}
                    if t==10: row.update(code=_code(b[:13]),name=f.get(3,''),contact=f.get(4,''))
                    elif t==11: row.update(code=_code(b[:13]),entity=_code(b[13:26]),date=day(f.get(5,0)),price=str(f.get(6,0)))
                    elif t in (13,15):
                        row.update(date=day(_unpack(b,0,'H')[0]),reference=b[2:15].decode('cp1252').rstrip(' '),entity=b[15:28].decode('cp1252').rstrip(' '))
                        if t==13:
                            if f.get(4,0) not in (0,1):raise PZHImportError('Dirección documental desconocida')
                            row.update(kind=f.get(2,0),issued=bool(f.get(4,0)),proforma=f.get(5,0)==1,amount=str(f.get(7,0)),invoice_base=str(f.get(10,0)),note=f.get(17,''))
                        else:
                            if f.get(2,0) not in (0,1) or f.get(1,0) not in (0,1,2):raise PZHImportError('Estado de vencimiento desconocido')
                            row.update(kind=f.get(1,0),paid=bool(f.get(2,0)),note=f.get(3,''),amount=str(f.get(4,0)))
                    else:
                        row.update(keys=[b[i:i+13].decode('cp1252').rstrip(' ') for i in range(0,91,13)],
                                   code=b[26:39].decode('cp1252').rstrip(' '),destination=b[65:78].decode('cp1252').rstrip(' '),
                                   date=day(f.get(10,0)),quantity=str(f.get(11,0)),price=str(f.get(14,0)))
                    if t==13 and row['kind']==5:
                        if f.get(5,0) not in (0,1,2,3):raise PZHImportError('Estado de registro de control desconocido')
                        row['amount']=None;row['invoice_base']=None;row['proforma']=False
                    rows.append(row)
                except PZHImportError as exc:
                    rejected.append({'table':t, 'record':identifier, 'reason':str(exc)})
                    continue
        except PZHImportError as exc:
            if t not in data['unsupported']:data['unsupported'].append(t)
            notes.append(f'IMPORTACIÓN PARCIAL: tabla {t} conservada sin conversión semántica: {exc}')
        else:
            data[target]=rows
            failed=[r for r in rejected if r['table']==t]
            if failed:
                if t not in data['unsupported']:data['unsupported'].append(t)
                notes.append(f'IMPORTACIÓN PARCIAL: tabla {t}: {len(rows)} registros recuperados y {len(failed)} sin convertir. Los rechazados permanecen en el PZH original archivado; revisar antes de usar sus importes.')
    # Invoice / entity / concept / order / delivery / destination / work.
    # Each document link must resolve uniquely; never join by reference alone.
    notes.extend(reconcile_documents(data))
    budget.project_metadata['pzh_operations_rejected']=json.dumps(rejected,ensure_ascii=False,separators=(',',':'))
    budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    notes.append('PZH: módulos seleccionados (' + ', '.join(sorted(selected)) + ') disponibles en Origen PZH. Los datos de origen no equivalen a documentos nativos editables; revisar diferencias y limitaciones.')
    previous=budget.project_metadata.get('pzh_operations_notes','').splitlines() if merge else []
    budget.project_metadata['pzh_operations_notes']='\n'.join(dict.fromkeys(previous+notes))
    return notes


def state(budget):
    try: data=json.loads(budget.project_metadata.get(KEY,'{}'))
    except (ValueError,TypeError) as exc: raise BudgetError('Conversión PZH inválida') from exc
    return data


def rejected_records(budget):
    try:
        rows=json.loads(budget.project_metadata.get('pzh_operations_rejected','[]'))
        if not isinstance(rows,list) or len(rows)>100000:raise ValueError('lista')
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'table','record','reason'}:raise ValueError('columnas')
            if type(row['table']) is not int or row['table'] not in SCHEMAS:raise ValueError('tabla')
            if type(row['record']) is not int or row['record']<0:raise ValueError('registro')
            if not isinstance(row['reason'],str):raise ValueError('motivo')
        return rows
    except (ValueError,TypeError) as exc:
        raise BudgetError('Inventario de registros PZH sin convertir inválido') from exc


def validate(budget):
    data=state(budget)
    rejected_records(budget)
    if data=={}:return data
    expected={'activities','phases','precedences','entities','offers','documents','supplies','dues','unsupported'}
    if not isinstance(data,dict) or set(data)!=expected or any(not isinstance(v,list) or len(v)>100000 for v in data.values()):
        raise BudgetError('Estructura de conversión PZH inválida')
    required={
        'activities':{'relation_id','parent','code','planned_start','planned_finish','actual_start','actual_finish','objective_quantity','planned_quantity','objective_price','planned_price'},
        'phases':{'id','relation_id','phase','quantity','cumulative'},
        'precedences':{'id','before','after'},
        'entities':{'id','fields','code','name','contact'},
        'offers':{'id','fields','code','entity','date','price'},
        'documents':{'id','fields','date','reference','entity','kind','issued','proforma','amount','invoice_base','note','calculated_base','base_difference','linked_supplies'},
        'supplies':{'id','fields','keys','code','destination','date','quantity','price','documents','amount'},
        'dues':{'id','fields','date','reference','entity','kind','paid','note','amount'}}
    numeric={'objective_quantity','planned_quantity','objective_price','planned_price','quantity','cumulative','price','amount','invoice_base','calculated_base','base_difference'}
    dates={'planned_start','planned_finish','actual_start','actual_finish','date'}
    try:
        for key,columns in required.items():
            seen=set()
            for row in data[key]:
                if not isinstance(row,dict) or set(row)!=columns:raise ValueError('columnas')
                identity=row.get('id',row.get('relation_id'))
                if identity in seen:raise ValueError('identificador repetido')
                seen.add(identity)
                for name,value in row.items():
                    if name in numeric:
                        if name=='base_difference' and value is None:continue
                        if key=='documents' and row['kind']==5 and name in ('amount','invoice_base') and value is None:continue
                        if not isinstance(value,str) or not Decimal(value).is_finite() or abs(Decimal(value))>Decimal('1e15'):raise ValueError('número')
                    elif name in dates:
                        if value is not None and (not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value):raise ValueError('fecha')
                    elif name in ('id','kind','phase','linked_supplies'):
                        if type(value) is not int or value<0:raise ValueError('entero')
                    elif name in ('issued','proforma','paid'):
                        if type(value) is not bool:raise ValueError('estado')
                    elif name=='fields':
                        if not isinstance(value,dict) or any(not isinstance(k,str) or not isinstance(v,(str,int)) for k,v in value.items()):raise ValueError('campos')
                    elif name=='documents':
                        if not isinstance(value,dict) or any(k not in ('1','2','3') or type(v) is not int for k,v in value.items()):raise ValueError('enlaces')
                    elif name=='keys':
                        if not isinstance(value,list) or len(value)!=7 or any(not isinstance(v,str) for v in value):raise ValueError('claves')
                    elif not isinstance(value,str):raise ValueError('texto')
        if any(type(v) is not int or not 0<=v<24 for v in data['unsupported']):raise ValueError('tabla')
    except (ValueError,TypeError,ArithmeticError) as exc:
        raise BudgetError('Dato inválido en conversión PZH: '+str(exc)) from exc
    ids={r.id for r in budget.relations}
    if any(r.get('relation_id') not in ids for k in ('activities','phases') for r in data[k]):
        raise BudgetError('La planificación PZH referencia una relación inexistente')
    if any(r.get('before') not in ids or r.get('after') not in ids for r in data['precedences']):
        raise BudgetError('Precedencia PZH sin relación')
    return data


def table(budget,kind):
    data=validate(budget)
    if kind=='pzh_rejected':
        rows=rejected_records(budget)
        return ('Tabla de origen','Registro de origen','Motivo sin conversión'),[(r['table'],r['record'],r['reason']) for r in rows]
    if kind=='pzh_plan':
        return ('Capítulo','Partida','Inicio previsto','Final previsto','Inicio real','Final real','Cantidad objetivo','Precio objetivo','Cantidad plan','Precio plan (objetivo)'),[(r['parent'],r['code'],r['planned_start'] or '',r['planned_finish'] or '',r['actual_start'] or '',r['actual_finish'] or '',r['objective_quantity'],r['objective_price'],r['planned_quantity'],r['objective_price']) for r in data.get('activities',[])]
    if kind=='pzh_phases':return ('Relación','Fase','Cantidad planificada','Acumulado de origen'),[(r['relation_id'],r['phase'],r['quantity'],r['cumulative']) for r in data.get('phases',[])]
    if kind=='pzh_edges':return ('Precedente','Sucesora'),[(r['before'],r['after']) for r in data.get('precedences',[])]
    if kind=='pzh_entities':return ('Código','Nombre','Contacto'),[(r['code'],r['name'],r['contact']) for r in data.get('entities',[])]
    if kind=='pzh_offers':return ('Concepto','Entidad','Fecha','Precio'),[(r['code'],r['entity'],r['date'] or '',r['price']) for r in data.get('offers',[])]
    if kind=='pzh_documents':return ('Fecha','Referencia','Entidad','Tipo original','Emitido','Proforma','Pagado guardado','Base factura guardada','Base calculada','Diferencia base','Suministros','Nota'),[(r['date'] or '',r['reference'],r['entity'],r['kind'],r['issued'],r['proforma'],r['amount'] if r['amount'] is not None else '',r['invoice_base'] if r['invoice_base'] is not None else '',r['calculated_base'] if r['kind']!=5 else '',r['base_difference'] if r['base_difference'] is not None else '',r['linked_supplies'],r['note']) for r in data.get('documents',[])]
    if kind=='pzh_supplies':
        quantities=effective_quantities(data)
        return ('Fecha imputación','Concepto','Destino','Cantidad propia','Cantidad aplicada','Heredada del contrato','Precio','Importe neto','Documentos de origen'),[(r['date'] or '',r['code'],r['destination'],r['quantity'] if '11' in r['fields'] else '',str(quantities[r['id']][0]),quantities[r['id']][1],r['price'],r['amount'],str(r['documents'])) for r in data.get('supplies',[])]
    if kind=='pzh_contracts':
        names={r['code']:r['name'] for r in data.get('entities',[])};rows=[]
        for doc in data.get('documents',[]):
            if doc['kind']!=1 or not doc['proforma'] or not doc['entity']:continue
            rows.append((doc['reference'],doc['entity'],names.get(doc['entity'],''),doc['linked_supplies'],doc['calculated_base'],doc['fields'].get('8','0'),doc['base_difference']))
        return ('Contrato','Entidad ofertante','Nombre','Suministros','Oferta calculada','Oferta guardada','Diferencia'),rows
    if kind=='pzh_balances':return ('Factura','Entidad','Emitida','Proforma','Base','IVA calculado','Bruto calculado','Vencimientos','Pagado según vencimientos','Pendiente según vencimientos','Retenciones pendientes','Diferencia pagado','Diferencia pendiente','Diferencia bruto / vencimientos','Aviso'),invoice_balances(data)
    if kind=='pzh_dues':return ('Fecha','Factura','Entidad','Tipo retención','Pagado','Importe','Nota'),[(r['date'] or '',r['reference'],r['entity'],r['kind'],r['paid'],r['amount'],r['note']) for r in data.get('dues',[])]
    raise BudgetError('Informe PZH desconocido')

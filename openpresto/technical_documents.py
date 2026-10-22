"""Native editable plain-text documents with immutable source provenance."""
import json,re,base64,hashlib,binascii
from uuid import uuid4
from .budget import BudgetError

KEY='technical_documents_v1'
HEADERS=('ID','Referencia','Título','Caracteres','Código de origen')


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>10000:raise BudgetError('Demasiados documentos técnicos')
        ids=set();refs=set();sources=set();size=0
        for row in data:
            if not isinstance(row,dict) or set(row) not in ({'id','reference','title','text','source'},{'id','reference','title','text','source','source_payload'}):raise BudgetError('Columnas de documento técnico inválidas')
            for key in ('id','reference','title'):
                if not isinstance(row[key],str) or not row[key].strip() or len(row[key])>10000:raise BudgetError('Identidad de documento técnico inválida')
            if row['id'] in ids or row['reference'].strip().casefold() in refs:raise BudgetError('Documento técnico repetido')
            ids.add(row['id']);refs.add(row['reference'].strip().casefold())
            if not isinstance(row['text'],str) or len(row['text'])>4*1024*1024:raise BudgetError('Texto de documento técnico fuera de límites')
            size+=len(row['text'].encode('utf-8'))
            if size>64*1024*1024:raise BudgetError('Los textos técnicos superan 64 MiB')
            source=row['source']
            if source is not None:
                if not isinstance(source,dict) or set(source)!={'sha256','code','offset'} or not isinstance(source['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',source['sha256']) or not isinstance(source['code'],str) or not source['code'] or len(source['code'])>13 or type(source['offset']) is not int or not 0<=source['offset']<64*1024*1024:raise BudgetError('Procedencia de documento técnico inválida')
                identity=source['sha256'],source['code']
                if identity in sources:raise BudgetError('Texto de origen copiado dos veces')
                sources.add(identity)
            if 'source_payload' in row:
                if source is None:raise BudgetError('Contenido original sin procedencia')
                payload=_payload_bytes(row['source_payload']);size+=len(payload)
                if size>64*1024*1024:raise BudgetError('Los documentos técnicos superan 64 MiB')
        return data
    except (TypeError,ValueError) as exc:raise BudgetError('Documentos técnicos inválidos: '+str(exc)) from exc


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def set_document(budget,reference,title,text,document_id=None):
    data=validate(budget);old=next((r for r in data if r['id']==document_id),None)
    if document_id is not None and old is None:raise BudgetError('Documento técnico inexistente')
    row=dict(id=old['id'] if old else uuid4().hex,reference=reference,title=title,text=text,source=old['source'] if old else None)
    if old and 'source_payload' in old:row['source_payload']=old['source_payload']
    _save(budget,[row if r['id']==row['id'] else r for r in data] if old else data+[row])


def copy_source(budget,code):
    from .pzh_entity_texts import read
    from .pzh_archive import pzh_archive_inventory
    data=validate(budget);inventory=pzh_archive_inventory(budget)
    if inventory is None:raise BudgetError('Este proyecto no conserva un PZH')
    existing=next((r for r in data if r['source'] and r['source']['sha256']==inventory['sha256'] and r['source']['code']==code),None)
    if existing:
        attach_original(budget,existing['id']);return
    source=read(budget,code,include_payload=True)
    row=dict(id=uuid4().hex,reference='PZH:'+code,title=source['title'] or code,text=source['text'],source=dict(sha256=source['sha256'],code=code,offset=source['offset']))
    payload=source['payload']
    row['source_payload']=dict(format='rtf' if payload.startswith(b'{\\rtf') else 'text-cp1252',bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),data=base64.b64encode(payload).decode('ascii'))
    _save(budget,data+[row])


def _payload_bytes(payload):
    if not isinstance(payload,dict) or set(payload)!={'format','bytes','sha256','data'} or payload['format'] not in ('rtf','text-cp1252') or type(payload['bytes']) is not int or not 0<=payload['bytes']<=16*1024*1024 or not isinstance(payload['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',payload['sha256']) or not isinstance(payload['data'],str) or len(payload['data'])>24*1024*1024:raise BudgetError('Contenido original de documento inválido')
    try:raw=base64.b64decode(payload['data'],validate=True)
    except (ValueError,binascii.Error) as exc:raise BudgetError('Contenido original de documento dañado') from exc
    if len(raw)!=payload['bytes'] or hashlib.sha256(raw).hexdigest()!=payload['sha256'] or (payload['format']=='rtf')!=raw.startswith(b'{\\rtf'):raise BudgetError('La huella o formato del documento original no coincide')
    return raw


def original_payload(budget,document_id):
    row=next((r for r in validate(budget) if r['id']==document_id),None)
    if row is None or 'source_payload' not in row:raise BudgetError('Esta copia no conserva un documento original separado; vuelve a adjuntarlo desde Origen PZH')
    return _payload_bytes(row['source_payload'])


def attach_original(budget,document_id):
    from .pzh_entity_texts import read_payload
    data=validate(budget);row=next((r for r in data if r['id']==document_id),None)
    if row is None or row['source'] is None:raise BudgetError('Selecciona una copia de un texto PZH')
    if 'source_payload' in row:return
    source=read_payload(budget,row['source']['code'])
    if source['sha256']!=row['source']['sha256'] or source['offset']!=row['source']['offset']:raise BudgetError('El documento no pertenece al PZH conservado')
    payload=source['payload']
    row['source_payload']=dict(format='rtf' if payload.startswith(b'{\\rtf') else 'text-cp1252',bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),data=base64.b64encode(payload).decode('ascii'))
    _save(budget,data)


def remove_document(budget,document_id):
    data=validate(budget)
    if not any(r['id']==document_id for r in data):raise BudgetError('Documento técnico inexistente')
    _save(budget,[r for r in data if r['id']!=document_id])


def report_rows(budget):
    return [(r['id'],r['reference'],r['title'],len(r['text']),r['source']['code'] if r['source'] else '') for r in validate(budget)]

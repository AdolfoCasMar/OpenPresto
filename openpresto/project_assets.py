"""Editable attachment inventory with lazy original streams in the source snapshot."""
import json
from .budget import BudgetError
from . import pzh_assets
from . import rich_documents
from .pzh_archive import pzh_archive_inventory

KEY='project_assets_v1'
HEADERS=('ID','Referencia','Título','Tabla de origen','Clave de origen','Bytes originales','Texto editado','Nota')


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>10000:raise BudgetError('Inventario de adjuntos inválido')
        if not data:return data
        archive=pzh_archive_inventory(budget)
        if archive is None:raise BudgetError('Falta el PZH conservado de los adjuntos')
        sources={(r['table'],r['code']):r for r in pzh_assets.catalogue(budget)};ids=set();refs=set();origins=set();size=0
        for row in data:
            if not isinstance(row,dict) or set(row)-{'rich_text'}!={'id','reference','title','note','text','source'}:raise BudgetError('Columnas de adjunto inválidas')
            for key in ('id','reference','title','note'):
                if not isinstance(row[key],str) or len(row[key])>100000 or (key!='note' and not row[key].strip()):raise BudgetError('Identidad de adjunto inválida')
            source=row['source']
            if not isinstance(source,dict) or set(source)!={'sha256','table','code','offset','bytes'} or source['sha256']!=archive['sha256'] or type(source['table']) is not int or not isinstance(source['code'],str):raise BudgetError('Procedencia de adjunto inválida')
            origin=(source['table'],source['code']);match=sources.get(origin)
            if match is None or type(source['offset']) is not int or type(source['bytes']) is not int or source['offset']!=match['offset'] or source['bytes']!=match['bytes']:raise BudgetError('El adjunto no corresponde al índice original')
            if row['id'] in ids or row['reference'].casefold() in refs or origin in origins:raise BudgetError('Adjunto repetido')
            ids.add(row['id']);refs.add(row['reference'].casefold());origins.add(origin)
            if row['text'] is not None:
                if source['table'] not in (3,12,20,23) or not isinstance(row['text'],str) or len(row['text'])>4*1024*1024:raise BudgetError('Texto editable de adjunto inválido')
                size+=len(row['text'].encode('utf-8'))
            if 'rich_text' in row:
                if source['table'] not in (3,12,20,23) or rich_documents.plain_text(row['rich_text'])!=row['text']:
                    raise BudgetError('El texto con formato no coincide con su copia de texto')
            if size>64*1024*1024:raise BudgetError('Los textos de adjuntos superan 64 MiB')
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Inventario de adjuntos inválido') from exc


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def copy_source(budget):
    archive=pzh_archive_inventory(budget)
    if archive is None:raise BudgetError('Falta el original PZH')
    data=validate(budget);existing={(r['source']['table'],r['source']['code']) for r in data}
    for source in pzh_assets.catalogue(budget):
        if (source['table'],source['code']) in existing:continue
        ref=f"PZH:{source['table']}:{source['code']}"
        data.append(dict(id=archive['sha256']+':'+ref,reference=ref,title=source['label']+' · '+source['code'],note='',text=None,source=dict(sha256=archive['sha256'],table=source['table'],code=source['code'],offset=source['offset'],bytes=source['bytes'])))
    if data:_save(budget,data)
    budget.project_metadata.pop('pzh_assets_pending',None)


def read(budget,asset_id):
    row=next((r for r in validate(budget) if r['id']==asset_id),None)
    if row is None:raise BudgetError('Adjunto inexistente')
    source=row['source'];stream=pzh_assets.read(budget,source['table'],source['code'])
    return dict(row,original=stream,text=row['text'] if row['text'] is not None else stream['text'])


def set_asset(budget,asset_id,title,note,text=None):
    data=validate(budget);row=next((r for r in data if r['id']==asset_id),None)
    if row is None:raise BudgetError('Adjunto inexistente')
    row.update(title=title,note=note)
    if text is not None:
        row['text']=text
        row.pop('rich_text',None)
    _save(budget,data)


def set_rich_text(budget,asset_id,runs):
    data=validate(budget);row=next((r for r in data if r['id']==asset_id),None)
    if row is None:raise BudgetError('Adjunto inexistente')
    row.update(text=rich_documents.plain_text(runs),rich_text=runs)
    _save(budget,data)


def report_rows(budget):
    return [(r['id'],r['reference'],r['title'],r['source']['table'],r['source']['code'],r['source']['bytes'],'Sí' if r['text'] is not None else 'No',r['note']) for r in validate(budget)]

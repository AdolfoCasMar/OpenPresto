"""Bounded entity-text records and their explicit code/offset index."""
import hashlib,struct
from .budget import BudgetError
from .pzh_archive import pzh_source_bytes
from .pzh_importer import _Reader,_fields,_code,_unpack,MAX_RECORDS
from .pzh_operations import SCHEMAS
from .pzh_text import decompress_pzh_text,rtf_plain_text,MAX_TEXT_BYTES


def _index(budget):
    raw=pzh_source_bytes(budget)
    if raw is None:return None,[]
    reader=_Reader(raw);count,start,index=reader.tables[23]
    if not count:return reader,[]
    if count>MAX_RECORDS or index+count*17>len(raw):raise BudgetError('Índice de textos de entidades PZH truncado')
    entities={}
    for _,_,body in reader.records(10,8):
        if len(body)<13:raise BudgetError('Entidad PZH incompleta')
        code=_code(body[:13]);fields=_fields(body[13:],SCHEMAS[10],'Entidad PZH')
        if code in entities:raise BudgetError('Código de entidad PZH repetido')
        entities[code]=fields.get(3,'')
    records={}
    for offset,_,record in reader.records(23,0):
        if len(record)<17 or record[8] not in (1,2):raise BudgetError('Formato de texto de entidad PZH desconocido')
        unpacked,packed=_unpack(record,9,'II')
        if packed!=len(record)-17 or unpacked>MAX_TEXT_BYTES:raise BudgetError('Texto de entidad PZH fuera de límites')
        records[offset]=(len(record),unpacked,packed)
    rows=[];codes=set();offsets=set()
    for i in range(count):
        at=index+i*17;code=_code(raw[at:at+13]);offset,=_unpack(raw,at+13,'I')
        if code not in entities or offset not in records or code in codes or offset in offsets:raise BudgetError('Vínculo del índice de textos de entidades PZH inválido')
        codes.add(code);offsets.add(offset);size,unpacked,packed=records[offset]
        rows.append(dict(code=code,title=entities[code],offset=offset,size=size,unpacked=unpacked,packed=packed))
    return reader,rows


def catalogue(budget):
    return _index(budget)[1]


def read_payload(budget,code):
    if not isinstance(code,str):raise BudgetError('Código de texto PZH inválido')
    reader,rows=_index(budget);row=next((r for r in rows if r['code']==code),None)
    if row is None:raise BudgetError('Texto de entidad PZH inexistente')
    record=reader.data[row['offset']:row['offset']+row['size']];payload=record[17:]
    raw=decompress_pzh_text(payload,row['unpacked']) if row['unpacked']!=row['packed'] else payload
    if len(raw)!=row['unpacked']:raise BudgetError('La longitud del texto de entidad no coincide con su cabecera')
    return dict(row,payload=raw,sha256=hashlib.sha256(reader.data).hexdigest())


def read(budget,code,include_payload=False):
    source=read_payload(budget,code);raw=source.pop('payload')
    try:text=rtf_plain_text(raw) if raw.startswith(bytes((123,92))+b'rtf') else raw.rstrip(b'\0').decode('cp1252')
    except UnicodeError as exc:raise BudgetError('Codificación de texto de entidad PZH no admitida') from exc
    if include_payload:source['payload']=raw
    return dict(source,text=text)

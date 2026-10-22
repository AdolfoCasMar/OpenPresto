"""Indexed original text/image/drawing streams, decoded only when requested."""
import hashlib,struct
from .budget import BudgetError
from .pzh_importer import _Reader,_code,_unpack
from .pzh_archive import pzh_source_bytes
from .pzh_text import MAX_TEXT_BYTES,decompress_pzh_text,rtf_plain_text

TABLES={3:'Texto 2',12:'Anotación',20:'Texto asociado',21:'Imagen',22:'Dibujo',23:'Texto de entidad'}
_CACHE=(None,())


def _wmf_stream(raw):
    # MS-WMF META_HEADER/record lengths are WORD counts. Keep any outer bytes.
    if len(raw)<32:return None
    kind,header,version,words=struct.unpack_from('<HHHI',raw,8)
    end=8+words*2
    if kind not in (1,2) or header!=9 or version not in (0x100,0x300) or words<12 or end>len(raw):return None
    at=26;records=0
    while at+6<=end:
        size,function=struct.unpack_from('<IH',raw,at);records+=1
        if size<3 or at+size*2>end or records>1000000:return None
        if function==0:return raw[8:end] if size==3 and at+6==end else None
        at+=size*2
    return None


def _wmf_eof_repair(raw):
    """Recognize only a zero-sized final EOF; never repair geometry or bounds."""
    if len(raw)<32:return None
    kind,header,version,words=struct.unpack_from('<HHHI',raw,8);end=8+words*2
    if kind not in (1,2) or header!=9 or version not in (0x100,0x300) or words<12 or end>len(raw):return None
    at=26;records=0
    while at+6<=end:
        size,function=struct.unpack_from('<IH',raw,at);records+=1
        if records>1000000:return None
        if size==0 and function==0 and at+6==end and len(raw)-end<=16 and not any(raw[end:]):
            fixed=bytearray(raw);struct.pack_into('<I',fixed,at,3);stream=_wmf_stream(bytes(fixed))
            return dict(data=stream,offset=at,old_size=0,new_size=3) if stream is not None else None
        if size<3 or at+size*2>end or function==0:return None
        at+=size*2
    return None


def _catalogue(budget):
    raw=pzh_source_bytes(budget)
    if raw is None:return None,[]
    reader=_Reader(raw);rows=[]
    for table,label in TABLES.items():
        count,start,index=reader.tables[table]
        if not count:continue
        boundary=reader.tables[table+1][1] if table<23 else len(raw)
        if index+count*17>boundary:raise BudgetError('Índice de documentos PZH fuera de límites')
        records={}
        for offset,_,record in reader.records(table,0):
            if len(record)<17:raise BudgetError('Cabecera de documento PZH incompleta')
            unpacked,packed=_unpack(record,9,'II')
            if packed!=len(record)-17 or unpacked>MAX_TEXT_BYTES:raise BudgetError('Documento PZH fuera de límites')
            records[offset]=(len(record),unpacked,packed,record[8])
        codes=set();offsets=set()
        for i in range(count):
            at=index+i*17;code=_code(raw[at:at+13]);offset,=_unpack(raw,at+13,'I')
            if not code or code in codes or offset in offsets or offset not in records:raise BudgetError('Vínculo de documento PZH inválido o repetido')
            codes.add(code);offsets.add(offset);size,unpacked,packed,kind=records[offset]
            rows.append(dict(table=table,code=code,offset=offset,size=size,bytes=unpacked,packed=packed,kind=kind,label=label))
    return reader,rows


def catalogue(budget):
    # One immutable archive identity and small index only; no decompressed streams.
    global _CACHE
    archive=budget.project_metadata.get('pzh_source_archive_v1');cached=_CACHE
    if archive is None:return []
    if cached[0] is not archive:
        _,rows=_catalogue(budget);cached=(archive,tuple(tuple(r.items()) for r in rows));_CACHE=cached
    return [dict(row) for row in cached[1]]


def clear_cache():
    global _CACHE
    _CACHE=(None,())


def read(budget,table,code):
    if type(table) is not int or table not in TABLES or not isinstance(code,str):raise BudgetError('Identidad de documento PZH inválida')
    row=next((r for r in catalogue(budget) if r['table']==table and r['code']==code),None)
    if row is None:raise BudgetError('Documento PZH inexistente')
    reader=_Reader(pzh_source_bytes(budget))
    payload=reader.data[row['offset']+17:row['offset']+row['size']]
    # Kind identifies the stream format, not whether equal-sized data is compressed.
    raw=decompress_pzh_text(payload,row['bytes']) if row['bytes']!=row['packed'] else payload
    if len(raw)!=row['bytes']:raise BudgetError('La longitud del documento PZH no coincide')
    fmt='bin';text=None;export=raw;repair=None
    if table in (3,12,20,23):
        fmt='rtf' if raw.startswith(b'{\\rtf') else 'txt'
        try:text=rtf_plain_text(raw) if fmt=='rtf' else raw.rstrip(b'\0').decode('cp1252')
        except UnicodeError as exc:raise BudgetError('Texto PZH no decodificable') from exc
    elif raw.startswith(b'\xff\xd8\xff'):fmt='jpg'
    elif raw.startswith(b'BM'):fmt='bmp'
    elif raw.startswith(b'\x89PNG\r\n\x1a\n'):fmt='png'
    elif raw.startswith((b'GIF87a',b'GIF89a')):fmt='gif'
    elif len(raw)>=6 and raw[:2]==b'AC' and raw[2:6].isdigit():fmt='dwg'
    elif len(raw)>=26:
        wmf=_wmf_stream(raw)
        if wmf is not None:fmt='wmf';export=wmf
        else:
            repair=_wmf_eof_repair(raw)
            if repair is not None:fmt='wmf-damaged'
    return dict(row,payload=raw,export=export,format=fmt,text=text,repair=repair,sha256=hashlib.sha256(raw).hexdigest())

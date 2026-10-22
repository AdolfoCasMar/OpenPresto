"""Bounded extraction of inert RTF picture destinations; never activates OLE."""
import hashlib
import re
import struct
from .budget import BudgetError
from .pzh_text import MAX_TEXT_BYTES
from .wmf_vector import records as wmf_records

MAX_PICTURES=128
_SPECIAL=re.compile(rb'[{}\\]')
_FORMATS={'pngblip':'png','jpegblip':'jpg','wmetafile':'wmf','emfblip':'emf','dibitmap':'dib','wbitmap':'bin','macpict':'pct','pmmetafile':'bin'}
_PROPERTIES={'picw','pich','picwgoal','pichgoal','picscalex','picscaley','piccropt','piccropb','piccropl','piccropr','wbmbitspixel','wbmplanes','wbmwidthbytes'}


def dib_bitmap(payload):
    """Wrap a bounded 40-byte, uncompressed RGB DIB for a portable BMP reader."""
    if not isinstance(payload,bytes) or not 40<=len(payload)<=MAX_TEXT_BYTES:raise BudgetError('DIB fuera de límites')
    header,width,height,planes,bits,compression,image_size,xppm,yppm,colors,important=struct.unpack_from('<IiiHHIIiiII',payload)
    if header!=40 or width<=0 or not height or width>20000 or abs(height)>20000 or width*abs(height)>16000000 or planes!=1 or compression!=0 or bits not in (1,4,8,24,32):raise BudgetError('Variante DIB no representada')
    if colors>256 or (bits<=8 and colors>1<<bits):raise BudgetError('Paleta DIB fuera de límites')
    count=colors or ((1<<bits) if bits<=8 else 0);offset=40+count*4;needed=((width*bits+31)//32)*4*abs(height)
    if offset+needed>len(payload) or image_size not in (0,needed):raise BudgetError('Datos DIB incompletos o longitud incompatible')
    return struct.pack('<2sIHHI',b'BM',14+len(payload),0,0,14+offset)+payload


def wmf_stream(payload):
    """Strip only a verified Aldus placeable header; keep the original separately."""
    stream=payload
    if payload.startswith(b'\xd7\xcd\xc6\x9a'):
        if len(payload)<22:raise BudgetError('Cabecera WMF incrustada incompleta')
        values=struct.unpack_from('<11H',payload);checksum=0
        for value in values[:10]:checksum^=value
        if checksum!=values[10]:raise BudgetError('La cabecera WMF incrustada no supera su comprobación')
        stream=payload[22:]
    wmf_records(stream)
    return stream


def scan(data):
    if not isinstance(data,bytes) or not data.startswith(b'{\\rtf') or len(data)>MAX_TEXT_BYTES:
        raise BudgetError('RTF de imágenes no reconocido o fuera de límites')
    stack=[];pictures=[];objects=0;at=0;closed_root=False;total=0
    def append(frame,chunk,mode):
        if not chunk:return
        picture=frame['picture']
        if picture['mode'] not in (None,mode):raise BudgetError('Imagen RTF con datos binarios y hexadecimales mezclados')
        picture['mode']=mode;picture['chunks'].append(chunk);picture['encoded_size']+=len(chunk)
        if picture['encoded_size']>MAX_TEXT_BYTES:raise BudgetError('Imagen RTF fuera de límites')
    def finish(frame,end):
        nonlocal total
        picture=frame['picture'];warnings=[]
        if picture['mode']=='hex':
            encoded=b''.join(picture['chunks'])
            try:payload=bytes.fromhex(encoded.decode('ascii'))
            except (ValueError,UnicodeError) as exc:raise BudgetError('Datos hexadecimales de imagen RTF inválidos') from exc
        else:payload=b''.join(picture['chunks'])
        total+=len(payload)
        if total>MAX_TEXT_BYTES:raise BudgetError('Las imágenes RTF superan el límite de memoria')
        declared=picture['formats'];fmt=next(iter(declared)) if len(declared)==1 else 'bin'
        if len(declared)>1:warnings.append('Varios formatos declarados; se conserva el contenido sin interpretarlo')
        if fmt=='png' and not payload.startswith(b'\x89PNG\r\n\x1a\n'):
            fmt='bin';warnings.append('La firma no coincide con la imagen PNG declarada')
        if fmt=='jpg' and not payload.startswith(b'\xff\xd8\xff'):
            fmt='bin';warnings.append('La firma no coincide con la imagen JPEG declarada')
        if fmt=='wmf':
            try:wmf_stream(payload)
            except BudgetError:fmt='bin';warnings.append('Metarchivo incrustado no reconocido o incompleto')
        if not payload:warnings.append('Imagen sin contenido')
        pictures.append(dict(id=len(pictures)+1,format=fmt,declared=sorted(declared),data=payload,sha256=hashlib.sha256(payload).hexdigest(),properties=picture['properties'],role=frame['role'],object_preview=frame['object'],offset=frame['start'],end=end,warnings=warnings))
    while at<len(data):
        char=data[at];at+=1
        if char==123:
            if closed_root or len(stack)>=256:raise BudgetError('Grupos RTF fuera de límites')
            parent=stack[-1] if stack else None
            stack.append(dict(start=at-1,destination=None,picture=None,role=parent['role'] if parent else 'normal',object=parent['object'] if parent else False))
        elif char==125:
            if not stack:raise BudgetError('Cierre RTF sin grupo')
            frame=stack.pop()
            if frame['picture'] is not None:finish(frame,at)
            if not stack:closed_root=True
        elif char==92:
            if not stack or at>=len(data):raise BudgetError('Escape RTF fuera de grupo o incompleto')
            frame=stack[-1];symbol=data[at];at+=1
            if 65<=symbol<=90 or 97<=symbol<=122:
                start=at-1
                while at<len(data) and (65<=data[at]<=90 or 97<=data[at]<=122):at+=1
                word=data[start:at].decode('ascii');start=at
                if at<len(data) and data[at]==45:at+=1
                while at<len(data) and 48<=data[at]<=57:at+=1
                value=data[start:at]
                if len(value)>11:raise BudgetError('Parámetro RTF fuera de límites')
                number=int(value) if value not in (b'',b'-') else None
                if number is not None and not -2147483648<=number<=2147483647:raise BudgetError('Parámetro RTF fuera de rango')
                if at<len(data) and data[at]==32:at+=1
                first=frame['destination'] is None
                if first:frame['destination']=word
                if first and word in ('shppict','nonshppict'):frame['role']=word
                if first and word=='object':objects+=1;frame['object']=True
                if first and word=='pict':
                    if any(parent['picture'] is not None for parent in stack[:-1]):raise BudgetError('Imagen RTF anidada dentro de otra imagen')
                    if len(pictures)>=MAX_PICTURES:raise BudgetError('El RTF supera 128 imágenes')
                    frame['picture']=dict(mode=None,chunks=[],encoded_size=0,formats=set(),properties={})
                picture=frame['picture']
                if picture is not None:
                    if word in _FORMATS:picture['formats'].add(_FORMATS[word])
                    if word in _PROPERTIES and number is not None:picture['properties'][word]=number
                if word=='bin':
                    if number is None or number<0 or at+number>len(data):raise BudgetError('Bloque binario RTF incompleto')
                    if picture is not None:append(frame,data[at:at+number],'bin')
                    at+=number
            elif symbol==39:
                if at+2>len(data) or any(c not in b'0123456789abcdefABCDEF' for c in data[at:at+2]):raise BudgetError('Escape hexadecimal RTF inválido')
                if frame['picture'] is not None:raise BudgetError('Escapes de texto dentro de una imagen RTF no admitidos')
                at+=2
            elif frame['picture'] is not None and symbol not in (42,10,13):
                raise BudgetError('Escape de texto dentro de una imagen RTF no admitido')
        else:
            match=_SPECIAL.search(data,at);end=match.start() if match else len(data);chunk=data[at-1:end];at=end
            if not stack:
                if chunk.strip(b' \t\r\n\0'):raise BudgetError('Datos fuera del documento RTF')
            elif stack[-1]['picture'] is not None:
                chunk=chunk.translate(None,b' \t\r\n');append(stack[-1],chunk,'hex')
    if stack or not closed_root:raise BudgetError('RTF de imágenes sin cierre')
    return dict(pictures=pictures,objects=objects)

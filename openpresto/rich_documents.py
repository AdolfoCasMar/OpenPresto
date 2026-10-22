"""Portable native text runs and RTF export; no UI or external resources."""
from html import escape
import math
import re
from .budget import BudgetError

FIELDS={'text','bold','italic','underline','strike','size'}
EXTRA_FIELDS={'color','alignment'}
ALIGNMENTS={'left','center','right','justify'}
MAX_BYTES=4*1024*1024


def validate(runs):
    if not isinstance(runs,list) or len(runs)>100000:
        raise BudgetError('Documento con formato inválido')
    total=0
    for row in runs:
        if not isinstance(row,dict) or not FIELDS<=set(row) or set(row)-FIELDS-EXTRA_FIELDS or not isinstance(row['text'],str):
            raise BudgetError('Fragmento de texto con formato inválido')
        if any(type(row[k]) is not bool for k in ('bold','italic','underline','strike')):
            raise BudgetError('Estilo de texto inválido')
        if 'color' in row and (not isinstance(row['color'],str) or re.fullmatch(r'#[0-9a-f]{6}',row['color']) is None):
            raise BudgetError('Color de texto inválido')
        if 'alignment' in row and (not isinstance(row['alignment'],str) or row['alignment'] not in ALIGNMENTS):
            raise BudgetError('Alineación de párrafo inválida')
        size=row['size']
        if type(size) not in (int,float) or not math.isfinite(size) or not 1<=size<=200 or size*2!=int(size*2):
            raise BudgetError('Tamaño de letra inválido: usa medios puntos entre 1 y 200')
        try:total+=len(row['text'].encode('utf-8'))
        except UnicodeError as exc:raise BudgetError('Texto Unicode inválido') from exc
        if total>MAX_BYTES:raise BudgetError('El documento con formato supera 4 MiB')
    return runs


def plain_text(runs):
    return ''.join(row['text'] for row in validate(runs))


def from_plain(text):
    return validate([dict(text=text,bold=False,italic=False,underline=False,strike=False,size=12)])


def to_html(runs):
    parts=[];paragraph=[];alignment='left'
    for row in validate(runs):
        for index,text in enumerate(row['text'].split('\n')):
            if index:
                parts.append(f'<p style="text-align:{alignment}">'+''.join(paragraph)+'</p>');paragraph=[]
            alignment=row.get('alignment','left')
            value=escape(text).replace('\t','&#160;&#160;&#160;&#160;')
            for field,tag in (('bold','b'),('italic','i'),('underline','u'),('strike','s')):
                if row[field]:value=f'<{tag}>{value}</{tag}>'
            css=f'font-size:{row["size"]}pt'+(f';color:{row["color"]}' if 'color' in row else '')
            paragraph.append(f'<span style="{css}">{value}</span>')
    parts.append(f'<p style="text-align:{alignment}">'+''.join(paragraph)+'</p>')
    return ''.join(parts)


def to_rtf(runs):
    validate(runs)
    colors=list(dict.fromkeys(row['color'] for row in runs if 'color' in row))
    if len(colors)>4095:raise BudgetError('La exportación RTF admite hasta 4.095 colores distintos')
    color_ids={color:index+1 for index,color in enumerate(colors)}
    result=['{\\rtf1\\ansi\\ansicpg1252\\uc1 ']
    if colors:
        result.append('{\\colortbl ;')
        for color in colors:
            result.append(''.join('\\'+channel+str(int(color[at:at+2],16)) for channel,at in (('red',1),('green',3),('blue',5)))+';')
        result.append('}')
    for row in runs:
        result.append('{\\plain\\fs'+str(int(row['size']*2)))
        result.append('\\'+{'left':'ql','center':'qc','right':'qr','justify':'qj'}[row.get('alignment','left')])
        if 'color' in row:result.append('\\cf'+str(color_ids[row['color']]))
        for field,control in (('bold','b'),('italic','i'),('underline','ul'),('strike','strike')):
            if row[field]:result.append('\\'+control)
        result.append(' ')
        for char in row['text']:
            if char in '{}\\':result.append('\\'+char)
            elif char=='\n':result.append('\\par\n')
            elif char=='\t':result.append('\\tab ')
            elif 32<=ord(char)<127:result.append(char)
            else:
                raw=char.encode('utf-16-le')
                for at in range(0,len(raw),2):
                    unit=int.from_bytes(raw[at:at+2],'little');result.append('\\u'+str(unit if unit<32768 else unit-65536)+'?')
        result.append('}')
    result.append('}')
    return ''.join(result).encode('ascii')

"""Bounded MS-WMF geometric SVG projection, independent of Windows and Qt.

This is a diagnostic preview, not a GDI emulator. Unsupported records are
reported. Output contains only generated geometry and escaped local text.
"""
import copy
import math
from html import escape
import struct
from .budget import BudgetError

MAX_BYTES=16*1024*1024
MAX_RECORDS=100000
MAX_POINTS=500000
OMITTED={0xa32:'Texto con espaciado avanzado no representado',0xf43:'Imagen incrustada de mapa de bits no representada',0x626:'Extensiones de impresión no representadas',0x234:'Selección de paleta no representada',0x35:'Aplicación de paleta no representada',0x412:'Escala de ventana adicional no representada',0x20a:'Desplazamiento de recorte no representado'}


def records(data):
    if not isinstance(data,bytes) or not 24<=len(data)<=MAX_BYTES:raise BudgetError('WMF fuera de límites')
    kind,header,version,words,objects,maximum,reserved=struct.unpack_from('<HHHIHIH',data)
    if kind not in (1,2) or header!=9 or version not in (0x100,0x300) or words*2!=len(data) or objects>10000:raise BudgetError('Cabecera WMF no admitida')
    rows=[];at=18
    while at+6<=len(data):
        size,function=struct.unpack_from('<IH',data,at)
        if size<3 or at+size*2>len(data) or len(rows)>=MAX_RECORDS:raise BudgetError('Registro WMF fuera de límites')
        payload=data[at+6:at+size*2];rows.append((function,payload));at+=size*2
        if function==0:
            if size!=3 or at!=len(data):raise BudgetError('Cierre WMF inválido')
            return rows
    raise BudgetError('WMF sin cierre')


def preview(data):
    rows=records(data);extent=next((struct.unpack('<hh',p) for f,p in rows if f==0x20c and len(p)==4),None)
    if not extent or not extent[0] or not extent[1]:raise BudgetError('El WMF no declara una ventana de dibujo utilizable')
    height,width=abs(extent[0]),abs(extent[1]);warnings=set();objects=[];saved=[];parts=[];points=0;drawn=0
    state=dict(origin=(0,0),extent=(extent[1],extent[0]),pen=(0,0,'#000000'),brush=(0,'#ffffff'),font=None,pos=(0,0),fill=1,clip=None,text='#000000',align=0,bgmode=1,bgcolor='#ffffff',rop=13)
    def unpack(payload,fmt):
        if len(payload)!=struct.calcsize('<'+fmt):raise BudgetError('Parámetros WMF incompletos')
        return struct.unpack('<'+fmt,payload)
    def color(value):
        if value>>24:
            warnings.add('Colores indexados en paleta');return None
        return '#%02x%02x%02x'%(value&255,(value>>8)&255,(value>>16)&255)
    def xml(value):
        if any(ord(char)<32 and char not in '\t\n\r' for char in value):
            warnings.add('Caracteres de control sustituidos en la vista');value=''.join(char if ord(char)>=32 or char in '\t\n\r' else '\ufffd' for char in value)
        return escape(value,quote=True)
    def point(x,y):
        ex,ey=state['extent'];ox,oy=state['origin']
        return (x-ox)*width/ex,(y-oy)*height/ey
    def add(value):
        nonlocal drawn
        if state['rop']!=13:
            warnings.add('Operaciones de mezcla distintas de copia');return
        clip=state['clip']
        if clip is not None:
            x,y,w,h=clip;identifier='clip'+str(drawn);value=f'<defs><clipPath id="{identifier}"><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"/></clipPath></defs><g clip-path="url(#{identifier})">{value}</g>'
        parts.append(value);drawn+=1
        if drawn>MAX_RECORDS:raise BudgetError('Demasiados elementos de dibujo WMF')
    def style(fill=False):
        kind,weight,ink=state['pen'];pen='none' if kind==5 or ink is None else ink
        stroke=abs(weight*width/state['extent'][0]) if weight else width/1000
        dash={1:'4,2',2:'1,2',3:'4,2,1,2',4:'4,2,1,2,1,2'}.get(kind)
        if kind not in (0,1,2,3,4,5):warnings.add('Estilo de pluma no representado');pen='none'
        brushkind,brushink=state['brush'];brush=brushink if fill and brushkind==0 and brushink is not None else 'none'
        if fill and brushkind not in (0,1):warnings.add('Rellenos tramados no representados')
        return f'stroke="{pen}" stroke-width="{stroke:g}" fill="{brush}" fill-rule="'+('evenodd' if state['fill']==1 else 'nonzero')+'"'+(f' stroke-dasharray="{dash}"' if dash else '')
    def make_object(kind,value):
        try:index=objects.index(None)
        except ValueError:index=len(objects);objects.append(None)
        if index>=10000:raise BudgetError('Demasiados objetos WMF')
        objects[index]=(kind,value)
    def rectangle(payload):
        bottom,right,top,left=unpack(payload,'hhhh');x1,y1=point(left,top);x2,y2=point(right,bottom)
        return min(x1,x2),min(y1,y2),abs(x2-x1),abs(y2-y1)
    for function,payload in rows:
        if function==0:break
        if function in (0x20b,0x20c):
            y,x=unpack(payload,'hh')
            if function==0x20c and (not x or not y):raise BudgetError('Ventana WMF de tamaño cero')
            state['origin' if function==0x20b else 'extent']=(x,y)
        elif function==0x2fa:
            if len(payload)==12:
                warnings.add('Extensión de pluma conservada fuera de la vista');payload=payload[:10]
            kind,x,y,ink=unpack(payload,'HhhI');make_object('pen',(kind,x,color(ink)))
        elif function==0x2fc:
            kind,ink,hatch=unpack(payload,'HIH');make_object('brush',(kind,color(ink)))
        elif function==0x2fb:
            if len(payload)<18:raise BudgetError('Fuente WMF incompleta')
            h,w,angle,orientation,weight=struct.unpack_from('<hhhhh',payload);italic,underline,strike,charset=payload[10:14]
            family=payload[18:].split(b'\0',1)[0].decode('cp1252',errors='replace')
            make_object('font',dict(height=h,width=w,angle=angle,orientation=orientation,weight=weight,italic=italic,underline=underline,strike=strike,charset=charset,family=family))
        elif function==0xf7:
            make_object('unknown',function);warnings.add('Paleta no representada')
        elif function==0x12d:
            index,=unpack(payload,'H')
            if index&0x8000:
                stock=index&0x7fff
                if stock in (0,1,2,3,4,5):state['brush']=(1,None) if stock==5 else (0,('#ffffff','#c0c0c0','#808080','#404040','#000000')[stock])
                elif stock in (6,7,8):state['pen']=(5,0,None) if stock==8 else (0,0,'#ffffff' if stock==6 else '#000000')
                else:warnings.add('Objeto de sistema no representado')
            elif index>=len(objects) or objects[index] is None:raise BudgetError('Selección de objeto WMF inexistente')
            else:
                key,value=objects[index]
                if key=='unknown':warnings.add('Objeto gráfico no representado')
                else:state[key]=value
        elif function==0x1f0:
            index,=unpack(payload,'H')
            if index>=len(objects) or objects[index] is None:raise BudgetError('Borrado de objeto WMF inexistente')
            objects[index]=None
        elif function in (0x102,0x104,0x106,0x12e):
            if function in (0x102,0x12e) and len(payload)==4:
                value,=unpack(payload,'I')
                if value>65535:raise BudgetError('Modo WMF DWORD fuera de rango')
                warnings.add('Modo de contexto con extensión DWORD');payload=struct.pack('<H',value)
            value,=unpack(payload,'H');state[{0x102:'bgmode',0x104:'rop',0x106:'fill',0x12e:'align'}[function]]=value
        elif function in (0x201,0x209):
            ink,=unpack(payload,'I');state['bgcolor' if function==0x201 else 'text']=color(ink)
        elif function in (0x103,0x105):
            value,=unpack(payload,'H')
            if function==0x103 and value not in (1,7,8):warnings.add('Modo de escala física no representado')
        elif function==0x1e:
            unpack(payload,'');saved.append(copy.deepcopy(state))
            if len(saved)>256:raise BudgetError('Demasiados estados WMF anidados')
        elif function==0x127:
            level,=unpack(payload,'h');target=len(saved)+level if level<0 else level-1
            if not 0<=target<len(saved):raise BudgetError('Estado WMF para restaurar inexistente')
            state=saved[target];saved=saved[:target]
        elif function==0x416:
            rect=rectangle(payload)
            if state['clip'] is not None:
                x,y,w,h=state['clip'];xx,yy,ww,hh=rect;left,top=max(x,xx),max(y,yy);rect=(left,top,max(0,min(x+w,xx+ww)-left),max(0,min(y+h,yy+hh)-top))
            state['clip']=rect
        elif function in (0x214,0x213):
            y,x=unpack(payload,'hh')
            if function==0x213:
                x1,y1=point(*state['pos']);x2,y2=point(x,y);add(f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" {style()}/>')
            state['pos']=(x,y)
        elif function in (0x325,0x324):
            if len(payload)<2:raise BudgetError('Polilínea WMF incompleta')
            count,=struct.unpack_from('<H',payload);points+=count
            if len(payload)!=2+count*4 or points>MAX_POINTS:raise BudgetError('Puntos WMF fuera de límites')
            coordinates=[point(*struct.unpack_from('<hh',payload,2+i*4)) for i in range(count)];tag='polygon' if function==0x324 else 'polyline';values=' '.join(f'{x:g},{y:g}' for x,y in coordinates);add(f'<{tag} points="{values}" {style(function==0x324)}/>')
        elif function==0x538:
            if len(payload)<2:raise BudgetError('Polígonos WMF incompletos')
            count,=struct.unpack_from('<H',payload)
            if len(payload)<2+count*2:raise BudgetError('Índice de polígonos WMF incompleto')
            sizes=struct.unpack_from('<'+'H'*count,payload,2);total=sum(sizes);points+=total;at=2+count*2
            if len(payload)!=at+total*4 or points>MAX_POINTS:raise BudgetError('Polígonos WMF fuera de límites')
            paths=[]
            for size in sizes:
                coordinates=[point(*struct.unpack_from('<hh',payload,at+i*4)) for i in range(size)];at+=size*4
                if coordinates:paths.append('M'+' L'.join(f'{x:g},{y:g}' for x,y in coordinates)+' Z')
            add('<path d="'+' '.join(paths)+f'" {style(True)}/>')
        elif function in (0x41b,0x418):
            x,y,w,h=rectangle(payload)
            add(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" {style(True)}/>' if function==0x41b else f'<ellipse cx="{x+w/2:g}" cy="{y+h/2:g}" rx="{w/2:g}" ry="{h/2:g}" {style(True)}/>')
        elif function==0x817:
            end_y,end_x,start_y,start_x,bottom,right,top,left=unpack(payload,'hhhhhhhh');cx=(left+right)/2;cy=(top+bottom)/2;rx=abs(right-left)/2;ry=abs(bottom-top)/2
            if not rx or not ry or (start_x==cx and start_y==cy) or (end_x==cx and end_y==cy):
                warnings.add('Arco degenerado no representado');continue
            start=math.atan2(-(start_y-cy)/ry,(start_x-cx)/rx);end=math.atan2(-(end_y-cy)/ry,(end_x-cx)/rx);delta=(end-start)%(2*math.pi);x1,y1=point(cx+rx*math.cos(start),cy-ry*math.sin(start));x2,y2=point(cx+rx*math.cos(end),cy-ry*math.sin(end));center_x,center_y=point(cx,cy);radius_x=abs(rx*width/state['extent'][0]);radius_y=abs(ry*height/state['extent'][1])
            if delta<1e-12:add(f'<ellipse cx="{center_x:g}" cy="{center_y:g}" rx="{radius_x:g}" ry="{radius_y:g}" {style()}/>')
            else:
                sweep=0 if state['extent'][0]*state['extent'][1]>0 else 1;large=int(delta>math.pi);add(f'<path d="M{x1:g},{y1:g} A{radius_x:g},{radius_y:g} 0 {large} {sweep} {x2:g},{y2:g}" {style()}/>')
        elif function==0x41f:
            ink,y,x=unpack(payload,'Ihh');ink=color(ink);xx,yy=point(x,y)
            if ink is not None:add(f'<rect x="{xx:g}" y="{yy:g}" width="{width/1000:g}" height="{height/1000:g}" fill="{ink}"/>')
        elif function==0x521:
            if len(payload)<6:raise BudgetError('Texto WMF incompleto')
            count,=struct.unpack_from('<H',payload);aligned=count+(count%2)
            if len(payload)!=2+aligned+4:raise BudgetError('Longitud de texto WMF incorrecta')
            y,x=struct.unpack_from('<hh',payload,2+aligned);font=state['font']
            if font is None or font['charset'] not in (0,1) or state['align']&1 or state['text'] is None:
                warnings.add('Texto sin fuente o con codificación/posición no representada');continue
            text=payload[2:2+count].decode('cp1252',errors='replace');xx,yy=point(x,y);size=abs(font['height']*height/state['extent'][1])
            if not size: warnings.add('Texto sin tamaño de fuente');continue
            if font['width'] or font['orientation']!=font['angle']:warnings.add('Métricas de fuente aproximadas')
            align=state['align'];anchor='middle' if align&6==6 else 'end' if align&2 else 'start';baseline='alphabetic' if align&24==24 else 'text-after-edge' if align&8 else 'text-before-edge';decoration=' '.join(k for k,flag in (('underline',font['underline']),('line-through',font['strike'])) if flag) or 'none'
            transform=f' transform="rotate({-font["angle"]/10:g} {xx:g} {yy:g})"' if font['angle'] else ''
            add(f'<text x="{xx:g}" y="{yy:g}" font-family="{xml(font["family"])}" font-size="{size:g}" font-weight="{700 if font["weight"]>=700 else 400}" font-style="{"italic" if font["italic"] else "normal"}" text-decoration="{decoration}" text-anchor="{anchor}" dominant-baseline="{baseline}" fill="{state["text"]}"{transform}>{xml(text)}</text>')
            warnings.add('Tipografía aproximada según las fuentes instaladas')
        else:warnings.add(OMITTED.get(function,f'Instrucción gráfica no representada (0x{function:04x})'))
    canvas_w=max(1,round(1000*width/max(width,height)));canvas_h=max(1,round(1000*height/max(width,height)))
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="white"/>'+''.join(parts)+'</svg>').encode('utf-8')
    if len(svg)>8*1024*1024:raise BudgetError('La vista WMF supera 8 MiB')
    return dict(svg=svg,warnings=sorted(warnings),elements=drawn,records=len(rows),width=width,height=height)

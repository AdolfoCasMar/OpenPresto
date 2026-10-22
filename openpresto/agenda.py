"""Dated notes and explicit holidays; source financial figures are not cash entries."""
import json
from decimal import Decimal
from .budget import BudgetError
from .planning import iso
from . import planning

KEY='agenda_v1'
HEADERS=('Fecha','Festivo indicado','Nota','Registro PZH')
TOTALS={4:'Flujo de caja',5:'Impuesto repercutido',6:'Impuesto soportado',7:'Retención fiscal soportada',8:'Retención fiscal repercutida',9:'Garantía soportada',10:'Garantía repercutida',11:'Pagado',12:'Pago previsto',13:'Pago pendiente',14:'Pedidos',15:'Contratos',16:'Entregas',17:'Entregas proforma',18:'Facturado',19:'Facturas proforma',20:'Partes',21:'Facturas a clientes'}


def source_rows(budget):
    from .pzh_archive import pzh_source_bytes
    from .pzh_importer import _Reader,_fields,_unpack
    from .pzh_operations import day
    raw=pzh_source_bytes(budget)
    if raw is None:raise BudgetError('Falta el PZH original de la agenda')
    reader=_Reader(raw);count,_,index=reader.tables[16];records={};rows=[]
    if index+count*6>reader.tables[17][1]:raise BudgetError('Índice de agenda PZH fuera de límites')
    for offset,identifier,body in reader.records(16,8):
        if len(body)<2:raise BudgetError('Fecha de agenda PZH incompleta')
        serial,=_unpack(body,0,'H');date=day(serial)
        if date is None:raise BudgetError('Agenda PZH sin fecha explícita')
        fields=_fields(body[2:],{1:'H',2:'B',3:'s',**{n:'d' for n in range(4,22)}},'Agenda PZH')
        if fields.get(2,0) not in (0,1):raise BudgetError('Festivo PZH fuera del perfil comprobado')
        records[offset]=(serial,identifier,date,{str(k):str(v) if isinstance(v,Decimal) else v for k,v in fields.items()})
    dates=set();offsets=set()
    for i in range(count):
        serial,offset=_unpack(raw,index+i*6,'HI');record=records.get(offset)
        if record is None or record[0]!=serial or serial in dates or offset in offsets:raise BudgetError('Vínculo de agenda PZH inválido o repetido')
        dates.add(serial);offsets.add(offset);_,identifier,date,fields=record;rows.append(dict(date=date,holiday=bool(fields['2']) if '2' in fields else None,note=fields.get('3',''),source_id=identifier,source_fields=fields))
    return rows


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>10000:raise BudgetError('Agenda fuera de límites')
        dates=set()
        for row in data:
            if not isinstance(row,dict) or set(row)!={'date','holiday','note','source_id','source_fields'}:raise BudgetError('Columnas de agenda inválidas')
            iso(row['date'])
            if row['date'] in dates:raise BudgetError('Fecha de agenda repetida')
            dates.add(row['date'])
            if row['holiday'] is not None and type(row['holiday']) is not bool:raise BudgetError('Indicación de festivo inválida')
            if not isinstance(row['note'],str) or len(row['note'])>100000:raise BudgetError('Nota de agenda inválida')
            if row['source_id'] is not None and (type(row['source_id']) is not int or row['source_id']<0):raise BudgetError('Registro de agenda inválido')
            fields=row['source_fields']
            if not isinstance(fields,dict) or set(fields)-{str(n) for n in range(1,22)}:raise BudgetError('Propiedades de agenda desconocidas')
            for key,value in fields.items():
                if key=='3':
                    if not isinstance(value,str):raise BudgetError('Nota de origen inválida')
                elif key in ('1','2'):
                    if type(value) is not int or not 0<=value<=(65535 if key=='1' else 1):raise BudgetError('Indicador de agenda inválido')
                else:
                    if not isinstance(value,str) or len(value)>200:raise BudgetError('Importe de agenda inválido')
                    number=Decimal(value)
                    if not number.is_finite() or abs(number)>Decimal('1e15'):raise BudgetError('Importe de agenda fuera de límites')
        return data
    except (ValueError,TypeError,ArithmeticError) as exc:raise BudgetError('Agenda inválida') from exc


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def copy_source(budget):
    data=validate(budget);dates={r['date']:r for r in data}
    for row in source_rows(budget):
        if row['date'] not in dates:data.append(row);dates[row['date']]=row
        elif dates[row['date']]['source_id'] is None:dates[row['date']].update(source_id=row['source_id'],source_fields=row['source_fields'])
    if data:_save(budget,data)
    budget.project_metadata.pop('pzh_agenda_pending',None)


def set_day(budget,date,holiday,note):
    data=validate(budget);old=next((r for r in data if r['date']==date),None)
    row=dict(date=date,holiday=holiday,note=note,source_id=old['source_id'] if old else None,source_fields=old['source_fields'] if old else {})
    _save(budget,[row if r['date']==date else r for r in data] if old else data+[row])


def add_holidays_to_plan(budget):
    previous=dict(budget.project_metadata)
    try:
        data=planning.validate(budget);holidays=set(data['holidays'])|{r['date'] for r in validate(budget) if r['holiday'] is True}
        planning.configure_calendar(budget,data['weekdays'],sorted(holidays))
    except Exception:
        budget.project_metadata.clear();budget.project_metadata.update(previous);raise


def report_rows(budget):return [(r['date'],'' if r['holiday'] is None else 'Sí' if r['holiday'] else 'No',r['note'],r['source_id'] if r['source_id'] is not None else '') for r in sorted(validate(budget),key=lambda r:r['date'])]


def source_total_rows(budget):return [(r['date'],label,r['source_fields'][str(tag)]) for r in validate(budget) for tag,label in TOTALS.items() if str(tag) in r['source_fields']]

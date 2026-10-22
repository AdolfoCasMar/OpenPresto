"""Native party directory, independent from invoices, cash and stock."""
import json
from uuid import uuid4
from .budget import BudgetError
from decimal import Decimal,InvalidOperation
from .planning import iso

KEY='entities_v1'
TEXT_FIELDS=('code','name','contact','address','city','postal_code','province','phone','phone_alt','fax','email','tax_id','note','title','college','registration')
SOURCE_FIELDS={3:'name',4:'contact',5:'address',6:'city',7:'postal_code',8:'province',9:'phone',10:'phone_alt',11:'fax',12:'email',13:'tax_id',14:'note',37:'title',38:'college',39:'registration'}
PROPERTY_FIELDS=('quantity','gross_area','path','active','date')
SOURCE_TOTALS={15:'Pagado',16:'Pago previsto de proformas',17:'Pendiente de pago',18:'Pedidos',19:'Contratos',20:'Entregas',21:'Entregas proforma',22:'Facturas recibidas',23:'Facturas proforma',24:'Retención de garantía',25:'Retención fiscal',26:'Impuesto acumulado',28:'Facturas a clientes',31:'Presupuesto de obra',32:'Certificación de obra',33:'Real de obra',34:'Objetivo de obra',35:'Plan de obra'}


def _properties(values):
    if not isinstance(values,dict) or set(values)!=set(PROPERTY_FIELDS):raise BudgetError('Propiedades adicionales de entidad inválidas')
    for key in ('quantity','gross_area'):
        value=values[key]
        if value is None:continue
        if not isinstance(value,str) or len(value)>200:raise BudgetError('La cantidad o superficie debe ser texto decimal')
        try:number=Decimal(value)
        except InvalidOperation as exc:raise BudgetError('Cantidad o superficie inválida') from exc
        if not number.is_finite() or abs(number)>Decimal('1e15') or number.as_tuple().exponent < -100 or (key=='gross_area' and number<0):raise BudgetError('Cantidad o superficie fuera de límites')
    if values['path'] is not None and (not isinstance(values['path'],str) or len(values['path'])>100000):raise BudgetError('Ruta de entidad inválida')
    if values['active'] is not None and type(values['active']) is not bool:raise BudgetError('Estado activo de entidad inválido')
    if values['date'] is not None:iso(values['date'])
    return values


def _source_properties(fields):
    from .pzh_operations import day
    values=dict.fromkeys(PROPERTY_FIELDS)
    for tag,key in ((27,'gross_area'),(29,'path'),(40,'quantity')):
        if str(tag) in fields:values[key]=fields[str(tag)]
    if '30' in fields:
        if type(fields['30']) is not int or fields['30'] not in (0,1):raise BudgetError('Estado activo PZH fuera del perfil comprobado')
        values['active']=bool(fields['30'])
    if '36' in fields:values['date']=day(fields['36'])
    return _properties(values)


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'[]')) if data is None else data
        if not isinstance(data,list) or len(data)>10000:raise ValueError('lista')
        ids=set()
        for row in data:
            columns=set(TEXT_FIELDS)|{'id','role','source_id','source_fields'}
            if not isinstance(row,dict) or set(row) not in (columns,columns|{'properties'}):raise ValueError('columnas')
            if any(not isinstance(row[k],str) or len(row[k])>100000 for k in TEXT_FIELDS):raise ValueError('texto')
            if not row['code'].strip() or not isinstance(row['id'],str) or not row['id'] or row['id'] in ids:raise ValueError('identidad')
            ids.add(row['id'])
            if type(row['role']) is not int or not 0<=row['role']<=255:raise ValueError('tipo')
            if row['source_id'] is not None and (type(row['source_id']) is not int or row['source_id']<0):raise ValueError('origen')
            fields=row['source_fields']
            if not isinstance(fields,dict) or len(fields)>256 or any(not isinstance(k,str) or not k.isdecimal() or type(v) not in (str,int) for k,v in fields.items()):raise ValueError('propiedades de origen')
            if 'properties' in row:_properties(row['properties'])
        return data
    except (TypeError,ValueError) as exc:raise BudgetError('Directorio de entidades inválido: '+str(exc)) from exc


def _save(budget,data):
    validate(budget,data)
    budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def set_entity(budget,values,entity_id=None):
    if not isinstance(values,dict) or set(values)-set(TEXT_FIELDS)-{'role','properties'}:raise BudgetError('Propiedades de entidad no editables')
    data=validate(budget)
    if entity_id is not None and (not isinstance(entity_id,str) or not entity_id):raise BudgetError('Identificador de entidad inválido')
    old=next((r for r in data if r['id']==entity_id),None)
    if entity_id is not None and old is None:raise BudgetError('Entidad inexistente')
    row=dict(old) if old else dict(dict.fromkeys(TEXT_FIELDS,''),id=uuid4().hex,role=0,source_id=None,source_fields={})
    row.update(values)
    _save(budget,[row if r['id']==row['id'] else r for r in data] if old else data+[row])


def copy_pzh(budget):
    from .pzh_operations import validate as source_state
    from .pzh_archive import pzh_archive_inventory,pzh_source_bytes
    inventory=pzh_archive_inventory(budget)
    if inventory is None or pzh_source_bytes(budget) is None:raise BudgetError('Falta el PZH original conservado')
    source=source_state(budget);data=validate(budget);existing={r['id']:r for r in data}
    prefix='pzh:'+inventory['sha256']+':entity:'
    for source_row in source.get('entities',[]):
        rid=prefix+str(source_row['id'])
        fields=source_row['fields']
        properties=_source_properties(fields)
        if rid in existing:
            if 'properties' not in existing[rid] and any(v is not None for v in properties.values()):existing[rid]['properties']=properties
            continue
        row=dict(dict.fromkeys(TEXT_FIELDS,''),id=rid,role=fields.get('2',0),source_id=source_row['id'],source_fields=dict(fields))
        row['code']=source_row['code']
        for tag,name in SOURCE_FIELDS.items():row[name]=fields.get(str(tag),'')
        if any(v is not None for v in properties.values()):row['properties']=properties
        data.append(row);existing[rid]=row
    _save(budget,data)


def report_rows(budget):
    return [(r['id'],r['code'],r['name'],r['role'],r['contact'],r['phone'],r['email'],r['tax_id'],r['address'],r['city'],r['postal_code'],r['province'],r['phone_alt'],r['fax'],r['title'],r['college'],r['registration'],r['note']) for r in validate(budget)]


def property_rows(budget):
    rows=[]
    for row in validate(budget):
        values=row.get('properties',dict.fromkeys(PROPERTY_FIELDS))
        rows.append((row['code'],row['name'],values['quantity'] if values['quantity'] is not None else '',values['gross_area'] if values['gross_area'] is not None else '',values['path'] if values['path'] is not None else '', '' if values['active'] is None else 'Sí' if values['active'] else 'No',values['date'] or ''))
    return rows


def source_total_rows(budget):
    return [(row['code'],row['name'],f'0x{tag:02x}',label,row['source_fields'][str(tag)]) for row in validate(budget) for tag,label in SOURCE_TOTALS.items() if str(tag) in row['source_fields']]


def find(budget,text='',role=None):
    if not isinstance(text,str) or (role is not None and (type(role) is not int or not 0<=role<=255)):
        raise BudgetError('Filtro de entidades inválido')
    query=text.strip().casefold()
    return [r for r in validate(budget) if (role is None or r['role']==role) and (not query or any(query in r[k].casefold() for k in TEXT_FIELDS))]

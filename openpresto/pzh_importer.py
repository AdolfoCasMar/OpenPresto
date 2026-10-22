"""Read-only, bounded reader for the observed compact PZH 8.x layout.

Independent implementation from synthetic data files. Unknown fields, layouts,
or economic discrepancies fail explicitly; no Presto executable is loaded.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from pathlib import Path
import re
import struct

from .budget import Budget, BudgetConcept, BudgetRelation, BudgetMeasurement, BudgetError, special_price_kind
from .calculations import calculator_for


class PZHImportError(BudgetError):
    """Unsupported, inconsistent, or truncated PZH file."""


class PZHCompressedTextError(PZHImportError):
    """A partial import needs the user's explicit choice in the UI."""


@dataclass(frozen=True)
class PZHImportResult:
    budget: Budget
    warnings: tuple[str, ...]


MAX_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 100000
HEADER_BYTES = 0x9C2
CONCEPT_FIELDS = {1: 'H', 2: 'B', 3: 's', 4: 's', 5: 's', 6: 's', 7: 's',
                  8: 'H', **{i: 'd' for i in range(9, 14)},
                  **{i: 'B' for i in range(14, 19)},
                  0x18: 'd', 0x19: 'd', 0x1A: 'd', 0x1B: 'd', 0x1C: 'd', 0x1E: 'd',
                  **{i: 'd' for i in (0x20, 0x21, 0x22, 0x23, 0x24, 0x25,
                                     0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2D, 0x2E)},
                  **{i: 'd' for i in range(0x34, 0x3A)}, 0x3A: 'B',
                  0x42: 'd', 0x43: 'B', 0x44: 'd', 0x47: 's', 0x5D: 's', 0x5E: 's',
                  **{i: 'd' for i in range(0x57, 0x5D)}}
RELATION_FIELDS = {1: 'H', **{i: 'H' for i in range(2, 6)}, 6: 'B', 7: 'B',
                   **{i: 'd' for i in range(0x0D, 0x13)}, 0x15: 'B',
                   0x18: 'B', 0x19: 'B', 0x1D: 'H', 0x1E: 'B', 0x1F: 's', 0x20: 'H'}
MEASUREMENT_FIELDS = {1: 'B', 2: 'B', 3: 's', 4: 's', 5: 's', 7: 's', 8: 's', 9: 's',
                      **{i: 'd' for i in range(0x0C, 0x11)}}


def _unpack(data, offset, fmt):
    size = struct.calcsize('<' + fmt)
    if offset < 0 or offset + size > len(data):
        raise PZHImportError(f'PZH truncado en 0x{offset:x}.')
    return struct.unpack_from('<' + fmt, data, offset)


def _text(data):
    try:
        return data.decode('cp1252')
    except UnicodeDecodeError as exc:
        raise PZHImportError('Codificación PZH no admitida; se esperaba Windows-1252.') from exc


def _code(data):
    value = _text(data).rstrip(' ')
    if not value or any(ord(c) < 32 for c in value):
        raise PZHImportError('Clave de concepto PZH no válida.')
    return value


def _relation_key(parent,child,suffix=b'  '):
    if suffix not in (b'  ',b' 0'):
        raise PZHImportError('Índice de aparición de relación PZH no admitido: '+suffix.hex())
    return (parent,child) if suffix==b'  ' else (parent,child,suffix.hex())


def _fields(data, schema, context):
    fields = {}
    pos = 0
    previous = 0
    while pos < len(data):
        tag = data[pos]
        pos += 1
        if tag <= previous or tag not in schema:
            raise PZHImportError(f'{context}: campo PZH 0x{tag:02x} aún no admitido; no se omite.')
        previous = tag
        fmt = schema[tag]
        if fmt == 'raw8':
            _unpack(data,pos,'Q')  # Bounds check; keep uninterpreted bytes, never money.
            fields[tag]=data[pos:pos+8].hex()
            pos+=8
        elif fmt == 's':
            end = data.find(b'\0', pos)
            if end < 0:
                raise PZHImportError(f'{context}: cadena PZH incompleta.')
            fields[tag] = _text(data[pos:end])
            pos = end + 1
        else:
            value, = _unpack(data, pos, fmt)
            pos += struct.calcsize('<' + fmt)
            if fmt == 'd':
                value = Decimal(str(value))
                if not value.is_finite() or abs(value) > Decimal('1e15'):
                    raise PZHImportError(f'{context}: número PZH fuera del límite admitido.')
            fields[tag] = value
    return fields


def _header_parts(data):
    """Decode the bounded header variant, retaining original record/source bytes.

    The observed five-byte cycle is recoverable from a fixed reserved header
    area. Header, length word and configuration each start their own cycle.
    Full table/configuration validation remains the reader's responsibility.
    """
    encoded = _unpack(data,20,'I')[0] == 1
    header = data[:HEADER_BYTES+4]
    key = None
    if encoded:
        key = data[64:69]
        reserved = data[64:112]
        if len(key)!=5 or any(c<48 or c>57 for c in key) or any(c!=key[i%5] for i,c in enumerate(reserved)):
            raise PZHImportError('Variante de cabecera PZH no reconocida; no se modifica el archivo.')
        def decode(block):
            return bytes((value-key[i%5])%256 for i,value in enumerate(block))
        header = data[:24]+decode(data[24:HEADER_BYTES])+decode(data[HEADER_BYTES:HEADER_BYTES+4])
    boundary = HEADER_BYTES+4+_unpack(header,HEADER_BYTES,'I')[0]
    if not HEADER_BYTES+4<=boundary<=len(data):
        raise PZHImportError('Cabecera de obra PZH fuera del archivo.')
    config = data[HEADER_BYTES+4:boundary]
    if key is not None:config=decode(config)
    return header, config, boundary, encoded


class _Reader:
    def __init__(self, data):
        self.data = data
        if len(data) < HEADER_BYTES + 4 or len(data) > MAX_BYTES:
            raise PZHImportError('Tamaño PZH no admitido (máximo 64 MiB).')
        if data[:4] != b'\0' * 4:
            raise PZHImportError('Cabecera PZH distinta del perfil compacto admitido.')
        self.tables = []
        header,self.config,boundary,self.encoded_header = _header_parts(data)
        previous_index = boundary
        for table in range(24):
            count, start, index = _unpack(header, 0x22 + table * 88, 'III')
            if count > MAX_RECORDS or not previous_index <= start <= index <= len(data):
                raise PZHImportError(f'Tabla PZH {table} fuera de límites.')
            if not count and start != index:
                raise PZHImportError(f'Tabla PZH {table} vacía con contenido inesperado.')
            self.tables.append((count, start, index))
            previous_index = index
        if self.tables[0][1] != boundary:
            raise PZHImportError('Distribución PZH no admitida.')
        # This observed prefix identifies the configuration layout, not a file suffix.
        if not self.config.startswith(b'\x018.0\0\x02') or len(self.config) < 9 or self.config[7] != 3:
            raise PZHImportError('Versión interna PZH distinta del perfil 8.x admitido.')
        end = self.config.find(b'\0', 8)
        if end < 0:
            raise PZHImportError('Falta el concepto raíz de la obra PZH.')
        self.root = _code(self.config[8:end])
        configuration_at=end+1
        self.configuration_options={}
        if self.config[configuration_at:configuration_at+1]==b'\x04':
            value,=_unpack(self.config,configuration_at+1,'B')
            self.configuration_options['04']=value;configuration_at+=2
        self.root_quantity_decimals=0
        if self.config[configuration_at:configuration_at+1]==b'\x06':
            self.root_quantity_decimals,=_unpack(self.config,configuration_at+1,'H')
            if self.root_quantity_decimals>12:raise PZHImportError('Precisión raíz PZH fuera de límites.')
            configuration_at+=3
        precisions={}
        for tag in range(7,13):
            if self.config[configuration_at:configuration_at+1]!=bytes([tag]):
                raise PZHImportError('Configuración de precisión PZH no reconocida.')
            value,=_unpack(self.config,configuration_at+1,'H')
            if value>12:raise PZHImportError('Precisión PZH fuera de límites.')
            precisions[tag]=value;configuration_at+=3
        if any(precisions[tag]!=2 for tag in (7,9,11,12)):
            raise PZHImportError('Perfil de precisiones monetarias o de medición PZH pendiente de contraste.')
        self.quantity_decimals=precisions[8];self.price_decimals=precisions[10]
        self.indirect_rate=Decimal('0')
        if self.config[configuration_at:configuration_at+1]==b'\x10':
            rate,=_unpack(self.config,configuration_at+1,'d')
            self.indirect_rate=Decimal(str(rate))
            if not self.indirect_rate.is_finite() or not 0<=self.indirect_rate<=Decimal('1e6'):
                raise PZHImportError('Porcentaje de indirectos PZH fuera de límites.')
        phase_pattern = b''.join(bytes([tag]) + b'(.)' for tag in range(0xEF, 0xF8))
        phase_matches = list(re.finditer(phase_pattern, self.config, re.DOTALL))
        self.reference_only=(self.encoded_header and self.tables[0][0]==1
                             and all(not count for i,(count,_,_) in enumerate(self.tables) if i not in (0,10,23)))
        if self.reference_only and not phase_matches:
            # This bounded library profile has no economic relationships or
            # measurement/certification tables. No approval phase is invented.
            self.approved_phase=None;self.certification_phase=None;self.exclude_undecomposed=False
            return
        if len(phase_matches) != 1:
            raise PZHImportError('No se puede identificar la fase presupuestaria aprobada del PZH.')
        self.approved_phase = phase_matches[0].group(5)[0]
        self.certification_phase = phase_matches[0].group(6)[0]
        footer_at=phase_matches[0].end()
        self.exclude_undecomposed=self.config[footer_at:footer_at+2]==b'\xf9\x01'
        if not 1 <= self.approved_phase <= 99:
            raise PZHImportError('Fase presupuestaria aprobada PZH fuera del perfil admitido.')

    def records(self, table, overhead):
        count, pos, end = self.tables[table]
        ids = set()
        for _ in range(count):
            if pos+max(8,overhead)>end:
                raise PZHImportError(f'Cabecera de registro incompleta en tabla PZH {table}.')
            size, identifier = _unpack(self.data, pos, 'II')
            stop = pos + size + overhead
            if size == 0 or stop > end or stop <= pos + overhead or identifier in ids:
                raise PZHImportError(f'Registro inválido en tabla PZH {table}.')
            ids.add(identifier)
            yield pos, identifier, self.data[pos + overhead:stop]
            pos = stop
        if pos != end:
            raise PZHImportError(f'Longitud inconsistente de tabla PZH {table}.')


def import_pzh(path, *, skip_compressed_text=False, modules=None, progress=None, native_modules=False) -> PZHImportResult:
    """Import the supported budget subset, without modifying the source file."""
    try:
        with Path(path).open('rb') as source:
            data = source.read(MAX_BYTES + 1)
        return _import(data, Path(path).name, skip_compressed_text=skip_compressed_text, modules=modules, progress=progress, native_modules=native_modules)
    except (OSError, struct.error, UnicodeError) as exc:
        raise PZHImportError(f'No se puede leer el archivo PZH: {exc}') from exc
    except (ArithmeticError, RecursionError) as exc:
        raise PZHImportError(f'Medición o cálculo PZH no admitido: {exc}') from exc


def _import(data, filename, *, skip_compressed_text=False, modules=None, progress=None, native_modules=False):
    selected = frozenset(('certifications', 'planning', 'management') if modules is None else modules)
    if selected - {'certifications', 'planning', 'management'}:
        raise PZHImportError('Selección de módulos PZH no válida.')
    def notify(value, label):
        if progress is not None: progress(value, label)
    notify(5, 'Leyendo estructura y presupuesto')
    reader = _Reader(data)
    budget = Budget()
    if reader.reference_only:budget.project_metadata['pzh_reference_only']='1'
    budget.root_quantity_decimals = reader.root_quantity_decimals
    if (reader.quantity_decimals,reader.price_decimals)!=(3,2):
        budget.project_metadata.update(engine='native-v1',quantity_decimals=str(reader.quantity_decimals),price_decimals=str(reader.price_decimals))
    if reader.configuration_options:
        import json
        budget.project_metadata['pzh_configuration_options']=json.dumps(reader.configuration_options)
    budget.bc3_zero_dimensions_as_blank = True
    stored_prices = {}
    source_concepts = {}
    for _, _, record in reader.records(0, 8):
        if len(record) < 13:
            raise PZHImportError('Concepto PZH incompleto.')
        code = _code(record[:13])
        fields = _fields(record[13:], CONCEPT_FIELDS, code)
        source_concepts[code] = fields
        extra={str(k):str(fields[k]) for k in (0x18,0x19,0x1b,0x1c,0x44,0x5c,0x5e) if k in fields}
        if extra:
            import json
            budget.project_metadata['pzh_concept_extra:' + code]=json.dumps(extra)
        if 3 in fields:
            budget.project_metadata['pzh_concept_field3:' + code] = fields[3]
        nature = {4: 'capitulo', 5: 'partida', 6: 'mano de obra',
                  7: 'maquinaria', 8: 'material'}.get(fields.get(2), '')
        price = fields.get(9, Decimal('0'))
        stored_prices[code] = price
        budget.add_concept(BudgetConcept(code, fields.get(5, ''), fields.get(6, ''), nature, price))
        if code == reader.root:
            budget.project_metadata['currency'] = fields.get(7, 'EUR')
    budget.set_root(reader.root)
    positions = {}
    pairs = {}
    rows = []
    source_relations = {}
    record_keys = {}
    unresolved = []
    excluded = []
    for offset, identifier, record in reader.records(1, 16):
        if len(record) < 28:
            raise PZHImportError('Clave de relación PZH no admitida.')
        parent, child = _code(record[:13]), _code(record[13:26])
        fields = _fields(record[28:], RELATION_FIELDS, f'{parent}/{child}')
        key=_relation_key(parent,child,record[26:28]);record_keys[identifier]=key
        source_relations[key] = fields
        if 7 in fields:
            budget.project_metadata['pzh_relation_field7:' + parent + '/' + child]=str(fields[7])
        if fields.get(0x18, 0) not in (0, 1):
            raise PZHImportError('Marca de exclusión presupuestaria PZH desconocida.')
        if fields.get(0x18) == 1:
            excluded.append(key)
            continue
        order, = _unpack(data, offset + 8, 'I')
        rows.append((order, identifier, parent, child, fields))
    percentage_codes={code for code in source_concepts if '%' in code}
    if reader.indirect_rate:
        budget.indirect_config={'profile':'native-v1','chapter_codes':[code for code,fields in source_concepts.items() if fields.get(2)==4],
                                'rate':str(reader.indirect_rate),'exclude_undecomposed':reader.exclude_undecomposed}
        budget.project_metadata['engine']='native-v1'
    if percentage_codes:
        budget.project_metadata['engine']='native-v1'
        budget.project_metadata['pzh_percentage_profile']='8x-prefix-observed-v1'
        for code in percentage_codes:
            if special_price_kind(code)!='porcentaje' or code.count('%')!=1:
                raise PZHImportError(f'Código porcentual PZH no admitido: {code}.')
    # Percentage bases depend on the serialized decomposition sequence.
    # The header index rank is a different order (e.g. it places M% before M01).
    # Both the resulting bases and every stored composed price are checked below.
    for _, identifier, parent, child, fields in (rows if percentage_codes else sorted(rows)):
        key=record_keys[identifier]
        if parent not in source_concepts or child not in source_concepts:
            unresolved.append({'id':identifier,'parent':parent,'child':child,'fields':{str(k):str(v) for k,v in fields.items()}})
            continue
        if key in pairs:
            raise PZHImportError('La misma relación PZH aparece más de una vez.')
        positions[parent] = positions.get(parent, 0) + 1
        quantity=fields.get(14, Decimal('0'))
        if child not in percentage_codes and source_concepts[parent].get(2)==4 and source_concepts[child].get(2)!=4:
            quantity=quantity.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        if child in percentage_codes:
            # PZH stores the displayed base / 100 here, unlike a BC3 rate.
            # The concept's budget price is the percentage rate.
            quantity=stored_prices[child]/100
            if fields.get(13,Decimal('1'))!=1:
                raise PZHImportError(f'Factor porcentual PZH no admitido en {parent}/{child}.')
        relation = BudgetRelation(parent, child, quantity,
                                  positions[parent], f'pzh-r{identifier}', fields.get(13, Decimal('1')))
        budget.add_relation(relation)
        pairs[key] = relation
        if 0x1E in fields:
            if fields[0x1E] not in (0,1):raise PZHImportError('Tipo de duración PZH fuera de límites')
            budget.project_metadata['pzh_duration_locked:'+relation.id]=str(fields[0x1E])
        if len(key)==3:budget.project_metadata['pzh_relation_occurrence:' + relation.id]=key[2]
    # Long text: plain, uncompressed records and their explicit concept index.
    notify(20, 'Recuperando textos')
    texts = {}
    compressed = set()
    rich_texts = {}
    decoded_compressed = 0
    for offset, _, record in reader.records(2, 0):
        # With overhead=0, the returned record includes its length and ID.
        if len(record) < 17 or record[8] not in (1, 2):
            raise PZHImportError('Compresión del texto PZH aún no admitida.')
        unpacked, packed = _unpack(record, 9, 'II')
        # Some 8.x works mark LZHUF with flag 1 as well as flag 2.
        # Lengths and the size-prefixed stream must still validate exactly.
        if record[8] == 2 or unpacked != packed:
            if packed != len(record) - 17 or unpacked > MAX_BYTES:
                raise PZHImportError('Texto comprimido PZH fuera de límites.')
            from .pzh_text import decompress_pzh_text, PZHTextError
            try:
                raw_text = decompress_pzh_text(record[17:], unpacked)
                decoded_compressed += 1
            except PZHTextError as exc:
                if not skip_compressed_text:
                    raise PZHCompressedTextError(str(exc)) from exc
                compressed.add(offset)
                texts[offset] = '[Texto PZH comprimido no convertido. Consulta el archivo original.]'
                continue
        else:
            if unpacked != packed or packed != len(record) - 17:
                raise PZHImportError('Longitud de texto PZH inconsistente.')
            raw_text = record[17:]
        if raw_text.startswith(b'{\\rtf'):
            from .pzh_text import rtf_plain_text
            texts[offset] = rtf_plain_text(raw_text)
            rich_texts[offset] = raw_text
        else:
            texts[offset] = _text(raw_text)
    count, _, index = reader.tables[2]
    from dataclasses import replace
    text_codes = set()
    text_offsets = set()
    for i in range(count):
        at = index + i * 17
        if at + 17 > reader.tables[3][1]:
            raise PZHImportError('Índice de textos PZH incompleto.')
        code = _code(data[at:at + 13])
        offset, = _unpack(data, at + 13, 'I')
        if code not in budget.concepts or offset not in texts or code in text_codes or offset in text_offsets:
            raise PZHImportError('Índice de textos PZH no válido.')
        text_codes.add(code)
        text_offsets.add(offset)
        budget.concepts[code] = replace(budget.concepts[code], text=texts[offset])
        if offset in rich_texts:
            import base64
            budget.project_metadata['pzh_rtf_source:' + code] = base64.b64encode(rich_texts[offset]).decode('ascii')
    measurements = {}
    unresolved_measurements=[]
    notify(30, 'Recuperando mediciones')
    phases = set()
    unapproved = 0
    for offset, identifier, record in reader.records(4, 12):
        if len(record) < 30 or record[0] not in (0, 1) or record[29] == 0:
            raise PZHImportError('Medición PZH con clave o fase no admitida.')
        phases.add(record[29])
        if record[29] > reader.approved_phase:
            unapproved += 1
            continue
        pair = _relation_key(_code(record[1:14]), _code(record[14:27]),record[27:29])
        if pair in excluded:
            continue
        if pair not in pairs:
            if any((row['parent'],row['child'])==pair[:2] for row in unresolved):
                unresolved_measurements.append({'id':identifier,'relation':list(pair),'phase':record[29],'record_hex':record.hex()})
                continue
            raise PZHImportError('Medición PZH sin relación presupuestaria.')
        fields = _fields(record[30:], MEASUREMENT_FIELDS, 'Medición PZH')
        flags = fields.get(1, 0)
        if flags not in (0, 1, 2):
            raise PZHImportError('Anulaciones o tipo de medición PZH aún no admitidos.')
        formula = fields.get(5, '')
        kind = {0: '', 1: '2', 2: '1'}[flags]
        if formula:
            if flags:
                raise PZHImportError('Fórmula y subtotal PZH combinados no admitidos.')
            kind = '3'
        dimensions = [fields.get(i) for i in range(12, 16)]
        n_lines = dimensions[0]
        if n_lines is None:
            n_lines = Decimal('1') if formula or any(v is not None for v in dimensions) else Decimal('0')
        line = BudgetMeasurement(pairs[pair].id, fields.get(4, ''), n_lines,
                                 *(v if v else None for v in dimensions[1:]),
                                 id=f'pzh-m{identifier}', formula=formula)
        sequence, = _unpack(data, offset + 8, 'I')
        if kind in ('1','2') and any(v is not None for v in dimensions):
            # A source subtotal may include its own dimensional contribution.
            # Native subtotal rows aggregate previous lines, so retain the
            # contribution first and then an explicit zero-contribution marker.
            budget.project_metadata['pzh_phase:' + line.id] = str(record[29])
            measurements.setdefault(pair, []).append((sequence, identifier, line))
            line = replace(line,id=line.id+'-subtotal',comment='',n_lines=Decimal(0),length=None,width=None,height=None)
            budget.project_metadata['pzh_subtotal_source:' + line.id] = str(identifier)
        if kind in ('1', '2'):
            budget.project_metadata['measurement_kind:' + line.id] = kind
        budget.project_metadata['pzh_phase:' + line.id] = str(record[29])
        measurements.setdefault(pair, []).append((sequence, identifier, line))
    for pair, lines in measurements.items():
        relation = pairs[pair]
        budget.concepts[relation.child_code] = replace(budget.concepts[relation.child_code], measurement_decimals=2)
        for _, _, line in sorted(lines,key=lambda row:row[:2]):
            budget.add_measurement(line)
        calculated = budget.relation_quantity(relation.id)
        if calculated != relation.quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):
            raise PZHImportError(f'Mediciones PZH de {pair[0]}/{pair[1]}: cantidad calculada {calculated}, guardada {relation.quantity}; importación detenida.')
    locked={code:stored_prices[code] for code,fields in source_concepts.items() if fields.get(14)==1 and any(r.parent_code==code for r in budget.relations)}
    if locked:
        budget.locked_prices.update(locked)
        budget.project_metadata['engine']='native-v1'
    notify(40, 'Comprobando cantidades y precios del presupuesto')
    from .calculations import calculation_batch
    composed = {r.parent_code for r in budget.relations}
    used = {r.child_code for r in budget.relations}
    # An absent price cache is not an explicitly stored zero. Only independent
    # catalogue roots may omit it; no such exception applies to valued items.
    uncached = {code for code in composed if 9 not in source_concepts[code]
                and code not in used and code != budget.root_code}
    def check_prices():
        calculator = calculator_for(budget)
        mismatches = []
        base_errors = []
        with calculation_batch(calculator):
            for pair,relation in pairs.items():
                if pair[1] not in percentage_codes or 14 not in source_relations[pair]:continue
                calculated=calculator.relation(relation.id).quantity
                saved=calculator.policy.quantity(source_relations[pair].get(14,Decimal('0')))
                if calculated!=saved:
                    base_errors.append(f'Base porcentual distinta en {pair[0]}/{pair[1]}: calculada {calculated}, guardada {saved}. No se modifica el PZH.')
            for code in sorted(composed):
                value = calculator.price(code)
                if code not in uncached and value != calculator.policy.price(stored_prices[code]):
                    mismatches.append(code)
        return mismatches, base_errors
    mismatches, base_errors = check_prices()
    if (mismatches or base_errors) and percentage_codes:
        # A distinct, versioned native policy is accepted only if every saved
        # price and percentage base agrees. Existing matching imports keep their
        # previous policy. No per-item rate, lock or balancing amount is guessed.
        budget.project_metadata['percentage_base_mode']='exact-amount-v1'
        alternate, alternate_bases = check_prices()
        if alternate or alternate_bases:
            budget.project_metadata.pop('percentage_base_mode')
        else:
            mismatches, base_errors = [], []
    if base_errors:
        raise PZHImportError(base_errors[0])
    if mismatches:
        raise PZHImportError(f'El precio calculado de {mismatches[0]} difiere del guardado en PZH. Puede contener indirectos, bloqueos o reglas aún no admitidas.')
    warnings = ['PZH: importación experimental del presupuesto; no acredita compatibilidad completa con Presto.',
                'Se conserva el PZH original. Guarda el resultado como un proyecto OpenPresto nuevo.']
    if uncached:
        import json
        budget.project_metadata['pzh_uncached_catalog_prices']=json.dumps(sorted(uncached))
        warnings.append(f'{len(uncached)} descomposiciones independientes del catálogo sin precio guardado: se calcula su precio nativo; no se han interpretado como precios cero ni bloqueos.')
    if budget.project_metadata.get('percentage_base_mode')=='exact-amount-v1':
        warnings.append('Importes porcentuales calculados sobre la base completa; todos los precios guardados y bases visibles coinciden. Se conserva esta política al editar y guardar.')
    if reader.reference_only:
        warnings[0]='PZH de referencia documental, sin relaciones económicas; no se identifica como presupuesto de obra completo.'
        warnings.append('Se recuperan el concepto raíz y las entidades reconocidas. Los contenidos de referencia de otras tablas siguen conservados en el original, sin conversión semántica completa.')
    if reader.encoded_header:
        warnings.append('Variante de cabecera PZH normalizada solo en memoria; se conservan exactamente los bytes originales.')
    if unresolved:
        import json
        budget.project_metadata['pzh_unresolved_relations']=json.dumps(unresolved,ensure_ascii=False)
        if unresolved_measurements:budget.project_metadata['pzh_unresolved_measurements']=json.dumps(unresolved_measurements,ensure_ascii=False)
        warnings.append(f'IMPORTACIÓN CON REFERENCIAS SIN RESOLVER: {len(unresolved)} relaciones apuntan a códigos ausentes del catálogo. Se conservan en metadatos y en el original; no se inventan conceptos ni se incluyen esas relaciones en el total calculado.')
    if 9 not in source_concepts[reader.root]:
        warnings.append('El PZH no almacena precio de presupuesto para la raíz; el total mostrado se calcula con la estructura recuperable, no acredita un importe original guardado.')
    if reader.indirect_rate:
        warnings.append(f'Costes indirectos PZH importados: {reader.indirect_rate} %, contrastados con todos los precios compuestos guardados.')
    if any(3 in fields for fields in source_concepts.values()):
        warnings.append('Campo de concepto 0x03 conservado como texto en metadatos; no se usa para cambiar códigos ni precios.')
    if percentage_codes:
        warnings.append('Porcentajes PZH convertidos al motor nativo: tipos del concepto y bases de relaciones contrastados con los importes guardados; prefijos y orden conservados.')
    from .storage import dumps, loads, _validate_extensions
    from copy import deepcopy
    for module, label in (('certifications', 'Certificaciones'), ('planning', 'Planificación'), ('management', 'Gestión')):
        if module not in selected:
            warnings.append(label + ': no seleccionado; datos originales conservados en la instantánea PZH.')
            continue
        notify({'certifications':55, 'planning':65, 'management':75}[module], 'Importando ' + label.lower())
        candidate = deepcopy(budget)
        try:
            if module == 'certifications':
                from .pzh_certifications import import_certifications
                notes = import_certifications(candidate, reader, source_concepts, source_relations, pairs)
            else:
                from .pzh_operations import import_operations
                notes = import_operations(candidate, reader, source_concepts, source_relations, pairs,
                                          modules={module}, merge=True)
            _validate_extensions(candidate)
        except (BudgetError, ArithmeticError, RecursionError, ValueError) as exc:
            warnings.append('IMPORTACIÓN PARCIAL — ' + label + ' no convertido: ' + str(exc))
        else:
            budget = candidate
            warnings.extend(notes)
    if excluded:
        warnings.append(f'{len(excluded)} relaciones marcadas fuera del presupuesto PZH se han excluido del cálculo; los conceptos se conservan en el catálogo.')
        import json
        budget.project_metadata['pzh_excluded_relations'] = json.dumps(excluded, ensure_ascii=False)
    if compressed:
        warnings.append(f'IMPORTACIÓN PARCIAL: {len(compressed)} textos comprimidos no convertidos; se muestran marcadores, no el texto original.')
    if decoded_compressed:
        warnings.append(f'Textos comprimidos recuperados mediante LZHUF: {decoded_compressed}.')
    if rich_texts:
        warnings.append('Textos RTF convertidos a texto editable. El RTF fuente se conserva en metadatos; editar el texto no modifica el formato original archivado.')
    if phases - {1}:
        warnings.append('Fases de medición presupuestaria consolidadas en la cantidad actual; no se conservan sus estados de aprobación.')
    if unapproved:
        warnings.append(f'{unapproved} líneas de fases posteriores a la fase presupuestaria aprobada ({reader.approved_phase}) no se incorporan a las cantidades actuales.')
    other = [(i, t[0]) for i, t in enumerate(reader.tables) if i not in (0, 1, 2, 4, 5, 10, 11, 13, 14, 15, 17, 18, 19) and t[0]]
    if other:
        warnings.append('Tablas adicionales PZH con campos aún no convertidos: ' + ', '.join(f'{i} ({n} registros)' for i, n in other) + '.')
    from .pzh_archive import preserve_pzh_source
    notify(85, 'Conservando el original y verificando el proyecto')
    preserve_pzh_source(budget, reader)
    if reader.tables[9][0]:
        from .concept_keywords import copy_source as copy_keywords
        try:copy_keywords(budget)
        except BudgetError as exc:
            budget.project_metadata['pzh_keyword_pending']=str(exc);warnings.append('Términos de búsqueda PZH pendientes: '+str(exc))
        else:warnings.append(f'Términos de búsqueda PZH convertidos: {reader.tables[9][0]} registros; no cambian códigos ni precios.')
    if native_modules:
        if 'planning' in selected:
            from .agenda import copy_source as copy_agenda
            try:copy_agenda(budget)
            except BudgetError as exc:
                budget.project_metadata['pzh_agenda_pending']=str(exc);warnings.append('Agenda PZH pendiente: '+str(exc))
        from .project_assets import copy_source as copy_assets
        try:copy_assets(budget)
        except BudgetError as exc:
            budget.project_metadata['pzh_assets_pending']=str(exc);warnings.append('Documentos y adjuntos PZH pendientes: '+str(exc))
        from .pzh_native_modules import convert_supported
        conversions=convert_supported(budget,selected,progress)
        pending=sum(r['status']=='pending' for r in conversions)
        warnings.append(f'Copias nativas editables: {len(conversions)-pending} conversiones disponibles; {pending} pendientes. Documentos como borradores, sin movimientos ni cobros/pagos históricos inventados.')
    warnings.append('El PZH fuente completo se conserva como instantánea verificable en el proyecto JSON. Conservar los bytes originales no equivale a convertir todos sus módulos en datos nativos editables.')
    import json
    budget.project_metadata['pzh_import_modules']=json.dumps(sorted(selected))
    budget.project_metadata.update({'import_format': 'pzh-8x-experimental',
                                    'import_source': filename,
                                    'import_sha256': hashlib.sha256(data).hexdigest(),
                                    'pzh_import_notes': '\n'.join(warnings)})
    budget.import_warnings = tuple(warnings)
    # Validate the full persistence contract before returning a model to the UI.
    from .storage import dumps, loads
    budget = loads(dumps(budget))
    from .pzh_archive import pzh_source_bytes
    if pzh_source_bytes(budget) != data:
        raise PZHImportError('La instantánea PZH no sobrevivió al guardado del proyecto.')
    budget.import_warnings = tuple(warnings)
    notify(100, 'Importación terminada')
    return PZHImportResult(budget, tuple(warnings))

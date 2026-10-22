"""Independent bounded LZHUF text decoding and plain-text RTF projection.

Implements the published LH1/LZHUF format, not code from Presto. RTF bytes
remain available separately: this projection is not a rich-text editor.
"""
import codecs
import struct

from .budget import BudgetError


class PZHTextError(BudgetError):
    pass


MAX_TEXT_BYTES = 16 * 1024 * 1024
_SYMBOLS = 314
_NODES = 627
_ROOT = 626


class _Bits:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def take(self, count):
        value = 0
        for _ in range(count):
            if self.position >= len(self.data) * 8:
                raise PZHTextError('Texto PZH comprimido truncado.')
            at, shift = divmod(self.position, 8)
            value = value * 2 + ((self.data[at] >> (7 - shift)) & 1)
            self.position += 1
        return value


class _AdaptiveTree:
    def __init__(self):
        self.weights = [1] * _SYMBOLS + [0] * (_NODES + 1 - _SYMBOLS)
        self.children = [i + _NODES for i in range(_SYMBOLS)] + [0] * (_NODES - _SYMBOLS)
        self.parents = [0] * (_NODES + _SYMBOLS)
        for i in range(_SYMBOLS):
            self.parents[i + _NODES] = i
        for i in range(_SYMBOLS, _NODES):
            left = (i - _SYMBOLS) * 2
            self.children[i] = left
            self.weights[i] = self.weights[left] + self.weights[left + 1]
            self.parents[left] = self.parents[left + 1] = i
        self.weights[_NODES] = 65535

    def _rescale(self):
        # Keep ordered leaves, halve their weights, then rebuild sibling pairs.
        nodes = [((self.weights[i] + 1) // 2, value)
                 for i, value in enumerate(self.children) if value >= _NODES]
        cursor = 0
        while len(nodes) < _NODES:
            weight = nodes[cursor][0] + nodes[cursor + 1][0]
            at = len(nodes)
            while at > cursor + 1 and nodes[at - 1][0] > weight:
                at -= 1
            nodes.insert(at, (weight, cursor))
            cursor += 2
        for i, (weight, child) in enumerate(nodes):
            self.weights[i] = weight
            self.children[i] = child
            self.parents[child] = i
            if child < _NODES:
                self.parents[child + 1] = i
        self.parents[_ROOT] = 0

    def symbol(self, bits):
        node = self.children[_ROOT]
        while node < _NODES:
            node = self.children[node + bits.take(1)]
        symbol = node - _NODES
        if self.weights[_ROOT] == 32768:
            self._rescale()
        node = self.parents[symbol + _NODES]
        while True:
            self.weights[node] += 1
            other = node
            while self.weights[other + 1] < self.weights[node]:
                other += 1
            if other != node:
                self.weights[node], self.weights[other] = self.weights[other], self.weights[node]
                left, right = self.children[node], self.children[other]
                for child, new_parent in ((left, other), (right, node)):
                    self.parents[child] = new_parent
                    if child < _NODES:
                        self.parents[child + 1] = new_parent
                self.children[node], self.children[other] = right, left
                node = other
            node = self.parents[node]
            if node == 0:
                return symbol


def decompress_pzh_text(payload, expected_size):
    """Decode one size-prefixed LZHUF block with a 4096-byte space dictionary."""
    if type(expected_size) is not int or not 0 <= expected_size <= MAX_TEXT_BYTES:
        raise PZHTextError('Longitud de texto PZH fuera del límite de 16 MiB.')
    if len(payload) < 4 or struct.unpack_from('<I', payload)[0] != expected_size:
        raise PZHTextError('La cabecera comprimida PZH no coincide con su longitud declarada.')
    bits = _Bits(payload[4:])
    tree = _AdaptiveTree()
    lengths = [3] + [4] * 3 + [5] * 8 + [6] * 12 + [7] * 24 + [8] * 16
    positions = {}
    prefix = previous = 0
    for group, length in enumerate(lengths):
        prefix <<= length - previous
        positions[length, prefix] = group
        prefix += 1
        previous = length
    ring = bytearray(b' ' * 4096)
    cursor = 4036
    output = bytearray()
    while len(output) < expected_size:
        symbol = tree.symbol(bits)
        if symbol < 256:
            chunk = bytes([symbol])
        else:
            prefix = 0
            for length in range(1, 9):
                prefix = prefix * 2 + bits.take(1)
                if (length, prefix) in positions:
                    break
            else:
                raise PZHTextError('Prefijo de distancia PZH inválido.')
            distance = (positions[length, prefix] << 6) + bits.take(6) + 1
            count = symbol - 253
            if len(output) + count > expected_size:
                raise PZHTextError('Referencia comprimida PZH excede el texto declarado.')
            # Copy incrementally: a match can overlap its own growing output.
            for _ in range(count):
                value = ring[(cursor - distance) & 4095]
                output.append(value)
                ring[cursor] = value
                cursor = (cursor + 1) & 4095
            continue
        output.extend(chunk)
        ring[cursor] = symbol
        cursor = (cursor + 1) & 4095
    if (bits.position + 7) // 8 != len(bits.data):
        raise PZHTextError('Datos adicionales después del texto PZH comprimido.')
    return bytes(output)


_DESTINATIONS = frozenset(('fonttbl', 'colortbl', 'stylesheet', 'info', 'pict', 'object',
    'filetbl', 'listtable', 'listoverridetable', 'generator', 'header', 'footer',
    'headerl', 'headerr', 'footerl', 'footerr', 'fldinst', 'datastore', 'themedata',
    'colorschememapping', 'xmlnstbl', 'rsidtbl'))
_TEXT_CONTROLS = {'par': '\n', 'line': '\n', 'tab': '\t', 'emdash': '—',
                  'endash': '–', 'bullet': '•', 'lquote': '‘', 'rquote': '’',
                  'ldblquote': '“', 'rdblquote': '”'}


def _rtf_projection(data, rich=False):
    """Read text groups and escapes, ignoring formatting and opaque destinations."""
    if not data.startswith(b'{\\rtf') or len(data) > MAX_TEXT_BYTES:
        raise PZHTextError('Documento RTF PZH no reconocido o demasiado grande.')
    # Latin-1 keeps byte indices stable while control words are parsed.
    source = data.decode('latin1')
    stack = []
    ignored, fallback, encoding = False, 1, 'cp1252'
    color_table=False;colors=[];rgb={}
    result = []
    runs = []
    style = dict(bold=False, italic=False, underline=False, strike=False, size=12)
    def emit(value):
        result.append(value)
        if rich:
            if runs and {key:item for key,item in runs[-1].items() if key!='text'}==style:
                runs[-1]['text'].append(value)
            else:
                if len(runs) >= 100000:
                    raise PZHTextError('Demasiados fragmentos RTF con formato.')
                runs.append(dict(text=[value], **style))
    skip = 0
    at = 0
    while at < len(source):
        char = source[at]
        at += 1
        if char == '{':
            if len(stack) >= 256:
                raise PZHTextError('RTF PZH con demasiados grupos anidados.')
            stack.append((ignored, fallback, encoding, dict(style), color_table))
        elif char == '}':
            if not stack:
                raise PZHTextError('Cierre de grupo RTF sin apertura.')
            ignored, fallback, encoding, style, color_table = stack.pop()
        elif char == '\\':
            if at >= len(source):
                raise PZHTextError('Escape RTF incompleto.')
            symbol = source[at]
            at += 1
            if symbol == '*':
                ignored = True
            elif symbol in ('\\', '{', '}', '~', '_', '-') or symbol == "'":
                if symbol == "'":
                    try:
                        digits = source[at:at + 2]
                        if len(digits) != 2 or any(c not in '0123456789abcdefABCDEF' for c in digits):
                            raise ValueError('dos cifras hexadecimales requeridas')
                        value = bytes([int(digits, 16)]).decode(encoding)
                    except (ValueError, UnicodeError) as exc:
                        raise PZHTextError('Escape hexadecimal RTF no válido.') from exc
                    at += 2
                else:
                    value = {'~': '\u00a0', '_': '\u2011', '-': '\u00ad'}.get(symbol, symbol)
                if skip:
                    skip -= 1
                elif not ignored:
                    emit(value)
            elif symbol.isalpha() and symbol.isascii():
                start = at - 1
                while at < len(source) and source[at].isascii() and source[at].isalpha():
                    at += 1
                word = source[start:at]
                start = at
                if at < len(source) and source[at] == '-':
                    at += 1
                while at < len(source) and source[at] in '0123456789':
                    at += 1
                number = source[start:at]
                parameter = int(number) if number not in ('', '-') and len(number) <= 10 else None
                if at < len(source) and source[at] == ' ':
                    at += 1
                if word == 'bin':
                    if parameter is None or parameter < 0 or at + parameter > len(source):
                        raise PZHTextError('Longitud binaria RTF no válida.')
                    at += parameter
                elif word=='colortbl' and not ignored:
                    if colors:raise PZHTextError('Tablas de colores RTF repetidas no admitidas.')
                    color_table=True;ignored=True;rgb={}
                elif color_table and word in ('red','green','blue'):
                    if parameter is None or not 0<=parameter<=255:raise PZHTextError('Componente de color RTF inválido.')
                    rgb[word]=parameter
                elif word in _DESTINATIONS:
                    ignored = True
                elif word == 'ansicpg' and parameter is not None:
                    encoding = 'cp' + str(parameter)
                    try:
                        codecs.lookup(encoding)
                    except LookupError as exc:
                        raise PZHTextError('Página de códigos RTF no admitida.') from exc
                elif word == 'uc' and parameter is not None:
                    if not 0 <= parameter <= 16:
                        raise PZHTextError('Longitud de sustitución Unicode RTF no admitida.')
                    fallback = parameter
                elif word == 'u' and parameter is not None:
                    if not -32768 <= parameter <= 65535:
                        raise PZHTextError('Unidad Unicode RTF fuera de rango.')
                    if not ignored:
                        emit(chr(parameter & 65535))
                    skip = fallback
                elif word in _TEXT_CONTROLS and not ignored:
                    emit(_TEXT_CONTROLS[word])
                elif not ignored and word in ('b', 'i', 'ul', 'strike'):
                    style[{'b':'bold','i':'italic','ul':'underline','strike':'strike'}[word]] = parameter != 0
                elif not ignored and word == 'ulnone':
                    style['underline'] = False
                elif not ignored and word == 'plain':
                    alignment=style.get('alignment')
                    style = dict(bold=False, italic=False, underline=False, strike=False, size=12)
                    if alignment:style['alignment']=alignment
                elif not ignored and word=='cf' and parameter is not None:
                    if parameter<0 or parameter>=len(colors):
                        if parameter!=0:raise PZHTextError('Índice de color RTF fuera de la tabla.')
                    color=colors[parameter] if 0<=parameter<len(colors) else None
                    if color is None:style.pop('color',None)
                    else:style['color']=color
                elif not ignored and word in ('ql','qc','qr','qj','pard'):
                    alignment={'qc':'center','qr':'right','qj':'justify'}.get(word)
                    if alignment:style['alignment']=alignment
                    else:style.pop('alignment',None)
                elif not ignored and word == 'fs' and parameter is not None and 2 <= parameter <= 400:
                    style['size'] = parameter / 2
            # Unknown control symbols carry formatting, not visible text.
        elif char==';' and color_table:
            if len(colors)>=4096:raise PZHTextError('Demasiados colores RTF.')
            colors.append('#'+''.join(f'{rgb.get(c,0):02x}' for c in ('red','green','blue')) if rgb else None);rgb={}
        elif char not in '\r\n':
            if skip:
                skip -= 1
            elif not ignored:
                emit(char.encode('latin1').decode(encoding))
    if stack:
        raise PZHTextError('Documento RTF con grupos sin cerrar.')
    text = ''.join(result)
    # Join UTF-16 surrogate pairs emitted by consecutive RTF Unicode escapes.
    try:
        if rich:
            for run in runs:
                run['text'] = ''.join(run['text']).encode('utf-16-le', 'surrogatepass').decode('utf-16-le')
            return runs
        return text.encode('utf-16-le', 'surrogatepass').decode('utf-16-le').strip('\r\n')
    except UnicodeError as exc:
        raise PZHTextError('Secuencia Unicode RTF incompleta.') from exc


def rtf_plain_text(data):
    return _rtf_projection(data)


def rtf_rich_runs(data):
    """Character styles, explicit text colours and basic paragraph alignment.

    Original objects and unsupported layout stay in the preserved source RTF.
    """
    return _rtf_projection(data, rich=True)

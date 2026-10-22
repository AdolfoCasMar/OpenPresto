"""Lector inicial, conservador, de conceptos y textos FIEBDC-3.

No evalúa descomposiciones ni mediciones. Mantiene los bytes originales para
permitir guardar una copia íntegra, incluidos los registros no interpretados.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
import codecs
import csv
import io
import re

MAX_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 100_000


class BC3Error(ValueError):
    pass


@dataclass
class Concept:
    code: str
    unit: str = ""
    summary: str = ""
    price: Decimal | None = None
    text: str = ""


@dataclass
class Document:
    concepts: list[Concept]
    raw: bytes
    encoding: str
    version: str
    generator: str
    counts: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def _encoding(raw: bytes) -> tuple[str, str | None]:
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig", None
    # El registro V solo requiere ASCII para identificar el juego declarado.
    header = re.search(rb"~V\|([^~]*)", raw, re.IGNORECASE)
    fields = header.group(1).split(b"|") if header else []
    charset = fields[4].strip().upper() if len(fields) > 4 else b""
    known = {b"ANSI": "cp1252", b"850": "cp850", b"437": "cp437",
             b"UTF-8": "utf-8", b"UTF8": "utf-8"}
    if charset in known:
        return known[charset], None
    if charset:
        raise BC3Error("Juego de caracteres no admitido: " + charset.decode("ascii", "replace"))
    return "cp850", "Sin juego de caracteres declarado: se ha usado CP850."


def parse(raw: bytes) -> Document:
    if len(raw) > MAX_BYTES:
        raise BC3Error("Esta versión admite archivos de hasta 32 MiB.")
    if b"\x00" in raw:
        raise BC3Error("El archivo parece binario; se requiere un BC3 de texto.")
    encoding, warning = _encoding(raw)
    try:
        content = raw.decode(encoding)
    except UnicodeError as exc:
        raise BC3Error(f"El contenido no coincide con la codificación {encoding}.") from exc
    prefix, separator, rest = content.partition("~")
    if not separator or prefix.strip("\ufeff\x1a\r\n\t "):
        raise BC3Error("No se reconoce un archivo BC3: falta el inicio de registros.")
    records = rest.split("~")
    if len(records) > MAX_RECORDS:
        raise BC3Error("Demasiados registros para esta versión (máximo 100.000).")
    concepts: dict[str, Concept] = {}
    texts: dict[str, str] = {}
    aliases: dict[str, str] = {}
    counts: Counter[str] = Counter()
    warnings = [warning] if warning else []
    version = generator = "No declarado"
    for number, record in enumerate(records, 1):
        fields = record.strip("\r\n\x1a ").split("|")
        kind = fields[0].strip().upper()
        if not re.fullmatch(r"[A-Z]", kind):
            raise BC3Error(f"Registro {number}: identificador de registro inválido.")
        counts[kind] += 1
        if kind == "V":
            version = fields[2].strip() if len(fields) > 2 else version
            generator = fields[3].strip() if len(fields) > 3 else generator
        elif kind == "C":
            if len(fields) < 2 or not fields[1].strip():
                raise BC3Error(f"Registro {number}: concepto sin código.")
            codes = [s.strip() for s in fields[1].split("\\") if s.strip()]
            if not codes:
                raise BC3Error(f"Registro {number}: concepto sin código.")
            code = codes[0]
            if code in concepts:
                warnings.append(f"Concepto repetido {code}: se aplican sus campos posteriores no vacíos.")
            concept = concepts.setdefault(code, Concept(code))
            for alias in codes:
                previous = aliases.get(alias)
                if previous is not None and previous != code:
                    raise BC3Error(f"Alias ambiguo: {alias}.")
                aliases[alias] = code
            if len(fields) > 2 and fields[2].strip():
                concept.unit = fields[2].strip()
            if len(fields) > 3 and fields[3].strip():
                concept.summary = " ".join(fields[3].split())
            if len(fields) > 4 and fields[4].strip("\\ \r\n"):
                prices = fields[4].strip().split("\\")
                value = prices[0].strip()
                if any(p.strip() for p in prices[1:]):
                    warnings.append(f"{code}: varios precios; se muestra el primero, sin seleccionar ámbito.")
                try:
                    # Decimal evita introducir errores binarios en importes.
                    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value):
                        raise InvalidOperation
                    concept.price = Decimal(value)
                except InvalidOperation:
                    concept.price = None
                    warnings.append(f"{code}: precio no interpretable ({value[:60]}); no se sustituye por cero.")
        elif kind == "T":
            if len(fields) < 3 or not fields[1].strip():
                warnings.append(f"Registro T {number} incompleto.")
            else:
                texts[fields[1].strip()] = fields[2].strip()
    if not concepts:
        raise BC3Error("El archivo no contiene conceptos ~C que esta versión pueda mostrar.")
    for code, text in texts.items():
        target = concepts.get(aliases.get(code, code))
        if target is not None:
            target.text = text
        else:
            warnings.append(f"Texto sin concepto asociado: {code}.")
    pending = sorted(set(counts) - {"V", "C", "T"})
    if pending:
        warnings.append("Registros conservados sin interpretar: " + ", ".join("~" + k for k in pending) + ".")
    return Document(list(concepts.values()), raw, encoding, version, generator, dict(counts), warnings)


def read(path: str | Path) -> Document:
    with Path(path).open("rb") as stream:
        return parse(stream.read(MAX_BYTES + 1))


def concepts_csv(document: Document) -> bytes:
    """CSV de consulta; no equivale a exportar un presupuesto completo."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Código", "Unidad", "Resumen", "Precio declarado", "Texto"])
    def safe(value: str) -> str:
        # Evita que un código/descripción se interprete como fórmula en Excel.
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for c in document.concepts:
        writer.writerow([safe(c.code), safe(c.unit), safe(c.summary),
                         str(c.price) if c.price is not None else "", safe(c.text)])
    return output.getvalue().encode("utf-8-sig")

"""Read the economic field of ~K without applying calculation settings.

Field order documented by FIEBDC-3/2024, PDF pages 5–6. Historical support
and runtime application remain separate gates; decimal fields stay opaque.
"""
from decimal import Decimal, InvalidOperation


NAMES = ('CI', 'GG', 'BI', 'BAJA', 'IVA')


def economic_coefficients(field: str) -> tuple[Decimal, ...]:
    if not isinstance(field, str):
        raise ValueError('El campo económico ~K debe ser texto')
    parts = field.strip().split('\\')
    if parts and not parts[-1].strip():
        parts.pop()  # optional terminal separator, not another coefficient
    if len(parts) > len(NAMES):
        raise ValueError('Demasiados coeficientes económicos en ~K')
    values = []
    for name, part in zip(NAMES, parts):
        try:
            value = Decimal(part.strip()) if part.strip() else Decimal(0)
        except InvalidOperation as exc:
            raise ValueError(f'Coeficiente {name} de ~K incorrecto') from exc
        if not value.is_finite():
            raise ValueError(f'Coeficiente {name} de ~K no finito')
        values.append(value)
    return tuple(values + [Decimal(0)] * (len(NAMES) - len(values)))

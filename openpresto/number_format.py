"""Formato de presentación de números; el almacenamiento usa Decimal textual."""
from decimal import Decimal
from PySide6.QtCore import QSettings


def display(value):
    text = str(value)
    if isinstance(value, Decimal) and QSettings().value('numbers/decimal_separator','.',type=str) == ',':
        return text.replace('.',',')
    return text


def input_number(text):
    return text.strip().replace(',', '.')

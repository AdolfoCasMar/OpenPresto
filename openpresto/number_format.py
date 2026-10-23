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


def formatter(separator):
    """Snapshot the separator for a single table render, never across edits."""
    if separator != ',':
        return str
    def format_value(value):
        text = str(value)
        return text.replace('.', ',') if isinstance(value, Decimal) else text
    return format_value

"""Shared code-cell presentation; colours never determine economic rules."""
from unicodedata import normalize
from PySide6.QtGui import QColor


COLOURS = {
    'obra': ('#bdeee9', '#153f43'),
    'capitulo': ('#c9ecee', '#183e4c'),
    'partida': ('#dfebfa', '#234568'),
    'mano de obra': ('#fff0b8', '#594510'),
    'maquinaria': ('#e6dcf5', '#49345e'),
    'material': ('#dcefdc', '#284b2b'),
    'porcentaje': ('#f5ced0', '#7a2932'),
    'otro': ('#edf0f3', '#344250'),
}


def code_kind(concept, root=None):
    if '%' in concept.code:
        return 'porcentaje'
    if concept.code == root:
        return 'obra'
    nature = ''.join(c for c in normalize('NFD', concept.nature.casefold().strip())
                     if not '\u0300' <= c <= '\u036f')
    return nature if nature in COLOURS else 'otro'


def style_code(item, concept, root=None, column=None):
    background, foreground = COLOURS[code_kind(concept, root)]
    if column is None:
        item.setBackground(QColor(background)); item.setForeground(QColor(foreground))
    else:
        item.setBackground(column, QColor(background)); item.setForeground(column, QColor(foreground))

"""Small, bundled vector icons. No desktop theme or external files required."""
from functools import lru_cache
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer

PATHS = {
 'budget': '<rect x="7" y="2" width="14" height="20" fill="#697b92" stroke="none"/><path d="M11 6h6M11 11h6M11 16h6" stroke="white"/><text x="1" y="17" fill="#8094ae" stroke="none" font-size="13">€</text>',
 'concepts': '<rect x="5" y="2" width="15" height="20" fill="#66717e" stroke="none"/><path d="M8 6h2m4 0h3M8 11h2m4 0h3M8 16h2m4 0h3" stroke="white"/>',
 'parties': '<circle cx="6" cy="12" r="3" fill="#8498b3" stroke="none"/><path d="M1 21v-3a5 5 0 0 1 10 0v3" fill="#8498b3" stroke="none"/><rect x="13" y="2" width="8" height="19" fill="#647080" stroke="none"/><path d="M15 6h4m-4 5h4m-4 5h4" stroke="white"/>',
 'gantt': '<path d="M3 2v19h19M5 6h10M9 11h11M13 16h8"/><path d="M5 6h10M9 11h11M13 16h8" stroke="#8399b6" stroke-width="4"/>',
 'precedence': '<rect x="2" y="2" width="8" height="5" fill="#879ab4" stroke="none"/><rect x="14" y="17" width="8" height="5" fill="#879ab4" stroke="none"/><path d="M6 8v5h12v3m-3-3 3 3 3-3"/>',
 'resources': '<path d="M3 14a9 9 0 0 1 18 0M2 14h20M10 13V3h4v10" fill="#efda45" stroke="#a89d53"/><path d="M4 18h16"/>',
 'phases': '<rect x="3" y="5" width="18" height="17"/><path d="M3 10h18M8 2v6M16 2v6"/><text x="6" y="20" fill="#699371" stroke="none" font-size="10">31</text>',
 'agenda': '<rect x="3" y="3" width="18" height="19"/><path d="M3 8h18M7 12h3m4 0h3m-10 5h3m4 0h3"/><path d="M3 3h18v5H3" fill="#8498b3" stroke="none"/>',
 'attachments': '<path d="M8 17V6a4 4 0 0 1 8 0v12a6 6 0 0 1-12 0V8m8-2v11a2 2 0 0 1-4 0" stroke="#555e69"/>',
 'contract': '<path d="M5 2h12l4 4v16H5z"/><path d="M9 6h5M9 10h8M9 14h8"/><circle cx="6" cy="18" r="5" fill="#c99743" stroke="none"/><path d="m3 18 2 2 4-5" stroke="white"/>',
 'offer': '<path d="M4 2h12l4 4v16H4z"/><circle cx="15" cy="17" r="6" fill="#8b73a7" stroke="none"/><text x="11" y="21" fill="white" stroke="none" font-size="12">€</text>',
 'orders': '<path d="M4 2h12l4 4v16H4z"/><circle cx="15" cy="17" r="6" fill="#8870a6" stroke="none"/><text x="11" y="21" fill="white" stroke="none" font-size="11">P</text>',
 'deliveries': '<path d="M4 2h12l4 4v16H4z"/><circle cx="15" cy="17" r="6" fill="#7d96ad" stroke="none"/><text x="11" y="21" fill="white" stroke="none" font-size="11">E</text>',
 'invoices': '<path d="M4 2h12l4 4v16H4z"/><circle cx="15" cy="17" r="6" fill="#6a9b76" stroke="none"/><text x="12" y="21" fill="white" stroke="none" font-size="11">F</text>',
 'supplies': '<path d="M3 2h18v20H3z" fill="#d9aa4e" stroke="none"/><path d="M7 6h3m4 0h3M7 11h3m4 0h3M7 16h3m4 0h3" stroke="white"/>',
 'dues': '<path d="M5 2v20M1 6h8M1 11h8M1 16h8"/><ellipse cx="17" cy="6" rx="4" ry="3" fill="#dfad51" stroke="none"/><path d="M13 6v13a4 3 0 0 0 8 0V6M13 11a4 3 0 0 0 8 0M13 15a4 3 0 0 0 8 0" stroke="#c18c34"/>',
 'chapters': '<path d="M4 4h16v4H4zM4 10h16v4H4zM4 16h16v4H4z"/>',
 'chapter-items': '<path d="M3 3h18v5H3zM5 8v12M5 13h5M5 19h5M10 11h11v4H10zM10 17h11v4H10z"/>',
 'work': '<path d="M3 4h18v16H3zM3 9h18M3 14h18M9 4v5M15 9v5M9 14v6"/>',
 'material': '<rect x="6" y="2" width="12" height="20"/><path d="M6 7h12M6 12h12M6 17h12M12 2v20"/>',
 'labour': '<path d="M4 11a8 8 0 0 1 16 0M2 11h20M8 10V5M16 10V5M6 13a6 6 0 0 0 12 0M4 22v-3l5-2M20 22v-3l-5-2"/>',
 'machine': '<path d="M3 17h18M6 17V9h8v8M10 9V4h5l3 8h3v5"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',

 'new': '<path d="M14 3H5v18h14V8zM14 3v5h5M8 14h8M12 10v8"/>',
 'open': '<path d="M3 8V5h7l2 3h9l-3 12H3zM3 8h18"/>',
 'save': '<path d="M4 3h14l3 3v15H3V3zM7 3v6h10V3M7 21v-8h10v8"/>',
 'import': '<path d="M15 3h5v18H4v-5M3 9h12M10 4l5 5-5 5"/>',
 'export': '<path d="M9 3H4v18h16v-5M9 9h12M16 4l5 5-5 5"/>',
 'undo': '<path d="M9 4 3 10l6 6M3 10h11a6 6 0 0 1 0 12"/>',
 'redo': '<path d="m15 4 6 6-6 6M21 10h-11a6 6 0 0 0 0 12"/>',
 'add': '<circle cx="12" cy="12" r="9"/><path d="M7 12h10M12 7v10"/>',
 'link': '<path d="m9 15 6-6M9 17l-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M15 7l2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0"/>',
 'measure': '<path d="m3 16 13-13 5 5L8 21zM7 12l2 2M10 9l2 2M13 6l2 2"/>',
 'calculate': '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 6h8M8 11h2M14 11h2M8 15h2M14 15h2M8 19h2M14 19h2"/>',
 'calendar': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18m-14 5 3 3 7-5"/>',
 'text': '<path d="M5 3h10l4 4v14H5zM14 3v5h5M8 12h8M8 16h8"/>',
 'delete': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
 'up': '<path d="m5 12 7-7 7 7M12 5v16"/>',
 'down': '<path d="m5 12 7 7 7-7M12 19V3"/>',
 'search': '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
 'edit': '<path d="m4 16 12-12 4 4L8 20l-5 1zM13 7l4 4"/>',
 'copy': '<rect x="8" y="8" width="13" height="13" rx="1"/><path d="M16 8V3H3v13h5"/>',
 'help': '<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 4M12 17v1"/>',
 'settings': '<path d="M3 6h18M3 12h18M3 18h18M7 3v6M16 9v6M9 15v6"/>',
 'tree': '<path d="M4 3v15h5M4 9h5"/><rect x="9" y="5" width="11" height="7" rx="1"/><rect x="9" y="15" width="11" height="7" rx="1"/>',
}


@lru_cache(maxsize=64)
def icon(name):
    result = QIcon()
    color = '#b7444c' if name == 'delete' else '#4e806b' if name == 'save' else '#b1434e' if name == 'material' else '#bb9234' if name in ('labour','machine') else '#7287a2'
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
           + PATHS.get(name, PATHS['text']) + '</svg>').encode()
    renderer = QSvgRenderer(svg)
    for size in (16, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


def action_icon(label):
    text = label.lower().replace('…', '').strip()
    for prefixes, name in (
        (('nuevo',), 'new'), (('abrir', 'proyectos recientes', 'recuperar'), 'open'),
        (('guardar',), 'save'), (('importar', 'fiebdc', 'presto pzh'), 'import'), (('exportar',), 'export'),
        (('deshacer',), 'undo'), (('rehacer',), 'redo'), (('eliminar', 'cerrar'), 'delete'),
        (('añadir concepto',), 'add'), (('insertar relación', 'añadir relación', 'relaciones'), 'link'),
        (('introducir medición', 'añadir medición', 'medición', 'copiar mediciones'), 'measure'),
        (('calcular', 'precios', 'motor económico', 'multiplicar', 'operar precios', 'ajustar'), 'calculate'),
        (('certificación', 'calendario'), 'calendar'), (('texto', 'avisos', 'informe', 'vista previa'), 'text'),
        (('buscar',), 'search'), (('editar', 'reemplazar'), 'edit'),
        (('copiar', 'duplicar'), 'copy'), (('subir', 'ir a raíz'), 'up'), (('bajar',), 'down'),
        (('ayuda', 'acerca'), 'help'), (('preferencias', 'precisión', 'configurar', 'porcentajes'), 'settings'),
        (('estructura', 'conceptos'), 'tree'),
    ):
        if text.startswith(prefixes):
            return icon(name)
    return QIcon()


def nature_icon(nature):
    name = {'capitulo':'tree', 'capítulo':'tree', 'partida':'work',
            'material':'material', 'mano de obra':'labour', 'maquinaria':'machine'}.get(nature.casefold(), 'work')
    return icon(name)

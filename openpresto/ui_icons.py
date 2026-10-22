"""Small, bundled vector icons. No desktop theme or external files required."""
from functools import lru_cache
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer

PATHS = {
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

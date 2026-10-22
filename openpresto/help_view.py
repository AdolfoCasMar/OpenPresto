"""Ayuda local integrada, independiente de recursos de investigación."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox

TEXT = """<h1>OpenPresto</h1>
<p>Aplicación independiente de presupuestos y mediciones.</p>
<h2>Proyectos</h2><p>Archivo permite crear, abrir, guardar, recuperar y abrir otra ventana.
Los proyectos recientes y preferencias se conservan en la configuración del usuario.
El guardado JSON conserva la versión anterior como .bak. Las copias de recuperación se
escriben periódicamente cuando existen cambios. Guarda una recuperación con otro nombre.</p>
<h2>Edición</h2><p>Selecciona una fila en Precios para sincronizar texto y mediciones.
F2 edita celdas; Ctrl+Z y Ctrl+Y recuperan cambios. Editar relación permite reorganizar
la jerarquía con validación de ciclos. Duplicar crea un concepto con sus componentes
compartidos; modificar un recurso compartido actualiza todas sus apariciones.</p>
<p>Ctrl+C copia filas de Precios; Ctrl+V las inserta en el nivel actual. Los conflictos
entre conceptos se notifican. Ctrl+H reemplaza resúmenes y textos de toda la obra.
Copiar mediciones sustituye las líneas del destino en una sola operación deshacible.</p>
<h2>Cálculo</h2><p>Las cantidades con mediciones y los precios descompuestos son calculados.
Configura precisión económica en el perfil nativo. Los perfiles económicos anteriores
conservan sus reglas y limitaciones explícitas.</p>
<h2>Intercambio y salida</h2><p>BC3 importa un perfil parcial documentado; guarda JSON para
conservar todos los datos nativos. La exportación rechaza configuraciones sin representación.
Informes ofrece presupuesto, resumen, precios y mediciones en PDF, HTML y CSV, además de
vista previa e impresión. Los importes provienen del motor económico activo.</p>
<h2>Documentos y ventanas</h2><p>Vincula archivos a un concepto desde Archivo. Los documentos
son referencias externas y deben acompañar al proyecto si se traslada a otro equipo.
Ventana guarda y restaura posiciones y visibilidad. Cascada y mosaico reorganizan paneles.</p>
<p>Versión de desarrollo: validación funcional de la integración pendiente.</p>"""


def show_help(host):
    dialog = QDialog(host)
    dialog.setWindowTitle('Ayuda de OpenPresto')
    dialog.resize(800, 650)
    layout = QVBoxLayout(dialog)
    view = QTextBrowser()
    view.setHtml(TEXT)
    layout.addWidget(view)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()

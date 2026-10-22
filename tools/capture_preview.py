"""Captura de revisión visual de la interfaz; no necesita sesión gráfica."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from openpresto.app import MainWindow

app = QApplication([])
if os.name == 'nt':
    # El plugin offscreen de Windows no enumera las fuentes del sistema.
    font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/segoeui.ttf'
    if font_path.exists():
        identifier = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(identifier)
        if families:
            app.setFont(QFont(families[0], 10))
window = MainWindow()
window.open_demo()
window.resize(1180, 780)
window.show()
app.processEvents()
window.table.setCurrentIndex(window.proxy.index(6, 0))
app.processEvents()
ROOT.joinpath('dist').mkdir(exist_ok=True)
assert window.grab().save(str(ROOT / 'dist/openpresto-preview.png'))
window.close()

"""Entrada compatible al espacio de trabajo MDI de OpenPresto."""
import sys
from PySide6.QtWidgets import QApplication
from .theme import DARK_STYLESHEET
from .mdi_workspace import PrestoWorkspace

def main(argv=None):
    import argparse
    from . import __version__, APP_ID
    parser = argparse.ArgumentParser(description='OpenPresto · Presupuestos y mediciones')
    parser.add_argument('file', nargs='?', help='Proyecto JSON o BC3')
    parser.add_argument('--viewer', action='store_true', help='Explorador BC3 de consulta')
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args(argv)
    if args.viewer:
        from .app import main as viewer_main
        return viewer_main([args.file] if args.file else [])
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName('OpenPresto')
    app.setOrganizationName('OpenPresto')
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    window = PrestoWorkspace()
    if args.file:
        window.load_path(args.file)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

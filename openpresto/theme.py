"""Paleta original de OpenPresto, compartida por el espacio MDI."""
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e2229;
    color: #e7eaf0;
}
QMenuBar {
    background-color: #20252d;
    color: #e7eaf0;
    border-bottom: 1px solid #333a45;
}
QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
}
QMenuBar::item:selected {
    background: #2f6fed;
    color: #ffffff;
}
QMenu {
    background-color: #262c36;
    color: #e7eaf0;
    border: 1px solid #3a4350;
}
QMenu::item {
    padding: 6px 24px 6px 24px;
}
QMenu::item:selected {
    background-color: #2f6fed;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    margin: 4px 8px;
    background: #3a4350;
}
QToolBar {
    background: #20252d;
    border: 0;
    border-bottom: 1px solid #333a45;
    spacing: 8px;
    padding: 6px;
}
QToolButton {
    background: #2b313c;
    color: #eef3ff;
    border: 1px solid #404957;
    border-radius: 4px;
    padding: 5px 10px;
}
QToolButton:hover {
    background: #364052;
}
QToolButton:pressed {
    background: #2f6fed;
}
QLabel {
    color: #e7eaf0;
}
QPushButton {
    background-color: #2b313c;
    color: #eef3ff;
    border: 1px solid #404957;
    border-radius: 4px;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #364052;
}
QPushButton:pressed {
    background-color: #2f6fed;
}
QPushButton:disabled, QToolButton:disabled, QMenu::item:disabled {
    color: #7d8795;
}
QTableWidget {
    background-color: #20252d;
    alternate-background-color: #252b35;
    color: #e7eaf0;
    gridline-color: #39414d;
    border: 1px solid #39414d;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 4px;
}
QHeaderView::section {
    background-color: #2c3440;
    color: #f0f4fa;
    padding: 7px;
    border: 0;
    border-right: 1px solid #3b4452;
    border-bottom: 1px solid #3b4452;
}
QTableCornerButton::section {
    background-color: #2c3440;
    border: 1px solid #3b4452;
}
QTabWidget::pane {
    border: 1px solid #39414d;
    background: #1e2229;
}
QTabBar::tab {
    background: #252b35;
    color: #cfd6e1;
    border: 1px solid #39414d;
    border-bottom: none;
    padding: 8px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #2f6fed;
    color: #ffffff;
}
QTabBar::tab:hover:!selected {
    background: #303846;
}
QStatusBar {
    background: #20252d;
    color: #dbe3ef;
    border-top: 1px solid #333a45;
}
QLineEdit, QComboBox {
    background-color: #252b35;
    color: #eef3ff;
    border: 1px solid #404957;
    border-radius: 4px;
    padding: 5px 6px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #2f6fed;
}
QDialog, QMessageBox {
    background-color: #1e2229;
    color: #e7eaf0;
}
"""


LIGHT_STYLESHEET = """
QWidget { background: #f4f4f4; color: #252a30; }
QMainWindow, QMdiArea { background: #e5e8ed; }
QMenuBar, QToolBar { background: #f5f5f5; border: 0; spacing: 3px; }
QMenuBar::item { padding: 5px 10px; }
QMenuBar::item:selected, QMenu::item:selected { background: #d5deeb; }
QMenu { background: white; border: 1px solid #b8c0cb; }
QMenu::item { padding: 5px 22px; }
QToolButton { border: 1px solid transparent; padding: 3px; background: transparent; }
QToolButton:hover, QToolButton:checked { background: #e0e6ee; border: 1px solid #b7c1cf; border-radius: 3px; }
QPushButton { background: #fafafa; border: 1px solid #bbc3ce; border-radius: 2px; padding: 3px 7px; }
QPushButton:hover { background: #dce5f1; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit { background: white; border: 1px solid #bdc4ce; padding: 2px; }
QPlainTextEdit, QTextEdit { background: white; color: #20242a; border: 1px solid #c4cad2; selection-background-color: #c4d5ed; }
QTableView, QTreeView { background: white; alternate-background-color: #f5f6f8; gridline-color: #d8dce2; border: 1px solid #c3c8d0; selection-background-color: #c5d4e8; selection-color: #172334; }
QHeaderView::section { background: #eeeeef; color: #333943; border: 0; border-right: 1px solid #c1c5cc; border-bottom: 1px solid #b8bec8; padding: 4px; }
QTabBar::tab { background: #f4f4f4; padding: 5px 12px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { background: white; border-bottom: 2px solid #758aa5; }
QGroupBox { border: 1px solid #c5ccd5; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; }
QMdiSubWindow { background: #f2f2f2; border: 1px solid #c2c8d1; }
QStatusBar { background: #e9edf2; }
QWidget:disabled { color: #949ba5; }
QToolTip { background: #fffde9; color: #252a30; border: 1px solid #aab4c1; padding: 4px; }
"""

"""Persistencia portable de geometrías del espacio de trabajo mediante Qt."""
from PySide6.QtCore import QSettings, QRect


def save_layout(host):
    settings = QSettings()
    settings.beginGroup('workspace')
    settings.remove('')
    settings.setValue('snap',host.window_snapping)
    for key, window in host.windows.items():
        settings.setValue(key + '/geometry', window.geometry())
        settings.setValue(key + '/visible', window.isVisible())
    header = host.prices.horizontalHeader()
    settings.setValue('prices/order',[header.logicalIndex(i) for i in range(host.prices.columnCount())])
    for column in range(host.prices.columnCount()):
        settings.setValue(f'prices/{column}/hidden',host.prices.isColumnHidden(column))
        settings.setValue(f'prices/{column}/width',host.prices.columnWidth(column))
    settings.endGroup()
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise ValueError('No se pudo guardar el espacio de trabajo')


def restore_layout(host):
    host._reference_layout = False
    settings = QSettings()
    settings.beginGroup('workspace')
    area = host.mdi.viewport().rect()
    for key in host.panels:
        geometry = settings.value(key + '/geometry')
        visible = settings.value(key + '/visible', False, type=bool)
        if visible:
            host.show_panel(key)
        window = host.windows.get(key)
        if window is not None:
            if isinstance(geometry, QRect):
                width = min(max(geometry.width(), 200), area.width())
                height = min(max(geometry.height(), 100), area.height())
                x = max(0, min(geometry.x(), area.width() - width))
                y = max(0, min(geometry.y(), area.height() - height))
                window.setGeometry(x, y, width, height)
            window.setVisible(visible)
    order = settings.value('prices/order',list(range(host.prices.columnCount())),type=list)
    if (len(order) == host.prices.columnCount() and all(type(value) is int for value in order)
            and set(order) == set(range(host.prices.columnCount()))):
        header = host.prices.horizontalHeader()
        for visual,logical in enumerate(order):
            header.moveSection(header.visualIndex(logical),visual)
    for column in range(host.prices.columnCount()):
        hidden = settings.value(f'prices/{column}/hidden',False,type=bool)
        width = settings.value(f'prices/{column}/width',host.prices.columnWidth(column),type=int)
        host.prices.setColumnHidden(column,hidden)
        host.prices.setColumnWidth(column,max(24,min(width,2000)))
    settings.endGroup()

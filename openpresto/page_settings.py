"""Configuración de página portable y persistente para informes."""
from PySide6.QtCore import QSettings,QSizeF,QMarginsF
from PySide6.QtGui import QPageLayout,QPageSize


def restore(host):
    if hasattr(host,'_report_page_layout'):
        return host._report_page_layout
    settings=QSettings()
    if not settings.contains('print/page_width'):
        return None
    try:
        width=settings.value('print/page_width',210.0,type=float)
        height=settings.value('print/page_height',297.0,type=float)
        orientation=settings.value('print/orientation',0,type=int)
        margins=[settings.value('print/margin_'+side,10.0,type=float) for side in ('left','top','right','bottom')]
        if not (1 <= width <= 2000 and 1 <= height <= 2000 and orientation in (0,1)
                and all(0 <= value <= 1000 for value in margins)):
            raise ValueError('Tamaño o márgenes de página inválidos')
        page=QPageSize(QSizeF(width,height),QPageSize.Unit.Millimeter)
        layout=QPageLayout(page,QPageLayout.Orientation(orientation),QMarginsF(*margins),QPageLayout.Unit.Millimeter)
        if not layout.isValid():
            raise ValueError('Configuración de página no válida')
        host._report_page_layout=layout
        return layout
    except (ValueError,TypeError,OverflowError) as exc:
        host.statusBar().showMessage('Se usará la página predeterminada: '+str(exc),10000)
        return None


def save(layout):
    settings=QSettings()
    size=layout.pageSize().size(QPageSize.Unit.Millimeter)
    margins=layout.margins(QPageLayout.Unit.Millimeter)
    values={'page_width':size.width(),'page_height':size.height(),'orientation':layout.orientation().value,
            'margin_left':margins.left(),'margin_top':margins.top(),'margin_right':margins.right(),'margin_bottom':margins.bottom()}
    for key,value in values.items():
        settings.setValue('print/'+key,value)
    settings.sync()
    if settings.status()!=QSettings.Status.NoError:
        raise ValueError('No se pudo guardar la configuración de página')

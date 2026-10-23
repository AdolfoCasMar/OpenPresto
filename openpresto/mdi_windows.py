"""Resizable MDI frames with local, optional edge snapping."""
from PySide6.QtCore import Qt,QRect,QSize,QEvent
from PySide6.QtGui import QMouseEvent,QColor,QPen
from PySide6.QtWidgets import QMdiSubWindow,QWidget,QSizePolicy,QLayout,QStyle,QStyleOptionTitleBar,QProxyStyle,QStyleFactory


class WorkspaceStyle(QProxyStyle):
    def __init__(self):super().__init__(QStyleFactory.create('Fusion'))
    def pixelMetric(self,metric,option=None,widget=None):
        if metric==QStyle.PixelMetric.PM_MdiSubWindowFrameWidth:return 2
        if metric==QStyle.PixelMetric.PM_TitleBarHeight and isinstance(widget,QMdiSubWindow):return 22
        return super().pixelMetric(metric,option,widget)
    def drawComplexControl(self,control,option,painter,widget=None):
        if control!=QStyle.ComplexControl.CC_TitleBar or not isinstance(widget,QMdiSubWindow):return super().drawComplexControl(control,option,painter,widget)
        painter.save();painter.fillRect(option.rect,QColor('#e6ecf4' if widget.mdiArea() and widget.mdiArea().activeSubWindow() is widget else '#f3f3f3'))
        painter.setPen(QColor('#c5c9d0'));painter.drawLine(option.rect.bottomLeft(),option.rect.bottomRight())
        buttons=[]
        for sub in (QStyle.SubControl.SC_TitleBarMinButton,QStyle.SubControl.SC_TitleBarMaxButton,QStyle.SubControl.SC_TitleBarNormalButton,QStyle.SubControl.SC_TitleBarCloseButton):
            if option.subControls&sub:
                rect=self.subControlRect(control,option,sub,widget)
                if not rect.isEmpty():buttons.append((sub,rect))
        text=option.rect.adjusted(6,0,-4,0)
        if buttons:text.setRight(min(rect.left() for _,rect in buttons)-4)
        painter.setPen(QColor('#46505d'));painter.drawText(text,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,painter.fontMetrics().elidedText(option.text,Qt.TextElideMode.ElideRight,text.width()))
        for sub,rect in buttons:
            center=rect.center();painter.setPen(QPen(QColor('#68717c'),1))
            if sub==QStyle.SubControl.SC_TitleBarCloseButton:
                painter.drawLine(center.x()-3,center.y()-3,center.x()+3,center.y()+3);painter.drawLine(center.x()-3,center.y()+3,center.x()+3,center.y()-3)
            elif sub==QStyle.SubControl.SC_TitleBarMinButton:painter.drawLine(center.x()-4,center.y()+2,center.x()+4,center.y()+2)
            else:painter.drawRect(center.x()-4,center.y()-3,7,6)
        painter.restore()


def snapped_rect(rect,area,neighbors,edges=(),distance=10):
    """Snap only near parallel edges; resizing never moves the opposite edge."""
    x,y,w,h=rect.x(),rect.y(),rect.width(),rect.height();xs=[0,area.width()];ys=[0,area.height()]
    for other in neighbors:
        if y<=other.y()+other.height()+distance and y+h>=other.y()-distance:xs.extend((other.x(),other.x()+other.width()))
        if x<=other.x()+other.width()+distance and x+w>=other.x()-distance:ys.extend((other.y(),other.y()+other.height()))
    def nearest(values):
        values=[value for value in values if abs(value)<=distance]
        return min(values,key=lambda value:(abs(value),value)) if values else 0
    if not edges:
        x+=nearest([target-edge for target in xs for edge in (x,x+w)])
        y+=nearest([target-edge for target in ys for edge in (y,y+h)])
    else:
        if 'left' in edges:
            delta=nearest([t-x for t in xs]);x+=delta;w-=delta
        if 'right' in edges:w+=nearest([t-x-w for t in xs])
        if 'top' in edges:
            delta=nearest([t-y for t in ys]);y+=delta;h-=delta
        if 'bottom' in edges:h+=nearest([t-y-h for t in ys])
    return QRect(x,y,w,h) if w>=160 and h>=100 else QRect(rect)


class WorkspaceWindow(QMdiSubWindow):
    def __init__(self,host):
        super().__init__();self.host=host;self._press=None;self._resize_edges=();self._moving=False;self.setMouseTracking(True);self.setMinimumSize(160,100)
        self.setOption(QMdiSubWindow.SubWindowOption.RubberBandMove,False)
        self.setOption(QMdiSubWindow.SubWindowOption.RubberBandResize,False)
        # Invisible grips also receive events above child widgets at the edges.
        self._grips=[]
        for _ in range(4):
            grip=QWidget(self);grip.setMouseTracking(True);grip.setAutoFillBackground(False)
            grip.setStyleSheet('background: transparent; border: none;')
            grip.installEventFilter(self);self._grips.append(grip)
        self._position_grips()
    def _position_grips(self):
        if not hasattr(self,'_grips'):return
        band=12;w,h=self.width(),self.height()
        for grip,rect in zip(self._grips,(QRect(0,0,w,band),QRect(0,h-band,w,band),QRect(0,band,band,max(0,h-2*band)),QRect(w-band,band,band,max(0,h-2*band)))):
            grip.setGeometry(rect);grip.setVisible(not self.isMaximized() and not self.isMinimized());grip.raise_()
    def resizeEvent(self,event):
        super().resizeEvent(event);self._position_grips()
    def showEvent(self,event):
        super().showEvent(event);self._position_grips()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange:self._position_grips()
    def eventFilter(self,watched,event):
        if watched in self._grips and event.type()==QEvent.Type.Leave and not self._press:
            self.unsetCursor();watched.unsetCursor()
        if watched in self._grips and event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseMove,QEvent.Type.MouseButtonRelease):
            local=self.mapFromGlobal(event.globalPosition().toPoint())
            forwarded=QMouseEvent(event.type(),local,event.globalPosition(),event.button(),event.buttons(),event.modifiers())
            handler={QEvent.Type.MouseButtonPress:self.mousePressEvent,QEvent.Type.MouseMove:self.mouseMoveEvent,QEvent.Type.MouseButtonRelease:self.mouseReleaseEvent}[event.type()]
            handler(forwarded);watched.setCursor(self.cursor());return True
        return super().eventFilter(watched,event)
    def minimumSizeHint(self):return QSize(160,100)
    def setWidget(self,widget):
        widget.setMinimumSize(0,0);widget.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored)
        if widget.layout():widget.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        super().setWidget(widget)
        self._position_grips()
    def _edges(self,point):
        if self.isMaximized() or self.isMinimized():return ()
        if point.y()>=4 and point.y()<22 and point.x()>self.width()-80:return ()
        edges=[]
        band=12
        if point.x()<band:edges.append('left')
        elif point.x()>=self.width()-band:edges.append('right')
        if point.y()<band:edges.append('top')
        elif point.y()>=self.height()-band:edges.append('bottom')
        if edges:
            # Longer corner targets make diagonal resizing easier to find.
            if point.x()<24 and 'left' not in edges:edges.append('left')
            elif point.x()>=self.width()-24 and 'right' not in edges:edges.append('right')
            if point.y()<24 and 'top' not in edges:edges.append('top')
            elif point.y()>=self.height()-24 and 'bottom' not in edges:edges.append('bottom')
        return tuple(edges)
    def _title_label(self,point):
        option=QStyleOptionTitleBar();option.initFrom(self);option.text=self.windowTitle();option.icon=self.windowIcon();option.titleBarFlags=self.windowFlags();option.titleBarState=self.windowState().value
        option.rect=QRect(0,0,self.width(),self.style().pixelMetric(QStyle.PixelMetric.PM_TitleBarHeight,option,self))
        return self.style().subControlRect(QStyle.ComplexControl.CC_TitleBar,option,QStyle.SubControl.SC_TitleBarLabel,self).contains(point)
    def _magnet(self,rect,edges,modifiers):
        if not self.host.window_snapping or modifiers&Qt.KeyboardModifier.AltModifier:return rect
        area=self.mdiArea();neighbors=[w.geometry() for w in area.subWindowList() if w is not self and w.isVisible() and not w.isMinimized() and not w.isMaximized()]
        return snapped_rect(rect,area.viewport().rect(),neighbors,edges)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._press=(event.globalPosition().toPoint(),QRect(self.geometry()));self._resize_edges=self._edges(event.position().toPoint())
            self._moving=not self._resize_edges and not self.isMaximized() and not self.isMinimized() and self._title_label(event.position().toPoint())
            if self._resize_edges or self._moving:
                self.mdiArea().setActiveSubWindow(self);self.raise_();event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._press and (self._resize_edges or self._moving) and event.buttons()&Qt.MouseButton.LeftButton:
            origin,rect=self._press;delta=event.globalPosition().toPoint()-origin;left,top,right,bottom=rect.x(),rect.y(),rect.x()+rect.width(),rect.y()+rect.height()
            if self._moving:
                moved=QRect(rect);moved.moveTo(max(0,rect.x()+delta.x()),max(0,rect.y()+delta.y()))
                self.setGeometry(self._magnet(moved,(),event.modifiers()));self.host._reference_layout=False;event.accept();return
            if 'left' in self._resize_edges:left=max(0,min(left+delta.x(),right-160))
            if 'right' in self._resize_edges:right=max(left+160,right+delta.x())
            if 'top' in self._resize_edges:top=max(0,min(top+delta.y(),bottom-100))
            if 'bottom' in self._resize_edges:bottom=max(top+100,bottom+delta.y())
            self.setGeometry(self._magnet(QRect(left,top,right-left,bottom-top),self._resize_edges,event.modifiers()));self.host._reference_layout=False;event.accept();return
        edges=self._edges(event.position().toPoint())
        cursor=Qt.CursorShape.ArrowCursor
        if len(edges)==2:cursor=Qt.CursorShape.SizeFDiagCursor if set(edges) in ({'left','top'},{'right','bottom'}) else Qt.CursorShape.SizeBDiagCursor
        elif edges:cursor=Qt.CursorShape.SizeHorCursor if edges[0] in ('left','right') else Qt.CursorShape.SizeVerCursor
        super().mouseMoveEvent(event);self.setCursor(cursor)
    def mouseReleaseEvent(self,event):
        press=self._press;edges=self._resize_edges;self._press=None;self._resize_edges=();self._moving=False
        super().mouseReleaseEvent(event)
        if event.button()!=Qt.MouseButton.LeftButton or not press or self.isMaximized() or self.isMinimized() or self.geometry()==press[1]:return
        self.host._reference_layout=False
        self.setGeometry(self._magnet(self.geometry(),edges,event.modifiers()))

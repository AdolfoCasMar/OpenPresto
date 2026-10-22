import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QRect,QPoint,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from openpresto.mdi_windows import snapped_rect


class SnapGeometryTests(unittest.TestCase):
    def test_move_snaps_adjacent_edges_without_resizing(self):
        self.assertEqual(snapped_rect(QRect(30,20,200,150),QRect(0,0,900,600),[QRect(238,20,250,300)]),QRect(38,20,200,150))
    def test_only_near_and_overlapping_windows_attract(self):
        rect=QRect(30,20,200,150);self.assertEqual(snapped_rect(rect,QRect(0,0,900,600),[QRect(238,400,200,100)]),rect);self.assertEqual(snapped_rect(rect,QRect(0,0,900,600),[QRect(260,20,200,100)]),rect)
    def test_resize_keeps_opposite_edge_fixed_and_snaps_viewport(self):
        self.assertEqual(snapped_rect(QRect(30,20,202,150),QRect(0,0,900,600),[QRect(238,20,250,300)],('right',)),QRect(30,20,208,150));self.assertEqual(snapped_rect(QRect(5,20,220,150),QRect(0,0,900,600),[],('left',)),QRect(0,20,225,150))


class WorkspaceWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('WindowSnapping')
    def setUp(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        from test_treasury import budget
        self.h=PrestoWorkspace();self.h.budget=budget();self.h._reset_history();self.h.show();self.h._open_views();self.app.processEvents()
    def tearDown(self):self.h.dirty=False;self.h.close();self.app.processEvents()
    def event(self,window,kind,point,buttons):
        button=Qt.MouseButton.LeftButton if kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease) else Qt.MouseButton.NoButton
        event=QMouseEvent(kind,point,window.mapToGlobal(point),button,buttons,Qt.KeyboardModifier.NoModifier);self.app.sendEvent(window,event)
    def test_real_border_drag_resizes_below_content_hint_and_preserves_model(self):
        from openpresto.storage import dumps
        w=self.h.windows['precios'];w.setGeometry(20,20,600,260);self.h.window_snapping=False;before=dumps(self.h.budget)
        start=QPoint(w.width()-2,100);end=QPoint(start.x()-260,100);self.event(w,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton);self.event(w,QEvent.Type.MouseMove,end,Qt.MouseButton.LeftButton);self.event(w,QEvent.Type.MouseButtonRelease,QPoint(w.width()-2,100),Qt.MouseButton.NoButton)
        self.assertLess(w.width(),400);self.assertGreaterEqual(w.width(),160);self.assertFalse(self.h._reference_layout);self.assertEqual(dumps(self.h.budget),before);self.assertEqual(len(self.h._undo),0)
    def test_manual_layout_survives_section_switch_and_main_window_resize(self):
        self.h._reference_layout=False;self.h.windows['precios'].setGeometry(20,20,420,250);expected=QRect(self.h.windows['precios'].geometry());self.h.section_ui.tabs.setCurrentIndex(3);self.h.section_ui.tabs.setCurrentIndex(0);self.app.processEvents();self.assertEqual(self.h.windows['precios'].geometry(),expected);self.h.resize(1450,900);self.app.processEvents();self.assertEqual(self.h.windows['precios'].geometry(),expected)
    def test_wide_grip_receives_drag_over_content_and_shows_resize_cursor(self):
        w=self.h.windows['precios'];w.setGeometry(20,20,600,260);self.h.window_snapping=False
        grip=w._grips[3];start=QPoint(1,80)
        self.event(grip,QEvent.Type.MouseMove,start,Qt.MouseButton.NoButton)
        self.assertEqual(grip.cursor().shape(),Qt.CursorShape.SizeHorCursor)
        self.event(grip,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
        self.event(grip,QEvent.Type.MouseMove,start+QPoint(-80,0),Qt.MouseButton.LeftButton)
        self.event(grip,QEvent.Type.MouseButtonRelease,start,Qt.MouseButton.NoButton)
        self.assertEqual(w.width(),520);self.assertEqual(w.x(),20)
    def test_top_grip_resizes_instead_of_moving_title_and_hides_when_maximized(self):
        w=self.h.windows['precios'];w.setGeometry(20,30,600,260);self.h.window_snapping=False
        grip=w._grips[0];start=QPoint(80,9)
        self.event(grip,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
        self.event(grip,QEvent.Type.MouseMove,start+QPoint(0,30),Qt.MouseButton.LeftButton)
        self.event(grip,QEvent.Type.MouseButtonRelease,start,Qt.MouseButton.NoButton)
        self.assertEqual(w.geometry(),QRect(20,60,600,230))
        self.assertEqual(set(w._edges(QPoint(20,5))),{'left','top'})
        w.showMaximized();self.app.processEvents();self.assertTrue(all(g.isHidden() for g in w._grips))
        w.showNormal();self.app.processEvents();self.assertTrue(all(not g.isHidden() for g in w._grips))
    def test_border_drag_snaps_to_neighbor_on_release(self):
        self.h.window_snapping=True
        for key,window in self.h.windows.items():
            if key not in ('precios','conceptos'):window.hide()
        w=self.h.windows['precios'];neighbor=self.h.windows['conceptos'];w.setGeometry(20,30,240,200);neighbor.setGeometry(400,30,240,240);start=QPoint(w.width()-2,100)
        self.event(w,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton);self.event(w,QEvent.Type.MouseMove,start+QPoint(132,0),Qt.MouseButton.LeftButton);self.event(w,QEvent.Type.MouseButtonRelease,QPoint(w.width()-2,100),Qt.MouseButton.NoButton)
        self.assertEqual(w.x(),20);self.assertEqual(w.x()+w.width(),neighbor.x())
    def test_title_drag_snaps_without_changing_window_size(self):
        self.h.window_snapping=True
        for key,window in self.h.windows.items():
            if key not in ('precios','conceptos'):window.hide()
        w=self.h.windows['precios'];neighbor=self.h.windows['conceptos'];w.setGeometry(20,30,240,200);neighbor.setGeometry(400,30,240,240);size=w.size();start=QPoint(80,15)
        self.event(w,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton);self.event(w,QEvent.Type.MouseMove,start+QPoint(132,0),Qt.MouseButton.LeftButton)
        self.assertEqual(w.x()+w.width(),neighbor.x())
        self.event(w,QEvent.Type.MouseButtonRelease,QPoint(80,15),Qt.MouseButton.NoButton)
        self.assertEqual(w.size(),size);self.assertEqual(w.x()+w.width(),neighbor.x())
    def test_magnet_releases_when_pointer_moves_beyond_attraction_distance(self):
        self.h.window_snapping=True
        for key,window in self.h.windows.items():
            if key not in ('precios','conceptos'):window.hide()
        w=self.h.windows['precios'];self.h.windows['conceptos'].setGeometry(400,30,240,240);w.setGeometry(20,30,240,200);start=QPoint(80,15)
        self.event(w,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton);self.event(w,QEvent.Type.MouseMove,start+QPoint(132,0),Qt.MouseButton.LeftButton);self.assertEqual(w.x(),160)
        self.event(w,QEvent.Type.MouseMove,QPoint(260-w.x(),15),Qt.MouseButton.LeftButton);self.assertEqual(w.x(),180);self.event(w,QEvent.Type.MouseButtonRelease,QPoint(80,15),Qt.MouseButton.NoButton);self.assertEqual(w.x(),180)
    def test_minimum_sizes_do_not_follow_wide_form_buttons(self):
        for key in ('precios','conceptos','mediciones','texto','gestion'):
            self.h.show_panel(key);w=self.h.windows[key];w.showNormal();w.resize(240,180);self.app.processEvents();self.assertLessEqual(w.width(),240);self.assertLessEqual(w.height(),180)

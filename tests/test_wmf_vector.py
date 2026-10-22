import os,struct,unittest,tempfile,time
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from openpresto import wmf_vector,project_assets
from openpresto.budget import BudgetError
from openpresto.pzh_importer import _Reader,_import
from pzh_auxiliary_cases import fixture


def record(function,payload=b''):
    assert len(payload)%2==0
    return struct.pack('<IH',3+len(payload)//2,function)+payload


def wmf(*rows):
    body=b''.join(rows)+record(0)
    return struct.pack('<HHHIHIH',1,9,0x300,9+len(body)//2,16,100,0)+body


def own_drawing():
    return wmf(record(0x20c,struct.pack('<hh',100,100)),record(0x20b,struct.pack('<hh',0,0)),record(0x2fa,struct.pack('<HhhI',0,2,0,255)),record(0x12d,struct.pack('<H',0)),record(0x325,struct.pack('<Hhhhhhh',3,10,10,90,10,90,90)))


def vector_fixture():
    raw=fixture();reader=_Reader(raw);start=reader.tables[22][1];old_next=reader.tables[23][1];payload=b'OWNWRAP!'+own_drawing();body=struct.pack('<IIBII',17+len(payload),0,1,len(payload),len(payload))+payload;index=b'ITEM'.ljust(13,b' ')+struct.pack('<I',start);result=bytearray(raw[:start]+body+index+raw[old_next:]);delta=len(result)-len(raw);struct.pack_into('<III',result,34+22*88,1,start,start+len(body));count,begin,end=reader.tables[23];struct.pack_into('<III',result,34+23*88,count,begin+delta,end+delta);return bytes(result)


class WMFVectorTests(unittest.TestCase):
    def test_polyline_color_coordinates_and_no_external_resources(self):
        result=wmf_vector.preview(own_drawing());self.assertEqual(result['elements'],1);self.assertEqual(result['warnings'],[]);root=ET.fromstring(result['svg']);line=root.find('{http://www.w3.org/2000/svg}polyline');self.assertEqual(line.attrib['points'],'10,10 90,10 90,90');self.assertEqual(line.attrib['stroke'],'#ff0000');self.assertNotIn(b'href',result['svg'])
    def test_object_deletion_reuses_lowest_slot(self):
        rows=wmf_vector.records(own_drawing())[:-1];raw=wmf(*(record(fn,p) for fn,p in rows[:-1]),record(0x1f0,struct.pack('<H',0)),record(0x2fa,struct.pack('<HhhI',0,1,0,0xff0000)),record(0x12d,struct.pack('<H',0)),record(*rows[-1]));self.assertIn(b'stroke="#0000ff"',wmf_vector.preview(raw)['svg'])
    def test_clip_save_restore_and_polygon_fill(self):
        ext=record(0x20c,struct.pack('<hh',100,100));box=struct.pack('<hhhh',80,80,20,20);raw=wmf(ext,record(0x1e),record(0x416,box),record(0x41b,box),record(0x127,struct.pack('<h',-1)),record(0x418,box));result=wmf_vector.preview(raw);self.assertEqual(result['elements'],2);self.assertEqual(result['svg'].count(b'<clipPath'),1);self.assertIn(b'<ellipse',result['svg'])
    def test_unsupported_records_report_partial_projection(self):
        raw=wmf(record(0x20c,struct.pack('<hh',100,100)),record(0x626,struct.pack('<HH',1,0)));result=wmf_vector.preview(raw);self.assertEqual(result['elements'],0);self.assertIn('impresión',result['warnings'][0])
    def test_arc_uses_radial_endpoints_and_counterclockwise_sweep(self):
        raw=wmf(record(0x20c,struct.pack('<hh',100,100)),record(0x817,struct.pack('<hhhhhhhh',10,50,50,90,90,90,10,10)));result=wmf_vector.preview(raw);self.assertIn(b'M90,50 A40,40 0 0 0 50,10',result['svg']);self.assertEqual(result['elements'],1)
    def test_polygon_rings_keep_holes_and_trailing_pen_data_is_explicit(self):
        poly=struct.pack('<HHHhhhhhhhhhhhhhhhh',2,4,4,0,0,90,0,90,90,0,90,30,30,60,30,60,60,30,60);raw=wmf(record(0x20c,struct.pack('<hh',100,100)),record(0x2fa,struct.pack('<HhhIH',0,1,0,255,34)),record(0x12d,struct.pack('<H',0)),record(0x538,poly));result=wmf_vector.preview(raw);self.assertIn(b'fill-rule="evenodd"',result['svg']);self.assertEqual(result['svg'].count(b' Z'),2);self.assertTrue(result['warnings'])
    def test_bad_bounds_and_object_links_rejected(self):
        raw=own_drawing()
        for bad in (raw[:-1],raw+b'\0\0',raw[:18]+b'\0'*6,wmf(record(0x20c,struct.pack('<hh',0,1))),wmf(record(0x20c,struct.pack('<hh',1,1)),record(0x12d,struct.pack('<H',99)))):
            with self.assertRaises(BudgetError):wmf_vector.preview(bad)
    def test_text_xml_is_escaped_and_font_metrics_are_explicit(self):
        font=struct.pack('<hhhhhBBBBBBBB',-12,0,0,0,700,0,0,0,0,0,0,0,0)+b'Sans\0';font+=b'\0'*(len(font)%2);text=b'<own>&';payload=struct.pack('<H',len(text))+text+struct.pack('<hh',30,20);raw=wmf(record(0x20c,struct.pack('<hh',100,100)),record(0x2fb,font),record(0x12d,struct.pack('<H',0)),record(0x521,payload));result=wmf_vector.preview(raw);ET.fromstring(result['svg']);self.assertIn(b'&lt;own&gt;&amp;',result['svg']);self.assertTrue(result['warnings'])
    def test_native_source_is_unchanged_and_geometry_survives_import(self):
        b=_import(vector_fixture(),'own-vector.pzh',native_modules=True).budget;row=next(r for r in project_assets.validate(b) if r['source']['table']==22);original=project_assets.read(b,row['id'])['original'];result=wmf_vector.preview(original['export']);self.assertEqual(result['elements'],1);self.assertEqual(original['payload'],b'OWNWRAP!'+own_drawing())


class VectorPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('VectorPreview')
    def test_render_and_export_use_one_source_and_no_history_change(self):
        from openpresto.mdi_workspace import PrestoWorkspace
        from openpresto.storage import dumps
        host=PrestoWorkspace();host.budget=_import(vector_fixture(),'own-vector.pzh',native_modules=True).budget;host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3);panel=host.panels['gestion'][1].technical_documents.assets
        try:
            before=dumps(host.budget);index=next(i for i,r in enumerate(project_assets.validate(host.budget)) if r['source']['table']==22);panel.table.setCurrentCell(index,1);panel.select();end=time.monotonic()+5
            while panel.current is None and time.monotonic()<end:panel.pool.waitForDone(100);self.app.processEvents()
            self.assertIsNotNone(panel.current);self.assertIsNotNone(panel.current['image']);self.assertFalse(panel.current['image'].isNull());self.assertIn('aproximada',panel.status.text());self.assertEqual(panel.current['image'].pixelColor(600,120).red(),255);self.assertEqual(panel.current['image'].pixelColor(600,120).green(),0)
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'own.svg'
                with patch('openpresto.project_assets_panel.QFileDialog.getSaveFileName',return_value=(str(path),'')):panel.export_vector()
                self.assertEqual(path.read_bytes(),panel.current['vector']['svg']);ET.fromstring(path.read_bytes())
            self.assertEqual(dumps(host.budget),before);self.assertEqual(len(host._undo),0)
        finally:panel.pool.waitForDone(5000);self.app.processEvents();host.dirty=False;host.close()
    def test_zoom_dialog_preserves_scene_and_reports_partial_view(self):
        from openpresto.vector_preview_dialog import VectorPreviewDialog
        from PySide6.QtWidgets import QPushButton
        vector=wmf_vector.preview(own_drawing());vector['warnings']=['Own unsupported record'];dialog=VectorPreviewDialog(vector,repaired=True);dialog.show();self.app.processEvents();initial=dialog.view.transform().m11();bounds=dialog.item.boundingRect()
        try:
            dialog.findChild(QPushButton,'vector-zoom-in').click();self.assertGreater(dialog.view.transform().m11(),initial);dialog.findChild(QPushButton,'vector-zoom-out').click();self.assertAlmostEqual(dialog.view.transform().m11(),initial);self.assertEqual(dialog.item.boundingRect(),bounds);self.assertIn('Vista parcial',dialog.notice.text());self.assertIn('cierre WMF corregido',dialog.notice.text());dialog.view.zoom(1e9);self.assertLessEqual(dialog.view.transform().m11(),50.000001)
        finally:dialog.close()

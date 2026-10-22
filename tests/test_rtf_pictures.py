import struct,unittest,zlib,os,tempfile,time
from pathlib import Path
from unittest.mock import patch
from openpresto.rtf_pictures import scan,dib_bitmap,wmf_stream
from openpresto.pzh_text import rtf_plain_text
from openpresto.budget import BudgetError


def own_png():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0'))+chunk(b'IEND',b'')


def own_rtf():return br'{\rtf1 Own before {\pict\pngblip\picw1\pich1 '+own_png().hex().encode()+br'} own after}'


def picture_fixture(data=None):
    from pzh_auxiliary_cases import fixture
    from openpresto.pzh_importer import _Reader
    raw=fixture();reader=_Reader(raw);count,start,end=reader.tables[23];assert count==0
    entity=next(reader.records(10,8))[2][:13];payload=own_rtf() if data is None else data;body=struct.pack('<IIBII',17+len(payload),0,2,len(payload),len(payload))+payload;result=bytearray(raw[:start]+body+entity+struct.pack('<I',start));struct.pack_into('<III',result,34+23*88,1,start,start+len(body));return bytes(result)


class RTFPictureTests(unittest.TestCase):
    def test_hex_png_bytes_properties_and_text_are_independent(self):
        data=own_rtf();result=scan(data);self.assertEqual(result['objects'],0);self.assertEqual(len(result['pictures']),1);row=result['pictures'][0];self.assertEqual(row['data'],own_png());self.assertEqual(row['format'],'png');self.assertEqual(row['properties'],dict(picw=1,pich=1));self.assertEqual(data[row['offset']:row['end']][:6],br'{\pict');self.assertEqual(rtf_plain_text(data),'Own before  own after')
    def test_binary_payload_with_braces_and_backslashes_does_not_change_groups(self):
        payload=b'\xff\xd8\xff{}\\pict\0';data=br'{\rtf1{\pict\jpegblip\bin'+str(len(payload)).encode()+b' '+payload+b'}}';self.assertEqual(scan(data)['pictures'][0]['data'],payload)
    def test_metadata_groups_and_fallback_pictures_remain_separate(self):
        picture=br'{\pict\pngblip{\*\blipuid 0011aa} '+own_png().hex().encode()+b'}';data=br'{\rtf1{\*\shppict'+picture+br'}{\nonshppict'+picture+b'}}';result=scan(data);self.assertEqual([r['role'] for r in result['pictures']],['shppict','nonshppict']);self.assertTrue(all(r['data']==own_png() for r in result['pictures']))
    def test_ole_counts_only_objects_and_extracts_inert_preview(self):
        picture=br'{\pict\pngblip '+own_png().hex().encode()+b'}';data=br'{\rtf1{\object{\*\objdata 0011}{\result'+picture+b'}}}';result=scan(data);self.assertEqual(result['objects'],1);self.assertTrue(result['pictures'][0]['object_preview']);self.assertEqual(result['pictures'][0]['data'],own_png())
    def test_binary_in_nonpicture_destination_is_not_scanned_as_rtf(self):
        blob=br'{\pict\pngblip 0011}';data=br'{\rtf1{\*\objdata\bin'+str(len(blob)).encode()+b' '+blob+b'}}';self.assertEqual(scan(data)['pictures'],[])
    def test_signature_mismatch_is_conserved_and_identified(self):
        row=scan(br'{\rtf1{\pict\pngblip 0102}}')['pictures'][0];self.assertEqual(row['format'],'bin');self.assertEqual(row['data'],b'\x01\x02');self.assertTrue(row['warnings'])
    def test_bad_or_mixed_encodings_and_bad_structure_rejected(self):
        bad=[br'{\rtf1{\pict\pngblip f}}',br'{\rtf1{\pict 00\bin1 x}}',br'{\rtf1{\pict\bin-1 }}',br'{\rtf1{\pict\bin999 x}}',br'{\rtf1{\pict\pict{\pict 00}}}',br'{\rtf1',br'{\rtf1}}',br'{\rtf1}{\rtf1}',br'{\rtf1{\pict zz}}',br'{\rtf1{\pict\bin2147483648 }}']
        for data in bad:
            with self.subTest(data=data),self.assertRaises(BudgetError):scan(data)
    def test_picture_count_and_group_depth_are_bounded(self):
        with self.assertRaises(BudgetError):scan(br'{\rtf1'+br'{\pict 00}'*129+b'}')
        with self.assertRaises(BudgetError):scan(br'{\rtf1'+b'{'*256+b'}'*257)
    def test_dib_wrapper_preserves_pixels_and_rejects_huge_or_truncated_input(self):
        dib=struct.pack('<IiiHHIIiiII',40,1,1,1,24,0,4,0,0,0,0)+b'\0\0\xff\0';bmp=dib_bitmap(dib);self.assertEqual(bmp[14:],dib);self.assertEqual(struct.unpack_from('<I',bmp,10)[0],54)
        for bad in (dib[:-1],struct.pack('<IiiHHIIiiII',40,20000,20000,1,24,0,0,0,0,0,0),bytes(40)):
            with self.assertRaises(BudgetError):dib_bitmap(bad)
    def test_plain_and_placeable_wmf_stream_validation(self):
        from test_wmf_vector import own_drawing
        raw=own_drawing();self.assertEqual(wmf_stream(raw),raw);header=struct.pack('<IHhhhhHI',0x9ac6cdd7,0,0,0,100,100,1440,0);checksum=0
        for value in struct.unpack('<10H',header):checksum^=value
        wrapped=header+struct.pack('<H',checksum)+raw;self.assertEqual(wmf_stream(wrapped),raw)
        with self.assertRaises(BudgetError):wmf_stream(wrapped[:20]+b'\0\0'+raw)
    def test_binary_picture_survives_pzh_import_and_native_reopen(self):
        from openpresto.pzh_importer import _import
        from openpresto import project_assets
        from openpresto.storage import loads,dumps
        data=br'{\rtf1 Before {\pict\pngblip\bin'+str(len(own_png())).encode()+b' '+own_png()+br'} After}';budget=loads(dumps(_import(picture_fixture(data),'own-binary-picture.pzh',native_modules=True).budget));row=next(r for r in project_assets.validate(budget) if r['source']['table']==23);original=project_assets.read(budget,row['id'])['original'];self.assertEqual(original['payload'],data);self.assertEqual(scan(original['payload'])['pictures'][0]['data'],own_png())


class RTFPicturePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([]);cls.app.setOrganizationName('OpenPrestoTests');cls.app.setApplicationName('RTFPictures')
    def ready(self,dialog):
        end=time.monotonic()+5
        while dialog.current is None and time.monotonic()<end:dialog.pool.waitForDone(100);self.app.processEvents()
        self.assertIsNotNone(dialog.current)
    def test_png_preview_exact_original_export_and_derived_png(self):
        from openpresto.rtf_picture_dialog import RTFPictureDialog
        from PySide6.QtGui import QImage
        dialog=RTFPictureDialog(scan(own_rtf()))
        try:
            self.ready(dialog);image=dialog.current['image'];self.assertIsNotNone(image);self.assertEqual(image.pixelColor(0,0).getRgb(),(255,0,0,255))
            with tempfile.TemporaryDirectory() as folder:
                original=Path(folder)/'own.png';view=Path(folder)/'view.png'
                with patch('openpresto.rtf_picture_dialog.QFileDialog.getSaveFileName',return_value=(str(original),'')):dialog.export_original()
                self.assertEqual(original.read_bytes(),own_png())
                with patch('openpresto.rtf_picture_dialog.QFileDialog.getSaveFileName',return_value=(str(view),'')):dialog.export_view()
                self.assertEqual(QImage(str(view)).pixelColor(0,0).getRgb(),(255,0,0,255))
        finally:dialog.pool.waitForDone(5000);dialog.close()
    def test_dib_and_wmf_are_rendered_without_windows_apis(self):
        from openpresto.rtf_picture_dialog import decode_picture
        from test_wmf_vector import own_drawing
        dib=struct.pack('<IiiHHIIiiII',40,1,-1,1,24,0,4,0,0,0,0)+b'\0\0\xff\0';result=decode_picture(dict(format='dib',data=dib));self.assertIsNotNone(result['image']);self.assertEqual(result['image'].pixelColor(0,0).green(),0)
        result=decode_picture(dict(format='wmf',data=own_drawing()));self.assertIsNotNone(result['image']);self.assertEqual(result['vector']['elements'],1);self.assertIn('aproximada',result['warning']);self.assertEqual(result['image'].pixelColor(600,120).green(),0)
    def test_binary_jpeg_payload_decodes_to_expected_color(self):
        from openpresto.rtf_picture_dialog import decode_picture
        from PySide6.QtGui import QImage,QColor
        from PySide6.QtCore import QBuffer,QByteArray,QIODevice
        image=QImage(2,2,QImage.Format.Format_RGB32);image.fill(QColor(0,0,255));output=QByteArray();buffer=QBuffer(output);buffer.open(QIODevice.OpenModeFlag.WriteOnly);self.assertTrue(image.save(buffer,'JPEG'));payload=bytes(output);data=br'{\rtf1{\pict\jpegblip\bin'+str(len(payload)).encode()+b' '+payload+b'}}';picture=scan(data)['pictures'][0];self.assertEqual(picture['data'],payload);result=decode_picture(picture);self.assertIsNotNone(result['image']);self.assertGreater(result['image'].pixelColor(0,0).blue(),240);self.assertLess(result['image'].pixelColor(0,0).red(),20)
    def test_unsupported_picture_still_exports_and_stale_result_is_ignored(self):
        from openpresto.rtf_picture_dialog import RTFPictureDialog
        report=scan(own_rtf());unknown=dict(report['pictures'][0],id=2,format='emf',data=b'own-opaque-object');report['pictures'].append(unknown);dialog=RTFPictureDialog(report)
        try:
            old=dialog.generation;dialog.table.setCurrentCell(1,0);dialog.ready(old,dict(image=None,vector=None,warning='stale',size=None));self.ready(dialog);self.assertIsNone(dialog.current['image']);self.assertNotEqual(dialog.current['warning'],'stale')
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'own.emf'
                with patch('openpresto.rtf_picture_dialog.QFileDialog.getSaveFileName',return_value=(str(path),'')):dialog.export_original()
                self.assertEqual(path.read_bytes(),unknown['data'])
        finally:dialog.pool.waitForDone(5000);dialog.close()
    def test_native_source_dialog_and_text_edit_keep_picture_and_history(self):
        from openpresto.pzh_importer import _import
        from openpresto.mdi_workspace import PrestoWorkspace
        from openpresto.storage import dumps,loads
        from openpresto import project_assets
        from PySide6.QtWidgets import QDialog
        host=PrestoWorkspace();host.budget=loads(dumps(_import(picture_fixture(),'own-pictures.pzh',native_modules=True).budget));host._reset_history();host._open_views();host.section_ui.tabs.setCurrentIndex(3);panel=host.panels['gestion'][1].technical_documents.assets
        def ready_panel():
            end=time.monotonic()+5
            while panel.current is None and time.monotonic()<end:panel.pool.waitForDone(100);self.app.processEvents()
            self.assertIsNotNone(panel.current)
        try:
            index=next(i for i,r in enumerate(project_assets.validate(host.budget)) if r['source']['table']==23);panel.table.setCurrentCell(index,1);panel.select();ready_panel();self.assertEqual(panel.current['rtf_pictures']['pictures'][0]['data'],own_png());before=dumps(host.budget);identifier=panel.current['id']
            def accept(dialog):self.assertEqual(dialog.report['pictures'][0]['data'],own_png());self.ready(dialog);return QDialog.DialogCode.Accepted
            with patch('openpresto.project_assets_panel.RTFPictureDialog.exec',new=accept):panel.open_pictures()
            from PySide6.QtCore import QCoreApplication,QEvent
            from openpresto.rtf_picture_dialog import RTFPictureDialog
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.assertEqual(host.findChildren(RTFPictureDialog),[])
            self.assertEqual(dumps(host.budget),before);self.assertEqual(len(host._undo),0)
            host._execute('assets.set',asset_id=identifier,title='Edited own document',note='',text='Edited plain copy');ready_panel();self.assertEqual(panel.current['rtf_pictures']['pictures'][0]['data'],own_png());self.assertEqual(len(host._undo),1);host.undo()
        finally:panel.pool.waitForDone(5000);host.panels['gestion'][1].technical_documents.pool.waitForDone(5000);self.app.processEvents();host.dirty=False;host.close()

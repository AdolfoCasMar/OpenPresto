"""Own tiny indexed auxiliary tables; no third-party fixture content."""
import struct
from datetime import date
from openpresto.pzh_importer import _Reader,HEADER_BYTES
from test_pzh_control import control_fixture


def fixture():
    raw=control_fixture();reader=_Reader(raw);boundary=HEADER_BYTES+4+len(reader.config);out=bytearray(raw[:boundary]);replacements={}
    code=lambda text:text.encode('cp1252').ljust(13,b' ')
    for table,key,payload,kind in ((3,'ITEM',b'Own specification',1),(12,'14620',b'{\\rtf1 Own uncompressed note}',2),(20,'ITEM',b'{\\rtf1 Own associated text}',2)):
        replacements[table]=(1,struct.pack('<IIBII',17+len(payload),0,kind,len(payload),len(payload))+payload,lambda start,key=key:code(key)+struct.pack('<I',start))
    bmp=struct.pack('<2sIHHI',b'BM',58,0,0,54)+struct.pack('<IiiHHIIiiII',40,1,1,1,24,0,4,0,0,0,0)+b'\x00\x00\xff\x00'
    wmf=struct.pack('<HHHIHIH',1,9,0x300,12,0,3,0)+struct.pack('<IH',3,0);drawing=b'WRAPTEST'+wmf
    for table,payload,kind in ((21,bmp,1),(22,drawing,1)):
        replacements[table]=(1,struct.pack('<IIBII',17+len(payload),0,kind,len(payload),len(payload))+payload,lambda start:code('ITEM')+struct.pack('<I',start))
    keywords=b''
    for rid,term in enumerate(('hiddenword','secondword','HIDDENWORD')):
        body=code('ITEM')+term.encode().ljust(16,b' ');keywords+=struct.pack('<III',len(body),rid,0)+body
    replacements[9]=(3,keywords,lambda start:b'')
    serial=(date(2020,1,6)-date(1979,12,31)).days
    body=struct.pack('<H',serial)+b'\x02\x01\x03Own holiday\0\x0b'+struct.pack('<d',250)
    replacements[16]=(1,struct.pack('<II',len(body),0)+body,lambda start:struct.pack('<HI',serial,start))
    for table in range(24):
        count,start,end=reader.tables[table];count,payload,index=replacements.get(table,(count,raw[start:end],lambda start:b''));begin=len(out);out+=payload;struct.pack_into('<III',out,34+table*88,count,begin,len(out));out+=index(begin)
    return bytes(out)

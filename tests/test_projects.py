import io
import json
import unittest
import zipfile
from PIL import Image
from photo_store import PhotoRecord
from projects import read_project, write_project


class ProjectTests(unittest.TestCase):
    def fixture(self):
        data=io.BytesIO();Image.new('RGB',(300,500),'blue').save(data,'PNG')
        return PhotoRecord(data.getvalue())

    def test_roundtrip_preserves_original_bytes_order_and_edits(self):
        record=self.fixture();stream=io.BytesIO()
        write_project(stream,[(record,{'name':'Foto ç.png','edits':{'rotation':90,'mode':'cover','zoom':1.8},'manual':True,'reviewed':True})])
        stream.seek(0);loaded=read_project(stream,PhotoRecord)
        self.assertEqual(loaded[0][0].original.read_bytes(),record.original.read_bytes())
        self.assertEqual(loaded[0][1]['edits']['zoom'],1.8)
        self.assertTrue(loaded[0][1]['manual'])
        self.assertEqual(loaded[0][1]['name'],'Foto ç.png')

    def test_corrupted_original_and_unsafe_structure_rejected(self):
        record=self.fixture();stream=io.BytesIO();write_project(stream,[(record,{'name':'Foto.png'})])
        original=zipfile.ZipFile(io.BytesIO(stream.getvalue()))
        for extra,damage in [(True,False),(False,True)]:
            broken=io.BytesIO()
            with zipfile.ZipFile(broken,'w') as archive:
                for name in original.namelist():archive.writestr(name,b'bad' if damage and name.endswith('.bin') else original.read(name))
                if extra:archive.writestr('../escape.txt','bad')
            broken.seek(0)
            with self.assertRaises(ValueError):read_project(broken,PhotoRecord)

    def test_unknown_version_and_empty_file_rejected(self):
        broken=io.BytesIO()
        with zipfile.ZipFile(broken,'w') as archive:archive.writestr('project.json',json.dumps({'application':'Instante','format':99,'photos':[]}))
        broken.seek(0)
        with self.assertRaises(ValueError):read_project(broken,PhotoRecord)
        with self.assertRaises(ValueError):read_project(io.BytesIO(b'not a zip'),PhotoRecord)

import io
import json
import threading
import time
import unittest
import urllib.request
import urllib.error
import zipfile
from http.server import ThreadingHTTPServer
from PIL import Image
import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def tearDown(self):
        with app.LOCK:app.IMAGES.clear()
        app.CACHE.clear()
    def request(self,path,data={},raw=False,token=app.TOKEN,origin=None,name='Foto.jpg'):
        headers={'X-PolaroidEditor-Token':token,'Content-Type':'application/octet-stream' if raw else 'application/json','X-Filename':name}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(self.url+'/api/'+path,data=data if raw else json.dumps(data).encode(),headers=headers),timeout=30)
    def upload(self,name='Foto.jpg'):
        stream=io.BytesIO();Image.new('RGB',(700,1000),'blue').save(stream,'PNG')
        with self.request('upload',stream.getvalue(),True,name=name) as response:return json.load(response)
    def export(self,items):
        with self.request('export/start',{'items':items}) as response:job=json.load(response)['job']
        for _ in range(150):
            with self.request('export/status',{'job':job}) as response:state=json.load(response)
            if state['state']!='running':break
            time.sleep(.02)
        self.assertEqual(state['state'],'ready',state)
        with self.request('export/download',{'job':job}) as response:return response.read()
    def test_full_export_collision_names_dimensions_and_progress(self):
        photos=[self.upload() for _ in range(3)]
        data=self.export([{'id':p['id']} for p in photos])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(),['Foto-polaroid.jpg','Foto-polaroid-2.jpg','Foto-polaroid-3.jpg'])
            for name in archive.namelist():
                with Image.open(io.BytesIO(archive.read(name))) as image:
                    self.assertEqual(image.size,(1500,1063));self.assertEqual(image.info['dpi'],(300,300))
                    self.assertGreater(image.getpixel((1450,500))[0],250)
        single=self.export([{'id':photos[0]['id']}])
        self.assertEqual(Image.open(io.BytesIO(single)).size,(1500,1063))
    def test_save_reopen_and_failed_open_preserves_session(self):
        photo=self.upload();edits={'rotation':90,'mode':'cover','zoom':2}
        with self.request('project/save',{'items':[{'id':photo['id'],'edits':edits,'reviewed':True,'manual':True}]}) as response:project=response.read()
        with self.assertRaises(urllib.error.HTTPError):self.request('project/open',b'bad',True)
        self.assertIn(photo['id'],app.IMAGES)
        with self.request('project/open',project,True) as response:loaded=json.load(response)['photos']
        self.assertNotEqual(loaded[0]['id'],photo['id']);self.assertTrue(loaded[0]['manual'])
        self.assertEqual(loaded[0]['edits']['zoom'],2)
        self.assertNotIn(photo['id'],app.IMAGES)
    def test_preview_orientation_and_empty_scene_are_supported(self):
        photo=self.upload()
        with self.request('preview',{'id':photo['id']}) as response:self.assertEqual(Image.open(io.BytesIO(response.read())).size,(1000,709))
        with self.request('orientation',{'id':photo['id']}) as response:
            result=json.load(response);self.assertFalse(result['suggested']);self.assertEqual(result['rotation'],270)

    def test_previews_keep_full_originals_out_of_decoded_cache(self):
        data=io.BytesIO();Image.new('RGB',(4000,3000),(80,110,130)).save(data,'JPEG')
        with self.request('upload',data.getvalue(),True) as response:photo=json.load(response)
        for zoom in (1,2,5):
            with self.request('preview',{'id':photo['id'],'edits':{'mode':'cover','zoom':zoom}}) as response:
                self.assertEqual(Image.open(io.BytesIO(response.read())).size,(1000,709))
        self.assertTrue(app.CACHE.entries)
        self.assertFalse(any(full for _,full in app.CACHE.entries))
        result=Image.open(io.BytesIO(self.export([{'id':photo['id'],'edits':{'mode':'cover','zoom':5}}])))
        self.assertEqual(result.size,(1500,1063));self.assertEqual(result.info['dpi'],(300,300))
        self.assertTrue(any(full for _,full in app.CACHE.entries))
    def test_access_and_invalid_input(self):
        for path,data,raw,token,origin in [('heartbeat',{},False,'bad',None),('heartbeat',{},False,app.TOKEN,'https://example.com'),('upload',b'bad',True,app.TOKEN,None),('export/start',{'items':[]},False,app.TOKEN,None)]:
            with self.assertRaises(urllib.error.HTTPError) as caught:self.request(path,data,raw,token,origin)
            self.assertIn(caught.exception.code,(400,403));caught.exception.close()

    def test_clear_is_scoped_atomic_and_releases_only_requested_records(self):
        photos=[self.upload(name=f'Foto-{n}.jpg') for n in range(3)]
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('clear',{'ids':[photos[0]['id'],None]})
        caught.exception.close()
        self.assertEqual(len(app.IMAGES),3)
        with self.request('clear',{'ids':[photos[0]['id'],photos[1]['id'],photos[0]['id'],'missing']}) as response:
            self.assertEqual(json.load(response)['removed'],2)
        self.assertEqual(set(app.IMAGES),{photos[2]['id']})
        with self.request('clear',{'ids':[p['id'] for p in photos]}) as response:
            self.assertEqual(json.load(response)['removed'],1)
        self.assertFalse(app.IMAGES)

    def test_embedded_padding_survives_preview_and_jpeg_export(self):
        source=Image.new('RGB',(800,800),'white')
        from PIL import ImageDraw
        ImageDraw.Draw(source).rectangle((100,100,699,699),fill=(160,160,160))
        stream=io.BytesIO();source.save(stream,'PNG')
        with self.request('upload',stream.getvalue(),True) as response:photo=json.load(response)
        self.assertEqual(photo['content_box'],[.125,.125,.875,.875])
        item={'id':photo['id'],'edits':{'rotation':0,'brightness':.4}}
        with self.request('preview',item) as response:
            preview=Image.open(io.BytesIO(response.read()));self.assertEqual(preview.getpixel((60,350)),(255,255,255))
        image=Image.open(io.BytesIO(self.export([item])))
        self.assertGreaterEqual(min(image.getpixel((90,531))),253)
        self.assertLess(max(image.getpixel((542,531))),70)

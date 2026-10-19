"""Validate a private reference batch without storing photos in test artifacts."""
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import urllib.request
import urllib.parse
import zipfile
from PIL import Image


def run(url,folder):
    html=urllib.request.urlopen(url).read().decode()
    token=re.search('name="instante-token" content="([^"]+)',html).group(1)
    def api(path,data,raw=False,name=''):
        request=urllib.request.Request(url+'/api/'+path,data=data if raw else json.dumps(data).encode(),
          headers={'X-Instante-Token':token,'Content-Type':'application/octet-stream' if raw else 'application/json',
                   'X-Filename':urllib.parse.quote(name)})
        return urllib.request.urlopen(request,timeout=120)
    supported={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
    paths=sorted(p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in supported)
    assert paths,'A pasta não contém imagens compatíveis.'
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    items=[];suggested=0;started=time.monotonic()
    for path in paths:
        with api('upload',path.read_bytes(),True,path.name) as response:photo=json.load(response)
        with api('orientation',{'id':photo['id']}) as response:orientation=json.load(response)
        suggested+=orientation['suggested']
        items.append({'id':photo['id'],'edits':{'rotation':orientation['rotation']}})
    with api('project/save',{'items':items}) as response:project=response.read()
    with api('project/open',project,True) as response:loaded=json.load(response)['photos']
    assert len(loaded)==len(paths)
    with api('export/start',{'items':[{'id':p['id'],'edits':p['edits']} for p in loaded]}) as response:job=json.load(response)['job']
    while True:
        with api('export/status',{'job':job}) as response:state=json.load(response)
        if state['state']!='running':break
        time.sleep(.1)
    assert state['state']=='ready',state
    with api('export/download',{'job':job}) as response:archive=zipfile.ZipFile(io.BytesIO(response.read()))
    assert len(archive.namelist())==len(paths)
    for name in archive.namelist():
        with Image.open(io.BytesIO(archive.read(name))) as image:
            assert image.size==(1500,1063) and image.info['dpi']==(300,300)
            assert image.info['icc_profile']
            r,g,b=image.getpixel((1400,500));assert r>250 and g<5 and b<5
    for path,digest in hashes.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    print(json.dumps({'photos':len(paths),'exported':len(archive.namelist()),'suggestions':suggested,
                      'portable_project':'OK','originals_unchanged':True,'geometry_and_dpi':'OK',
                      'elapsed_seconds':round(time.monotonic()-started,2)}))


if __name__=='__main__':run(sys.argv[1],sys.argv[2])

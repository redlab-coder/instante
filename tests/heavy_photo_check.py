"""Synthetic 30 MP batch; never needs or captures client photographs."""
import io
import json
from pathlib import Path
import sys
import time
import zipfile
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/'tests/artifacts/heavy'
directory.mkdir(parents=True,exist_ok=True)
files=[]
for n,color in enumerate(('#315b6a','#a0b7b7','#c9906c')):
    image=Image.new('RGB',(6000,5000),color)
    ImageDraw.Draw(image).rectangle((1200,1000,4800,4000),outline='white',width=35)
    file=directory/f'Grande-{n+1}.jpg';image.save(file,'JPEG',quality=95);image.close();files.append(file)

started=time.monotonic()
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1366,'height':900},accept_downloads=True)
    page.goto(sys.argv[1]);page.wait_for_function("!document.getElementById('add').disabled")
    page.locator('#files').set_input_files([str(f) for f in files]*4)
    page.wait_for_function('photos.length===12&&!importing',timeout=180000)
    page.locator('[data-fit=cover]').click();page.locator('#zoom-number').fill('2.00');page.locator('#zoom-number').press('Enter')
    page.wait_for_timeout(500)
    # Exercise the real pointer path while measuring browser frame scheduling.
    page.evaluate('window.frameGaps=[];window.lastFrame=performance.now();window.frameRunning=true;function measure(t){frameGaps.push(t-lastFrame);lastFrame=t;if(frameRunning)requestAnimationFrame(measure)};requestAnimationFrame(measure)')
    frame=page.locator('#tile-frame').bounding_box()
    page.mouse.move(frame['x']+frame['width']/2,frame['y']+frame['height']/2)
    page.mouse.down();page.mouse.move(frame['x']+frame['width']/2+50,frame['y']+frame['height']/2+30,steps=25);page.mouse.up()
    page.wait_for_timeout(800);gaps=page.evaluate('frameRunning=false;frameGaps')
    with page.expect_download(timeout=180000) as event:page.locator('#export').click()
    target=directory/'large-export.zip';event.value.save_as(target)
    with zipfile.ZipFile(target) as archive:
        assert len(archive.namelist())==12
        for name in archive.namelist():
            with Image.open(io.BytesIO(archive.read(name))) as image:assert image.size==(1500,1063) and image.info['dpi']==(300,300)
    assert page.evaluate('photos.length')==12
    browser.close()
ordered=sorted(gaps)
print(json.dumps({'photos':12,'megapixels_each':30,'exports':12,'elapsed_seconds':round(time.monotonic()-started,2),
                  'median_frame_ms':round(ordered[len(ordered)//2],1),'p95_frame_ms':round(ordered[int(len(ordered)*.95)],1)}))

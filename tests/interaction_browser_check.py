"""Measure actual photo displacement, drag work and gradual adjustment controls."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def run(url):
    artifacts=ROOT/'tests/artifacts/interaction';artifacts.mkdir(parents=True,exist_ok=True)
    files=[]
    for width,height in ((1200,800),(6000,4000)):
        image=Image.new('RGB',(width,height),(80,110,130))
        radius=min(width,height)*.035
        ImageDraw.Draw(image).ellipse((width/2-radius,height/2-radius,width/2+radius,height/2+radius),fill=(240,20,20))
        file=artifacts/f'Landmark-{width}.png';image.save(file);image.close();files.append(file)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(json.loads(request.post_data)) if request.url.endswith('/api/preview') else None)
        page.goto(url);page.wait_for_function('editingAllowed&&!restoring')
        page.locator('#files').set_input_files([str(f) for f in files]);page.wait_for_function('photos.length===2&&!importing',timeout=60000)
        page.evaluate("""()=>{window.redCenter=()=>{const canvas=document.getElementById('tile-image'),data=canvas.getContext('2d').getImageData(59,70,945,945).data;let x=0,y=0,n=0;
          for(let row=0;row<945;row+=2)for(let col=0;col<945;col+=2){const index=(row*945+col)*4;if(data[index]>190&&data[index+1]<65&&data[index+2]<65){x+=59+col;y+=70+row;n++;}}
          return n?[x/n,y/n]:null;};}""")
        cases=0
        for viewport in (1440,375):
            page.set_viewport_size({'width':viewport,'height':1000})
            for index in range(2):
                for rotation in (0,90,180,270):
                    for mode,zoom in (('cover',1),('cover',2),('cover',4),('contain',1)):
                        page.evaluate("""async config=>{selected=photos[config.index].id;current().edits={...defaults(),rotation:config.rotation,mode:config.mode,zoom:config.zoom};revision++;renderLibrary();await sourceFor(current());drawLive();await renderEditor();}""",{'index':index,'rotation':rotation,'mode':mode,'zoom':zoom})
                        page.wait_for_function('redCenter()!==null&&displayedPhoto===selected&&!liveFrame')
                        frame=page.locator('#tile-frame').bounding_box();scale=frame['width']/1063
                        before=page.evaluate('redCenter()');start=page.evaluate('sessionRevision');count=len(requests)
                        x,y=frame['x']+frame['width']/2,frame['y']+frame['height']/2
                        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y+12,steps=12)
                        # At zoom 1, the shorter source axis has no crop travel.
                        turn=rotation%180!=0;w,h=(800,1200) if turn else (1200,800)
                        expected_x=20 if (w>h if mode=='contain' else zoom>1 or h>w) else 0
                        expected_y=12 if (h>w if mode=='contain' else zoom>1 or w>h) else 0
                        target=[before[0]+expected_x/scale,before[1]+expected_y/scale]
                        page.wait_for_function('target=>{const center=redCenter();return center&&Math.abs(center[0]-target[0])<3&&Math.abs(center[1]-target[1])<3}',arg=target)
                        assert page.evaluate('sessionRevision')==start,'Writing session storage during drag'
                        assert len(requests)==count,'Rendering server previews during pointer movement'
                        page.mouse.up();assert page.evaluate('sessionRevision')==start+1
                        cases+=1
        # Clamping the actual crop center prevents a dead zone when reversing at an edge.
        page.evaluate("()=>{current().edits={...defaults(),rotation:0,mode:'cover',zoom:2};revision++;drawLive();}")
        page.evaluate('moveBy(10000,0)')
        edge=page.evaluate('current().edits.cy');page.evaluate('moveBy(-5,0)')
        assert page.evaluate('current().edits.cy')<edge
        # A slide of 10% from neutral now changes brightness by only 1%.
        page.locator('#brightness').evaluate("el=>{el.value='10';el.dispatchEvent(new Event('input',{bubbles:true}));}")
        assert page.evaluate('current().edits.brightness')==1.01
        page.locator('#brightness').evaluate("el=>{el.value='-10';el.dispatchEvent(new Event('input',{bubbles:true}));}")
        assert page.evaluate('current().edits.brightness')==.99
        page.locator('#brightness-number').fill('0.1');page.locator('#brightness-number').press('Enter')
        assert page.evaluate('current().edits.brightness')==1.001
        page.locator('#brightness-number').fill('0.01');page.locator('#brightness-number').press('Enter')
        assert page.evaluate('current().edits.brightness')==1.0001
        page.locator('#brightness-zero').click();assert page.evaluate('current().edits.brightness')==1
        for key in ('brightness','contrast','saturation','sharpness'):
            page.locator('#'+key).evaluate("el=>{el.value='50';el.dispatchEvent(new Event('input',{bubbles:true}));}")
            assert page.evaluate(f'current().edits.{key}')==(1.5 if key=='sharpness' else 1.25)
            page.locator('#'+key+'-zero').click()
        # Existing strong values remain exact; the slider maps back to the same factor.
        page.locator('#brightness-number').fill('-60');page.locator('#brightness-number').press('Enter')
        assert page.evaluate('current().edits.brightness')==.4
        raw=page.locator('#brightness').input_value()
        assert abs(float(raw)+77.4597)<.2
        page.locator('#brightness-zero').click()
        page.wait_for_timeout(1000);requests.clear()
        page.locator('#contrast-number').fill('6.2');page.locator('#contrast-number').press('Enter')
        page.wait_for_timeout(1000)
        active=page.evaluate('selected')
        matching=[r for r in requests if r['id']==active and r['edits']['contrast']==1.062]
        assert len(matching)==1,matching
        page.locator('#clear-all').click();page.locator('#clear-confirm').click();page.wait_for_function('!photos.length&&!clearing')
        assert page.evaluate('previewCache.size')==0
        assert not errors,errors
        browser.close()
    print(json.dumps({'pointer_tracking_cases':cases,'resolution_and_zoom_independent':'OK','edge_reverse':'OK',
                      'no_storage_or_server_work_during_drag':'OK','gradual_filters':'OK','precise_values':'OK','shared_preview':'OK'}))


if __name__=='__main__':run(sys.argv[1])

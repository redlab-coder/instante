"""Review queue, F shortcut, white padding and safe clearing in the real UI."""
import hashlib
import io
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.demo_art import make_demos


def run(url):
    artifacts=ROOT/'tests/artifacts/refinement';artifacts.mkdir(parents=True,exist_ok=True)
    files=make_demos(artifacts/'demo')
    padded=artifacts/'Com preenchimento.png';image=Image.new('RGB',(800,800),'white');draw=ImageDraw.Draw(image)
    draw.rectangle((100,100,699,699),fill=(160,160,160));draw.rectangle((300,300,399,399),fill='white');image.save(padded);files.append(padded)
    hashes={f:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    metadata=artifacts/'Thumbs.db';metadata.write_bytes(b'Windows thumbnail metadata')
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.wait_for_function('editingAllowed&&!restoring')
        page.locator('#files').set_input_files([str(f) for f in files]+[str(metadata)]);page.wait_for_function('photos.length===4&&!importing',timeout=60000)
        ids=page.evaluate('photos.map(p=>p.id)')
        def ready():page.wait_for_function("!document.getElementById('review-photo').disabled")
        def select(index):page.locator(f'.photo-row[data-id="{ids[index]}"] .photo-select').click();ready()
        def confirm():ready();page.locator('#review-photo').click()
        ready();page.locator('#filter-review').click()
        confirm();assert page.evaluate('selected')==ids[1]
        ready();page.keyboard.press('f');assert page.evaluate('selected')==ids[2]
        ready();before=page.evaluate('photos.map(p=>p.reviewed)')
        page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'f',repeat:true,bubbles:true}))")
        assert page.evaluate('photos.map(p=>p.reviewed)')==before
        page.locator('#help').click();page.keyboard.press('f');assert page.evaluate('photos.map(p=>p.reviewed)')==before
        page.locator('#help-dialog [data-close-dialog]').click()
        page.locator('#brightness-number').focus();page.keyboard.press('f');assert page.evaluate('photos.map(p=>p.reviewed)')==before
        page.locator('#tile-frame').focus();page.keyboard.press('f');assert page.evaluate('selected')==ids[3]
        ready();page.keyboard.press('f');assert page.evaluate('photos.every(p=>p.reviewed)')
        assert page.locator('.review-empty').is_visible()
        assert page.evaluate('selected')==ids[3]
        page.keyboard.press('f');assert page.evaluate('!photos[3].reviewed&&selected===photos[3].id')
        # Outside the filter, F toggles without advancing. The queue wraps at its end.
        page.locator('#filter-review').click();select(1);page.keyboard.press('f');assert page.evaluate('selected')==ids[1]
        page.locator('#filter-review').click();select(3);page.keyboard.press('f');assert page.evaluate('selected')==ids[1]
        ready();page.keyboard.press('f');assert page.evaluate('photos.every(p=>p.reviewed)')
        page.locator('#filter-review').click();select(0)
        # Clicking a preview only focuses it; changing an image invalidates its review.
        page.locator('#tile-frame').click();assert page.evaluate('photos[0].reviewed')
        frame=page.locator('#tile-frame').bounding_box();page.mouse.move(frame['x']+frame['width']/2,frame['y']+frame['height']/2);page.mouse.down()
        page.keyboard.press('f');assert page.evaluate('photos[0].reviewed&&selected===photos[0].id')
        page.mouse.up()
        page.locator('#brightness-number').fill('-10');page.locator('#brightness-number').press('Enter')
        assert page.evaluate('!photos[0].reviewed')
        page.locator('#filter-review').click();page.reload()
        page.wait_for_function('editingAllowed&&!restoring&&photos.length===4');assert page.evaluate('filterReview')
        readonly=context.new_page();readonly.goto(url);readonly.wait_for_function('photos.length===4&&!restoring')
        readonly_state=readonly.evaluate('photos.map(p=>p.reviewed)');readonly.keyboard.press('f')
        assert readonly.evaluate('photos.map(p=>p.reviewed)')==readonly_state
        assert readonly.locator('#clear-all').is_disabled()
        for _ in range(3):
            readonly.locator('#takeover').click();readonly.wait_for_function('editingAllowed&&!restoring');page.wait_for_function('!editingAllowed')
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            assert not page.evaluate('editingAllowed')
            page.locator('#takeover').click();page.wait_for_function('editingAllowed&&!restoring');readonly.wait_for_function('!editingAllowed')
        readonly.close()
        page.locator('#filter-review').click()
        # A delayed photograph cannot be confirmed while the previous one is visible.
        select(0)
        page.evaluate('()=>{const id=photos[2].id;sources.get(id)?.then(b=>b.close());sources.delete(id);previewCache.delete(id)}')
        cdp=context.new_cdp_session(page);cdp.send('Network.enable')
        cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':600,'downloadThroughput':-1,'uploadThroughput':-1})
        page.locator(f'.photo-row[data-id="{ids[2]}"] .photo-select').click()
        assert page.locator('#review-photo').is_disabled()
        prior=page.evaluate('photos[2].reviewed');page.keyboard.press('f');assert page.evaluate('photos[2].reviewed')==prior
        ready();cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
        # Existing padding stays white in the fast canvas, final preview and exported JPG.
        select(3);page.locator('#rotate').click()
        page.wait_for_function('current().edits.rotation===0&&displayedPhoto===selected')
        page.route('**/api/preview',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"teste"}'))
        page.locator('#brightness-number').fill('-60');page.locator('#brightness-number').press('Enter')
        page.wait_for_function("document.getElementById('tile-image').getContext('2d').getImageData(404,670,1,1).data[0]<90")
        pixels=page.evaluate("()=>{const c=document.getElementById('tile-image').getContext('2d');return [[90,531],[670,659],[470,459],[30,531],[1400,531]].map(([x,y])=>Array.from(c.getImageData(1063-y,x,1,1).data).slice(0,3))}")
        assert pixels[0]==[255,255,255] and pixels[3]==[255,255,255] and pixels[4]==[255,0,0],pixels
        assert 58<=pixels[1][0]<=70 and 98<=pixels[2][0]<=106,pixels
        page.unroute('**/api/preview');page.evaluate('renderEditor()')
        page.wait_for_function("document.getElementById('retry-preview').hidden")
        page.evaluate('renderSheets()');page.wait_for_function("document.querySelectorAll('.sheet-open:not(:disabled)').length===4")
        page.locator('.sheet-open').last.click()
        with page.expect_download(timeout=60000) as event:page.locator('#download-sheet').click()
        export=artifacts/'padding.jpg';event.value.save_as(export)
        with Image.open(export) as result:
            assert min(result.getpixel((90,531)))>=253 and max(result.getpixel((670,659)))<70
        page.wait_for_function('!exporting');page.locator('#sheet-dialog [data-close-dialog]').click()
        assert not page.locator('#clear-all').inner_text().strip()
        # The loaded state and its confirmation dialog fit narrow windows.
        for width in (1440,1366,900,740,520,375,320):
            page.set_viewport_size({'width':width,'height':900});page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            page.locator('#clear-all').click()
            assert page.locator('#clear-dialog').is_visible()
            page.wait_for_timeout(220)
            page.screenshot(path=str(artifacts/f'clear-{width}.png'),full_page=True)
            page.locator('#clear-cancel').click();assert page.evaluate('photos.length')==4
        page.set_viewport_size({'width':1440,'height':1000})
        # A rejected clear keeps every photo, then retry clears only the session.
        with page.expect_download() as event:page.locator('#save-project').click()
        saved=artifacts/'preserved.polaroid';event.value.save_as(saved);page.wait_for_function('!exporting')
        saved_hash=hashlib.sha256(saved.read_bytes()).hexdigest()
        page.route('**/api/clear',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"teste de recuperação"}'))
        page.locator('#clear-all').click();page.locator('#clear-confirm').click();page.wait_for_function('!clearing')
        assert page.evaluate('photos.length')==4 and page.locator('#clear-dialog').is_visible()
        page.unroute('**/api/clear');page.locator('#clear-confirm').click();page.wait_for_function('photos.length===0&&!clearing')
        page.wait_for_timeout(700)
        assert page.evaluate('photos.length===0&&selected===null&&!filterReview&&sources.size===0&&sheetCache.size===0')
        assert page.locator('#clear-all').is_hidden() and page.locator('#export').is_disabled()
        assert page.locator('#retry-preview').is_hidden() and page.locator('#empty-add').evaluate('(el)=>el===document.activeElement')
        page.reload();page.wait_for_function('editingAllowed&&!restoring');assert page.evaluate('photos.length')==0
        assert hashlib.sha256(saved.read_bytes()).hexdigest()==saved_hash
        page.locator('#project-file').set_input_files(str(saved));page.wait_for_function('photos.length===4&&!importing')
        assert page.evaluate('photos[3].edits.brightness')==.4
        assert page.evaluate('photos[3].content_box')==[.125,.125,.875,.875]
        page.locator('#clear-all').click();page.locator('#clear-confirm').click();page.wait_for_function('photos.length===0&&!clearing')
        for file,digest in hashes.items():assert hashlib.sha256(file.read_bytes()).hexdigest()==digest
        assert not errors,errors
        browser.close()
    print(json.dumps({'review_advance':'OK','F_shortcut_and_guards':'OK','review_wrap_and_last_photo':'OK',
                      'preview_readiness':'OK','white_padding_live_preview_export':'OK','clear_cancel_failure_retry':'OK',
                      'clear_keeps_originals_and_saved_batch':'OK','responsive_320_to_1440':'OK'}))


if __name__=='__main__':run(sys.argv[1])

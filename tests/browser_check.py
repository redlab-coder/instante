"""End-to-end interactions against a running source or packaged instance."""
import io
import json
from pathlib import Path
import sys
import zipfile
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.demo_art import make_demos


def run(url):
    artifacts=ROOT/'tests/artifacts';artifacts.mkdir(parents=True,exist_ok=True)
    demos=make_demos(artifacts/'demo')
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();errors=[];api_errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('response',lambda r:api_errors.append(f'{r.url}: {r.status}') if '/api/' in r.url and '/preview' not in r.url and r.status>=400 else None)
        page.goto(url);page.wait_for_function("document.getElementById('add').disabled===false")
        page.locator('#files').set_input_files([str(f) for f in demos]);page.wait_for_function('photos.length===3&&!importing',timeout=60000)
        page.wait_for_function("document.querySelectorAll('.sheet-open:not(:disabled)').length===3")
        assert page.locator('#zoom').is_disabled()
        assert page.evaluate("photos[0].edits.mode")=='contain'
        page.locator('[data-fit=cover]').click();assert page.locator('#zoom').is_enabled()
        page.locator('#zoom-number').fill('1.50');page.locator('#zoom-number').press('Enter')
        page.locator('#rotate').click();assert page.evaluate('photos[0].manual&&!photos[0].reviewed')
        page.locator('[data-fit=contain]').click();assert page.evaluate('photos[0].edits.zoom')==1
        # Upright is a display transform; export edits never change on view toggle.
        edits=page.evaluate('JSON.stringify(photos[0].edits)')
        page.locator('[data-view=print]').click();page.wait_for_function("document.getElementById('tile-image').width===1500")
        assert page.evaluate('JSON.stringify(photos[0].edits)')==edits
        page.locator('[data-view=upright]').click()
        page.locator('#photo-list .photo-select').first.click();page.keyboard.press('ArrowDown');assert page.evaluate('selected===photos[1].id')
        page.locator('#invert').click()
        page.locator('#review-batch').click();assert page.locator('.batch-card').count()==3
        page.locator('.batch-card').first.click();assert not page.locator('#batch-dialog').is_visible()
        # Save includes the original files and can be reopened with exact adjustments.
        saved_edits=page.evaluate('JSON.stringify(photos.map(p=>p.edits))')
        with page.expect_download() as event:page.locator('#save-project').click()
        batch=artifacts/'roundtrip.instante';event.value.save_as(batch)
        page.wait_for_function('!exporting');page.on('dialog',lambda d:d.accept())
        page.locator('#project-file').set_input_files(str(batch));page.wait_for_function('!importing&&photos.length===3')
        assert page.evaluate('JSON.stringify(photos.map(p=>p.edits))')==saved_edits
        with page.expect_download(timeout=60000) as event:page.locator('#export').click()
        exported=artifacts/'browser-export.zip';event.value.save_as(exported)
        with zipfile.ZipFile(exported) as archive:
            assert len(archive.namelist())==3
            for name in archive.namelist():
                image=Image.open(io.BytesIO(archive.read(name)));assert image.size==(1500,1063) and image.info['dpi']==(300,300)
        page.wait_for_function('!exporting')
        # Recovery and exclusive editing across two tabs.
        page.reload();page.wait_for_function('photos.length===3&&editingAllowed&&!restoring')
        second=context.new_page();second.goto(url);second.wait_for_function('photos.length===3&&!restoring')
        assert second.locator('#add').is_disabled()
        second.locator('#takeover').click();second.wait_for_function('editingAllowed')
        page.wait_for_function('!editingAllowed');assert page.locator('#rotate').is_disabled()
        second.locator('#invert').click();new_rotation=second.evaluate('current().edits.rotation')
        second.close();page.locator('#takeover').click();page.wait_for_function('editingAllowed&&!restoring')
        assert page.evaluate('current().edits.rotation')==new_rotation
        # Simulated preview failure preserves all imported photos.
        page.route('**/api/preview',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"teste"}'))
        page.locator('#rotate').click();page.wait_for_function("!document.getElementById('retry-preview').hidden")
        assert page.evaluate('photos.length')==3
        page.unroute('**/api/preview');page.locator('#retry-preview').click()
        page.wait_for_function("document.getElementById('retry-preview').hidden")
        # Reset creates predictable, attractive public screenshots.
        for i in range(3):page.evaluate(f"selected=photos[{i}].id;photos[{i}].edits=defaults();photos[{i}].reviewed=true;")
        page.evaluate('async()=>{selected=photos[0].id;for(const p of photos)await updateThumbnail(p);renderLibrary();renderEditor();renderSheets();saveSession();}')
        page.wait_for_function("document.querySelectorAll('.sheet-open:not(:disabled)').length===3")
        page.wait_for_timeout(600)
        page.evaluate("clearTimeout(toastTimer);document.getElementById('toast').hidden=true;window.scrollTo(0,0)")
        page.screenshot(path=str(artifacts/'workspace.png'),full_page=True)
        (ROOT/'docs/images').mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(ROOT/'docs/images/workspace.png'),full_page=True)
        page.locator('.sheet-open').first.click();page.screenshot(path=str(ROOT/'docs/images/print.png'),full_page=True)
        page.locator('#sheet-dialog [data-close-dialog]').click()
        for width in (1366,900,740,520,375,320):
            page.set_viewport_size({'width':width,'height':900});page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Horizontal overflow at {width}'
            page.screenshot(path=str(artifacts/f'layout-{width}.png'),full_page=True)
        # Removal is reachable through the keyboard and keeps the rest of the batch.
        page.set_viewport_size({'width':1440,'height':1000});page.locator('.row-actions button').nth(2).focus();page.keyboard.press('Enter')
        page.wait_for_function('photos.length===2')
        assert not errors,errors
        assert not api_errors,api_errors
        browser.close()
    print(json.dumps({'browser':'OK','project_roundtrip':'OK','export':'OK','tab_recovery':'OK','exclusive_editor':'OK','preview_failure':'OK','responsive_layout':'OK','keyboard_remove':'OK'}))


if __name__=='__main__':run(sys.argv[1])

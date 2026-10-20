"""Expanded file drop area and upright-only previews against the real UI."""
import base64
import io
import json
from pathlib import Path
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        errors, uploads, choosers = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: uploads.append(request) if request.url.endswith('/api/upload') else None)
        page.on('filechooser', lambda chooser: choosers.append(chooser))
        page.goto(url)
        page.wait_for_function('editingAllowed&&!restoring')
        stream = io.BytesIO()
        Image.new('RGB', (800, 600), '#315b6a').save(stream, 'PNG')
        encoded = base64.b64encode(stream.getvalue()).decode()
        transfer = page.evaluate_handle("""encoded=>{const data=new DataTransfer();
          const bytes=Uint8Array.from(atob(encoded), c=>c.charCodeAt(0));
          for(const name of ['Foto A.png','Foto B.png'])data.items.add(new File([bytes],name,{type:'image/png'}));return data;}""", encoded)

        def event(selector, kind, data=transfer):
            page.locator(selector).dispatch_event(kind, {'dataTransfer': data})

        # Clicking blank space does not open a file picker.
        page.locator('.editor-heading').click()
        assert not choosers
        event('.library', 'dragenter')
        assert page.locator('#import-area').evaluate("el=>el.classList.contains('file-drop-active')")
        event('.editor-heading h2', 'dragenter')
        event('.library', 'dragleave')
        assert page.locator('#import-area').evaluate("el=>el.classList.contains('file-drop-active')")
        event('.editor-heading h2', 'dragleave')
        assert not page.locator('#import-area').evaluate("el=>el.classList.contains('file-drop-active')")

        # Both files import once, even though the event bubbles through nested elements.
        event('#empty-editor h3', 'dragenter')
        event('#empty-editor h3', 'drop')
        page.wait_for_function('photos.length===2&&!importing')
        assert len(uploads) == 2
        page.wait_for_function('displayedPhoto===selected')
        assert page.locator('[data-view]').count() == 0
        assert page.evaluate("document.getElementById('tile-image').width===1063&&document.getElementById('tile-image').height===1500")
        page.wait_for_function("document.querySelectorAll('.sheet-open:not(:disabled)').length===2")
        assert page.locator('.sheet-open img').first.evaluate('el=>el.naturalHeight>el.naturalWidth')
        page.locator('.sheet-open').first.click()
        page.wait_for_function("document.getElementById('sheet-dialog-image').naturalHeight>document.getElementById('sheet-dialog-image').naturalWidth")
        assert page.locator('#sheet-dialog-image').evaluate('el=>el.naturalHeight>el.naturalWidth')
        event('.library', 'drop')  # A modal prevents background imports.
        assert len(uploads) == 2
        page.locator('#sheet-dialog [data-close-dialog]').click()

        # Text/internal drags and the Adjustments panel do not import or highlight.
        text = page.evaluate_handle("()=>{const data=new DataTransfer();data.setData('text/plain','texto');return data;}")
        event('.editor', 'dragenter', text)
        event('.editor', 'drop', text)
        event('.adjustments', 'drop')
        assert len(uploads) == 2
        assert not page.locator('#import-area').evaluate("el=>el.classList.contains('file-drop-active')")
        frame = page.locator('#tile-frame').bounding_box()
        page.mouse.move(frame['x'] + frame['width']/2, frame['y'] + frame['height']/2)
        page.mouse.down()
        page.mouse.move(frame['x'] + frame['width']/2 + 25, frame['y'] + frame['height']/2, steps=8)
        page.mouse.up()
        assert len(uploads) == 2
        event('#tile-frame', 'dragenter')
        event('#tile-frame', 'drop')
        page.wait_for_function('photos.length===4&&!importing')
        assert len(uploads) == 4
        event('.library .panel-heading', 'drop')
        page.wait_for_function('photos.length===6&&!importing')
        assert len(uploads) == 6

        # A second tab cannot import; busy operations cannot accept a new drop.
        readonly = context.new_page()
        readonly.goto(url)
        readonly.wait_for_function('photos.length===6&&!restoring')
        assert readonly.locator('#add').is_disabled()
        readonly.evaluate("()=>{const data=new DataTransfer();data.items.add(new File(['bad'],'Ignore.png',{type:'image/png'}));document.querySelector('.editor').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:data}));}")
        assert readonly.evaluate('photos.length') == 6
        readonly.close()
        page.evaluate('exporting=true')
        event('.editor', 'dragenter')
        event('.editor', 'drop')
        assert len(uploads) == 6
        page.evaluate('exporting=false')

        artifacts = ROOT/'tests/artifacts/import'
        artifacts.mkdir(parents=True, exist_ok=True)
        for width in (1440, 900, 740, 520, 375, 320):
            page.set_viewport_size({'width': width, 'height': 900})
            page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
            event('.editor', 'dragenter')
            page.screenshot(path=str(artifacts/f'drop-{width}.png'), full_page=True)
            event('.editor', 'dragleave')
        page.locator('#clear-all').click()
        page.locator('#clear-confirm').click()
        page.wait_for_function('photos.length===0&&!clearing')
        assert not errors, errors
        browser.close()
    print(json.dumps({'expanded_drop': 'OK', 'single_import_per_drop': 'OK', 'pointer_drag': 'OK',
                      'drop_guards': 'OK', 'upright_previews': 'OK', 'responsive_brand': 'OK'}))


if __name__ == '__main__':
    run(sys.argv[1])

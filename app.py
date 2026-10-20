"""Loopback-only desktop application; client originals never leave the machine."""
import argparse
import io
import json
import os
import secrets
import sys
import threading
import tempfile
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
from PIL import Image, UnidentifiedImageError
from engine import render_tile, jpeg_bytes, normalized_edits, output_names, APERTURE, PAGE, PHOTO, RED_START
from desktop import SingleInstance, run_tray
from photo_store import PhotoRecord, PhotoCache
from projects import read_project, write_project, MAX_FILE, MAX_TOTAL, MAX_PHOTOS
from orientation import suggest
from updater import Updater, installed_directory
from version import VERSION, PORTABLE_NAMESPACE, INSTALLED_NAMESPACE, INSTALLED_MUTEX

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
TOKEN = secrets.token_urlsafe(24)
INSTANCE = secrets.token_hex(16)
IMAGES, JOBS = {}, {}
LOCK = threading.RLock()
CACHE = PhotoCache()
LAST_ACTIVE = time.monotonic()


def snapshot(items):
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_PHOTOS:
        raise ValueError('Selecione entre 1 e 100 fotos.')
    with LOCK:
        result = []
        for item in items:
            source = IMAGES[item['id']]
            result.append((source['record'], {'name': source['name'],
                           'edits': normalized_edits(item.get('edits')),
                           'manual': bool(item.get('manual')), 'reviewed': bool(item.get('reviewed'))}))
        return result


def start_export(records):
    with LOCK:
        for key, old in list(JOBS.items()):
            if old['state'] != 'running' and time.monotonic() - old['created'] > 3600:
                old['directory'].cleanup()
                del JOBS[key]
        if any(j['state'] == 'running' for j in JOBS.values()):
            raise ValueError('Aguarde a exportação em andamento.')
        if len(JOBS) >= 8:
            oldest = min(JOBS, key=lambda k: JOBS[k]['created'])
            JOBS.pop(oldest)['directory'].cleanup()
        job_id = secrets.token_hex(12)
        directory = tempfile.TemporaryDirectory(prefix='PolaroidEditor-export-')
        names = output_names([meta['name'] for _, meta in records])
        job = dict(state='running', done=0, total=len(records), error=None, directory=directory,
                   filename=names[0] if len(records) == 1 else 'PolaroidEditor-polaroids.zip',
                   created=time.monotonic(), path=Path(directory.name) / 'result')
        JOBS[job_id] = job
    def work():
        current_name = ''
        try:
            archive = zipfile.ZipFile(job['path'], 'w', zipfile.ZIP_STORED) if len(records) > 1 else None
            try:
                for index, (record, meta) in enumerate(records):
                    current_name = meta['name']
                    with CACHE.lock:
                        image = render_tile(CACHE.get(record, full=True), meta['edits'])
                        data = jpeg_bytes(image)
                    if archive:
                        archive.writestr(names[index], data)
                    else:
                        job['path'].write_bytes(data)
                    job['done'] = index + 1
            finally:
                if archive:
                    archive.close()
            job['state'] = 'ready'
        except Exception:
            job['error'] = f'Falha em {current_name}. Nenhum arquivo parcial foi disponibilizado; tente exportar novamente.'
            job['state'] = 'failed'
            job['path'].unlink(missing_ok=True)
    threading.Thread(target=work, daemon=True, name='PolaroidEditor-export').start()
    return job_id


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if not getattr(sys, 'frozen', False):
            super().log_message(format, *args)

    def reply(self, data, content_type='application/json', status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(data)

    def json_reply(self, value, status=200):
        self.reply(json.dumps(value, ensure_ascii=False).encode(), status=status)

    def send_file(self, stream, filename, content_type):
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(filename, safe=''))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        while chunk := stream.read(256 * 1024):
            self.wfile.write(chunk)

    def authorized_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.authorized_host():
            return self.json_reply({'error': 'Acesso inválido.'}, 403)
        path = urlparse(self.path).path
        if path == '/health':
            return self.json_reply({'product': 'Polaroid Editor', 'version': VERSION, 'instance': INSTANCE, 'pid': os.getpid()})
        if path == '/':
            html = (ROOT / 'ui/index.html').read_text(encoding='utf-8')
            html = html.replace('__TOKEN__', TOKEN).replace('__VERSION__', VERSION)
            return self.reply(html.encode(), 'text/html; charset=utf-8')
        if path in ('/app.js', '/icons.js', '/style.css'):
            return self.reply((ROOT / 'ui' / path[1:]).read_bytes(), 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
        if path == '/favicon.ico':
            from desktop import icon_image
            stream = io.BytesIO()
            icon_image().save(stream, 'ICO')
            return self.reply(stream.getvalue(), 'image/x-icon')
        return self.json_reply({'error': 'Não encontrado.'}, 404)

    def do_POST(self):
        global LAST_ACTIVE
        origin = self.headers.get('Origin')
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if not self.authorized_host() or self.headers.get('X-PolaroidEditor-Token') != TOKEN or (origin and origin != expected):
            return self.json_reply({'error': 'Acesso inválido.'}, 403)
        LAST_ACTIVE = time.monotonic()
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = MAX_TOTAL + 2 * 1024**2 if path == '/api/project/open' else MAX_FILE if path == '/api/upload' else 1024**2
            if length < 0 or length > limit:
                raise ValueError('O arquivo ou a solicitação excede o limite permitido.')
            if path == '/api/project/open':
                with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as stream:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(remaining, 256*1024))
                        if not chunk:
                            raise ValueError('O envio do lote foi interrompido.')
                        stream.write(chunk)
                        remaining -= len(chunk)
                    stream.seek(0)
                    with CACHE.lock:
                        staged = read_project(stream, PhotoRecord)
                        replacement, response = {}, []
                        for record, meta in staged:
                            id_ = secrets.token_hex(12)
                            replacement[id_] = {'record': record, 'name': meta['name']}
                            response.append(dict(id=id_, width=record.width, height=record.height,
                                                 content_box=record.content_box, **meta))
                        with LOCK:
                            IMAGES.clear()
                            IMAGES.update(replacement)
                        CACHE.clear()
                return self.json_reply({'photos': response})
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('O envio foi interrompido.')
            if path == '/api/upload':
                name = unquote(self.headers.get('X-Filename', 'Foto'))[:512]
                with CACHE.lock:
                    with LOCK:
                        if len(IMAGES) >= MAX_PHOTOS or sum(p['record'].bytes for p in IMAGES.values()) + length > MAX_TOTAL:
                            raise ValueError('O lote aceita até 100 fotos e 4 GB. Salve este lote antes de iniciar outro.')
                    record = PhotoRecord(body)
                    id_ = secrets.token_hex(12)
                    with LOCK:
                        IMAGES[id_] = {'record': record, 'name': name}
                return self.json_reply(dict(id=id_, name=name, width=record.width, height=record.height,
                                            content_box=record.content_box))
            data = json.loads(body or b'{}')
            if not isinstance(data, dict):
                raise ValueError('Solicitação inválida.')
            if path == '/api/heartbeat':
                updates = getattr(self.server, 'updater', None)
                return self.json_reply({'version': VERSION, 'update': updates.snapshot() if updates else {'state': 'disabled'}})
            if path == '/api/quit':
                self.json_reply({'ok': True})
                threading.Thread(target=getattr(self.server, 'request_shutdown', self.server.shutdown), daemon=True).start()
                return
            if path == '/api/delete':
                with LOCK:
                    removed = IMAGES.pop(data['id'], None)
                if removed:
                    CACHE.discard(removed['record'])
                return self.json_reply({'ok': True})
            if path == '/api/clear':
                ids = data.get('ids')
                if (not isinstance(ids, list) or len(ids) > MAX_PHOTOS
                        or any(not isinstance(id_, str) for id_ in ids)):
                    raise ValueError('Lista de fotos inválida.')
                with LOCK:
                    removed = [IMAGES.pop(id_) for id_ in dict.fromkeys(ids) if id_ in IMAGES]
                for photo in removed:
                    CACHE.discard(photo['record'])
                return self.json_reply({'ok': True, 'removed': len(removed)})
            if path == '/api/project/save':
                records = snapshot(data['items'])
                with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as stream:
                    write_project(stream, records)
                    self.send_file(stream, 'Meu lote.polaroid', 'application/zip')
                return
            if path == '/api/export/start':
                return self.json_reply({'job': start_export(snapshot(data['items']))})
            if path in ('/api/export/status', '/api/export/download'):
                with LOCK:
                    job = JOBS[data['job']]
                if path.endswith('/status'):
                    return self.json_reply({k: job[k] for k in ('state', 'done', 'total', 'error', 'filename')})
                if job['state'] != 'ready':
                    raise ValueError('A exportação ainda não está pronta.')
                with job['path'].open('rb') as stream:
                    self.send_file(stream, job['filename'], 'image/jpeg' if job['total'] == 1 else 'application/zip')
                return
            with LOCK:
                record = IMAGES[data['id']]['record']
            if path == '/api/source':
                return self.reply(record.live.read_bytes(), 'image/jpeg')
            if path == '/api/orientation':
                with CACHE.lock:
                    image = CACHE.get(record)
                    result = suggest(image)
                return self.json_reply(result)
            if path in ('/api/preview', '/api/thumbnail'):
                with CACHE.lock:
                    image = render_tile(CACHE.get(record, full=path == '/api/preview'), data.get('edits'))
                if path.endswith('/thumbnail'):
                    image = image.transpose(Image.Transpose.ROTATE_270)
                    image.thumbnail((128, 180), Image.Resampling.LANCZOS)
                else:
                    image.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
                stream = io.BytesIO()
                image.save(stream, 'PNG')
                return self.reply(stream.getvalue(), 'image/png')
            return self.json_reply({'error': 'Não encontrado.'}, 404)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, UnidentifiedImageError,
                OSError, Image.DecompressionBombError, zipfile.BadZipFile) as error:
            message = str(error) if isinstance(error, ValueError) else 'Não foi possível processar o arquivo ou a solicitação.'
            return self.json_reply({'error': message}, 400)
        except (BrokenPipeError, ConnectionResetError):
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--no-tray', action='store_true')
    parser.add_argument('--isolated', action='store_true', help='Instância separada apenas para testes.')
    parser.add_argument('--no-updates', action='store_true', help='Não consultar atualizações nesta execução.')
    args = parser.parse_args()
    install_dir = installed_directory() if not args.isolated else None
    instance = None if args.isolated else SingleInstance(INSTALLED_NAMESPACE if install_dir else PORTABLE_NAMESPACE, mutex_name=INSTALLED_MUTEX if install_dir else None)
    if instance and not instance.owner:
        existing = instance.existing_url()
        instance.close()
        if existing:
            if not args.no_browser:
                webbrowser.open(existing)
            if sys.stdout:
                print(existing, flush=True)
        elif sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'O Polaroid Editor já está iniciando ou encerrando. Aguarde alguns segundos e tente novamente.', 'Polaroid Editor', 0x40)
        return
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        if instance:
            instance.close()
        raise
    server.daemon_threads = True
    updates = None
    if install_dir and not args.no_updates:
        try:
            updates = Updater(install_dir)
            updates.start()
        except OSError:
            pass  # An update failure must never prevent local editing.
    server.updater = updates
    url = f'http://127.0.0.1:{server.server_port}'
    if instance:
        instance.publish(url, INSTANCE)
    stopped = threading.Event()
    shutdown_lock = threading.Lock()
    diagnostic = None
    if os.environ.get('POLAROID_EDITOR_TEST_TRACE'):
        import faulthandler
        diagnostic = open(os.environ['POLAROID_EDITOR_TEST_TRACE'], 'w')
        faulthandler.enable(file=diagnostic)
    tray = None
    def request_shutdown():
        with shutdown_lock:
            if stopped.is_set():
                return
            stopped.set()
        if diagnostic:
            faulthandler.dump_traceback_later(8, file=diagnostic)
        server.shutdown()
        if tray:
            tray.stop()
    server.request_shutdown = request_shutdown
    if sys.platform == 'win32' and not args.no_tray:
        tray = run_tray(url, request_shutdown, lambda: bool(IMAGES), updates)
    if not args.no_browser:
        webbrowser.open(url)
    if sys.stdout:
        print(url, flush=True)
    # With a tray icon, the session deliberately stays available until explicit exit.
    if not tray:
        def idle_monitor():
            while not stopped.wait(20):
                if time.monotonic() - LAST_ACTIVE > 300:
                    request_shutdown()
                    return
        threading.Thread(target=idle_monitor, daemon=True).start()
    try:
        if tray:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                tray.run()
            finally:
                request_shutdown()
                thread.join(timeout=5)
        else:
            server.serve_forever()
    finally:
        server.server_close()
        with LOCK:
            IMAGES.clear()
        CACHE.clear()
        if instance:
            instance.close()
        if updates:
            updates.install_on_exit()


if __name__ == '__main__':
    main()

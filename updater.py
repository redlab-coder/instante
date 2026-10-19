"""Public GitHub releases, verified downloads, installation on normal exit.

No GitHub credentials are shipped. Portable copies never install updates.
"""
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import urllib.request

from version import VERSION, REPOSITORY

MAX_DOWNLOAD = 150 * 1024**2
LOG = logging.getLogger('instante.updater')


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}', value):
        raise ValueError('Versão de atualização inválida.')
    return tuple(map(int, value.split('.')))


def installed_directory():
    directory = Path(sys.executable).resolve().parent
    if getattr(sys, 'frozen', False) and Path(sys.executable).name.lower() == 'instante.exe':
        marker = directory / 'installed.marker'
        if marker.is_file() and marker.read_text(encoding='utf-8').strip() == 'Instante':
            return directory
    return None


def validate_manifest(value):
    if not isinstance(value, dict):
        raise ValueError('Manifesto de atualização inválido.')
    version_tuple(value.get('version'))
    version = value['version']
    expected = f'https://github.com/{REPOSITORY}/releases/download/v{version}/Instante-Setup-{version}.exe'
    digest = value.get('sha256')
    if value.get('url') != expected or not isinstance(digest, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', digest):
        raise ValueError('Origem ou verificação da atualização inválida.')
    size = value.get('size')
    if type(size) is not int or not 0 < size <= MAX_DOWNLOAD:
        raise ValueError('Tamanho de atualização inválido.')
    return value


class Updater:
    def __init__(self, directory, root=None, current=VERSION, opener=urllib.request.urlopen):
        self.directory = Path(directory).resolve()
        self.root = Path(root or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Instante' / 'updates')
        self.root.mkdir(parents=True, exist_ok=True)
        self.current = current
        self.opener = opener
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.pending = None
        self._ui_state = {'state': 'idle', 'version': None}
        self.status = 'Atualizações automáticas ativadas'
        try:
            value = validate_manifest(json.loads((self.root / 'pending.json').read_text(encoding='utf-8')))
            if version_tuple(value['version']) > version_tuple(current) and self.valid_download(value):
                self.pending = value
                self.status = 'Atualização pronta · será instalada ao encerrar'
                self._ui_state = {'state': 'ready', 'version': value['version']}
            elif version_tuple(value['version']) <= version_tuple(current):
                self.destination(value).unlink(missing_ok=True)
                (self.root / 'pending.json').unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            pass

    def destination(self, manifest):
        # File names are derived from a validated numeric version, never from a
        # server-provided file path or a release asset's arbitrary name.
        return self.root / f"Instante-Setup-{manifest['version']}.exe"

    def snapshot(self):
        # Each transition replaces the whole value. Reading the status never
        # waits for the download lock or exposes temporary paths to the UI.
        return self._ui_state.copy()

    def valid_download(self, manifest):
        path = self.destination(manifest)
        if not path.is_file() or path.stat().st_size != manifest['size']:
            return False
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return hmac.compare_digest(digest.lower(), manifest['sha256'].lower())

    def check(self):
        if not self.lock.acquire(blocking=False):
            return
        candidate = None
        try:
            if self.stopped.is_set():
                return
            self.status = 'Verificando atualizações…'
            request = urllib.request.Request(f'https://github.com/{REPOSITORY}/releases/latest/download/update.json', headers={'User-Agent':f'Instante/{self.current}'})
            with self.opener(request, timeout=20) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError('Manifesto de atualização excede o tamanho permitido.')
                manifest = validate_manifest(json.loads(raw))
            if version_tuple(manifest['version']) <= version_tuple(self.current):
                self.pending = None
                self._ui_state = {'state': 'idle', 'version': None}
                (self.root / 'pending.json').unlink(missing_ok=True)
                self.status = 'Instante atualizado'
                return
            candidate = manifest['version']
            target = self.destination(manifest)
            if not self.valid_download(manifest):
                self.status = 'Baixando atualização em segundo plano…'
                self._ui_state = {'state': 'downloading', 'version': candidate}
                temporary = target.with_suffix('.part')
                try:
                    request = urllib.request.Request(manifest['url'], headers={'User-Agent':f'Instante/{self.current}'})
                    count, digest = 0, hashlib.sha256()
                    with self.opener(request, timeout=30) as response, temporary.open('wb') as stream:
                        while chunk := response.read(256 * 1024):
                            if self.stopped.is_set():
                                return
                            count += len(chunk)
                            if count > manifest['size']:
                                raise ValueError('Download excede o tamanho anunciado.')
                            digest.update(chunk)
                            stream.write(chunk)
                    if count != manifest['size'] or not hmac.compare_digest(digest.hexdigest(), manifest['sha256'].lower()):
                        raise ValueError('A atualização não passou na verificação de integridade.')
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            state = self.root / 'pending.tmp'
            state.write_text(json.dumps(manifest), encoding='utf-8')
            state.replace(self.root / 'pending.json')
            self.pending = manifest
            self._ui_state = {'state': 'ready', 'version': candidate}
            self.status = 'Atualização pronta · será instalada ao encerrar'
        except (OSError, ValueError, TypeError) as error:
            LOG.info('Atualização adiada: %s', type(error).__name__)
            self.status = 'Atualização pronta · será instalada ao encerrar' if self.pending else 'Sem conexão · tentaremos novamente depois'
            self._ui_state = ({'state': 'ready', 'version': self.pending['version']} if self.pending else
                              {'state': 'available', 'version': candidate} if candidate else
                              {'state': 'idle', 'version': None})
        finally:
            self.lock.release()

    def start(self):
        def watch():
            if self.stopped.wait(15):
                return
            while not self.stopped.is_set():
                self.check()
                if self.stopped.wait(6 * 60 * 60):
                    return
        threading.Thread(target=watch, daemon=True, name='Instante-updates').start()

    def check_async(self):
        threading.Thread(target=self.check, daemon=True, name='Instante-update-check').start()

    def install_on_exit(self):
        self.stopped.set()
        # Only complete, verified downloads can be applied. This method runs
        # after server/session shutdown and after releasing the application mutex.
        try:
            if not self.pending or not self.valid_download(self.pending):
                return False
            args = [str(self.destination(self.pending)), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', f'/WAITPID={os.getpid()}', f'/DIR={self.directory}', f'/LOG={self.root / "install.log"}']
            subprocess.Popen(args, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), close_fds=True)
            return True
        except OSError:
            LOG.info('Atualização será tentada no próximo encerramento.')
            return False

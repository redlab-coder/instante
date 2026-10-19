"""Build portable EXE, per-user installer, update manifest and checksums."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION, REPOSITORY


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-exe', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    if os.name != 'nt':
        raise SystemExit('Compile os binários no Windows.')
    if not args.skip_exe:
        from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
        numbers = tuple(map(int, VERSION.split('.'))) + (0,)
        info = VSVersionInfo(ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[StringFileInfo([StringTable('041604B0', [StringStruct('CompanyName', 'RedLab'), StringStruct('FileDescription', 'Instante — Estúdio de impressão'), StringStruct('FileVersion', VERSION), StringStruct('ProductName', 'Instante'), StringStruct('ProductVersion', VERSION), StringStruct('OriginalFilename', 'Instante.exe')])]), VarFileInfo([VarStruct('Translation', [1046, 1200])])])
        resource = ROOT / 'build' / 'version-info.txt'
        resource.parent.mkdir(exist_ok=True)
        resource.write_text(str(info), encoding='utf-8')
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed', '--name', 'Instante-Portable', '--icon', 'assets/instante.ico', '--version-file', str(resource), '--add-data', 'ui;ui', '--add-data', 'assets/models;assets/models', '--exclude-module', 'psutil', '--exclude-module', 'charset_normalizer', 'app.py'], check=True)
    compiler = Path(os.environ.get('ISCC', ROOT / '.tools' / 'inno' / 'ISCC.exe'))
    subprocess.run([str(compiler), f'/DAppVersion={VERSION}', 'installer/instante.iss'], check=True)
    setup = ROOT / 'dist' / f'Instante-Setup-{VERSION}.exe'
    with setup.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'version': VERSION, 'url': f'https://github.com/{REPOSITORY}/releases/download/v{VERSION}/{setup.name}', 'sha256': digest, 'size': setup.stat().st_size}
    (ROOT / 'dist' / 'update.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    checksums = []
    for path in (setup, ROOT / 'dist' / 'Instante-Portable.exe', ROOT / 'dist' / 'update.json'):
        with path.open('rb') as stream:
            checksums.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}')
    (ROOT / 'dist' / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()

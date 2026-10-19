"""Actual per-user install, single instance, deferred update and uninstall.

Uses a temporary application directory and updater state. Never replaces an
existing user's Instante installation or stops an unrelated application.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import winreg
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop import SingleInstance
from version import VERSION, INSTALLED_NAMESPACE, INSTALLED_MUTEX, REPOSITORY

for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{AAE0E3E8-B729-46AE-B534-2E04C256A5C1}_is1',0,winreg.KEY_READ|view):
            raise SystemExit('Teste cancelado: já existe uma instalação registrada do usuário.')
    except FileNotFoundError:pass
probe=SingleInstance(INSTALLED_NAMESPACE,mutex_name=INSTALLED_MUTEX)
try:
    assert probe.owner,'Já há um Instante instalado em execução. O teste não interromperá essa sessão.'
finally:probe.close()

setup=ROOT/'dist'/f'Instante-Setup-{VERSION}.exe'
flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
with tempfile.TemporaryDirectory(prefix='Instante-install-test-') as temporary:
    sandbox=Path(temporary)
    directory=sandbox/'Aplicativo Instante'
    env=dict(os.environ,LOCALAPPDATA=str(sandbox/'Local'))
    metadata=Path(env['LOCALAPPDATA'])/INSTALLED_NAMESPACE/'runtime.json'
    current=None
    def start(no_updates=True):
        args=[str(directory/'Instante.exe'),'--no-browser']
        if no_updates:args.append('--no-updates')
        process=subprocess.Popen(args,env=env,creationflags=flags)
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            try:
                state=json.loads(metadata.read_text())
                health=json.load(urllib.request.urlopen(state['url']+'/health',timeout=1))
                if state['instance']==health['instance']:
                    assert health['version']==VERSION
                    return process,state
            except (OSError,ValueError,KeyError):pass
            time.sleep(.1)
        raise AssertionError('A instalação não iniciou')
    def api(state,path,data):
        html=urllib.request.urlopen(state['url']).read().decode()
        token=re.search('name="instante-token" content="([^"]+)',html).group(1)
        headers={'X-Instante-Token':token,'Content-Type':'application/octet-stream' if isinstance(data,bytes) else 'application/json'}
        body=data if isinstance(data,bytes) else json.dumps(data).encode()
        return urllib.request.urlopen(urllib.request.Request(state['url']+'/api/'+path,data=body,headers=headers)).read()
    try:
        subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=',f'/DIR={directory}'],check=True,timeout=90,creationflags=flags)
        assert (directory/'installed.marker').read_text().strip()=='Instante'
        assert (directory/'Instante.exe').read_bytes()==(ROOT/'dist'/'Instante-Portable.exe').read_bytes()
        current,state=start()
        second=subprocess.Popen([str(directory/'Instante.exe'),'--no-browser','--no-updates'],env=env,creationflags=flags)
        assert second.wait(timeout=20)==0
        assert json.loads(metadata.read_text())['instance']==state['instance']
        api(state,'quit',{})
        assert current.wait(timeout=20)==0
        current=None
        # Simulate a verified newer queue using the genuine installer, without
        # publishing a fake version. The product must wait until normal exit.
        updates=Path(env['LOCALAPPDATA'])/'Instante'/'updates'
        updates.mkdir(parents=True,exist_ok=True)
        staged=updates/'Instante-Setup-9999.0.0.exe'
        shutil.copyfile(setup,staged)
        manifest={'version':'9999.0.0','url':f'https://github.com/{REPOSITORY}/releases/download/v9999.0.0/{staged.name}','sha256':hashlib.sha256(staged.read_bytes()).hexdigest(),'size':staged.stat().st_size}
        (updates/'pending.json').write_text(json.dumps(manifest),encoding='utf-8')
        current,state=start(no_updates=False)
        picture=io.BytesIO();Image.new('RGB',(100,100),'blue').save(picture,'PNG')
        api(state,'upload',picture.getvalue())
        assert not (updates/'install.log').exists(),'Não deve aplicar atualização durante edição'
        assert current.poll() is None
        api(state,'quit',{})
        assert current.wait(timeout=20)==0
        current=None
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            log=(updates/'install.log').read_text(encoding='utf-8-sig',errors='replace') if (updates/'install.log').exists() else ''
            if 'Installation process succeeded.' in log:
                break
            time.sleep(.2)
        else:raise AssertionError('Atualização ao encerrar falhou: '+log[-3000:])
        time.sleep(1)
        current,state=start()
        api(state,'quit',{})
        assert current.wait(timeout=20)==0
        current=None
        print(json.dumps({'installation':'OK','stable_single_instance':'OK','no_update_while_editing':'OK','actual_installer_on_normal_exit':'OK','reopen_after_update':'OK'}))
    finally:
        if current and current.poll() is None:
            try:api(state,'quit',{});current.wait(timeout=20)
            except (OSError,subprocess.TimeoutExpired):pass
        uninstaller=directory/'unins000.exe'
        if uninstaller.exists():
            subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=90,creationflags=flags)
            deadline=time.monotonic()+10
            while (directory/'Instante.exe').exists() and time.monotonic()<deadline:time.sleep(.1)
            assert not (directory/'Instante.exe').exists(),'Desinstalação não removeu o aplicativo de teste'
    print(json.dumps({'uninstall':'OK','user_installation_untouched':True}))

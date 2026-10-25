"""Local Windows launcher. The check mode never starts services or installs packages."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:5173'
MODULES = ('fastapi', 'uvicorn', 'multipart', 'pydantic', 'PIL', 'cryptography')


def requirements():
    return [name for name in MODULES if importlib.util.find_spec(name) is None]


def free_port(port):
    with socket.socket() as connection:
        try:
            connection.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def ready(url, deadline, processes):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError('A service exited. See data/launcher-logs for the error.')
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    if url.endswith('/api/health'):
                        body=json.load(response)
                        if body.get('app') != 'MHP' or body.get('status') != 'ok':
                            raise RuntimeError('The backend health check did not identify MHP.')
                    return
        except (OSError, ValueError):
            pass
        time.sleep(.5)
    raise RuntimeError('Startup timed out. See data/launcher-logs.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args=parser.parse_args()
    node=shutil.which('node.exe') or shutil.which('node')
    vite=ROOT/'frontend/node_modules/vite/bin/vite.js'
    missing=requirements()
    if args.check:
        result={'python':sys.version.split()[0], 'python_modules_missing':missing,
                'node_found':bool(node), 'vite_present':vite.is_file(),
                'backend_entry_present':(ROOT/'app/main.py').is_file(),
                'ports_free':{str(port):free_port(port) for port in (8000,5173)}}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if not missing and node and vite.is_file() else 1
    if sys.version_info < (3,12):
        raise RuntimeError('Python 3.12 or newer is required.')
    # Recreate a separate environment when a moved .venv can no longer be used.
    if Path(sys.prefix).resolve() not in ((ROOT/'.venv').resolve(), (ROOT/'.mhp-runtime').resolve()):
        runtime=ROOT/'.mhp-runtime'
        python=runtime/'Scripts/python.exe'
        if not python.is_file():
            subprocess.run([sys.executable,'-m','venv',str(runtime)],check=True)
        return subprocess.call([str(python),'-B',str(Path(__file__).resolve())])
    if missing:
        print('Preparing Python dependencies. The first launch needs internet access.',flush=True)
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-cloud.lock')],check=True)
    if not node:
        raise RuntimeError('Node.js is missing. Install Node.js 22 LTS or newer and run this launcher again.')
    if not vite.is_file():
        npm=shutil.which('npm.cmd')
        npm_cli=Path(npm).parent/'node_modules/npm/bin/npm-cli.js' if npm else None
        if not npm_cli or not npm_cli.is_file():
            raise RuntimeError('npm is missing. Reinstall Node.js with npm.')
        print('Preparing frontend dependencies. The first launch needs internet access.',flush=True)
        subprocess.run([node,str(npm_cli),'ci'],cwd=ROOT/'frontend',check=True)
    for port in (8000,5173):
        if not free_port(port):
            raise RuntimeError(f'Port {port} is in use. Close the previous local MHP service before retrying.')
    if not (ROOT/'.env').exists():
        (ROOT/'.env').write_text('AUTH_COOKIE_SECURE=0\nAUTH_EMAIL_PROVIDER=netease_smtp\n',encoding='utf-8')
    logs=ROOT/'data/launcher-logs'
    logs.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update(AUTH_COOKIE_SECURE='0',VITE_API_BASE='http://127.0.0.1:8000',PYTHONUTF8='1')
    env['AUTH_ALLOWED_ORIGINS']=','.join(filter(None,[env.get('AUTH_ALLOWED_ORIGINS',''),'http://127.0.0.1:5173','http://localhost:5173']))
    processes=[]
    streams=[]
    try:
        for name,command,cwd in (
            ('backend',[sys.executable,'-B','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--workers','1'],ROOT),
            ('frontend',[node,str(vite),'--host','127.0.0.1','--port','5173','--strictPort'],ROOT/'frontend'),
        ):
            stream=(logs/(name+'.log')).open('ab')
            streams.append(stream)
            process=subprocess.Popen(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            processes.append(process)
        print('Starting local MHP. Please wait...',flush=True)
        deadline=time.monotonic()+120
        ready('http://127.0.0.1:8000/api/health',deadline,processes)
        ready(URL,deadline,processes)
        webbrowser.open(URL)
        print('Local MHP: '+URL+'\nOnline MHP: https://118.178.92.58\nKeep this window open while using local MHP.',flush=True)
        input('Press ENTER here to stop the local frontend and backend.\n')
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
        for stream in streams:stream.close()


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as exc:
        print('MHP startup stopped: '+str(exc),file=sys.stderr)
        raise SystemExit(1)

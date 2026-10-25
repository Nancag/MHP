"""Build a Windows x64 WebView2 beta using the installed .NET compiler; no secrets."""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(__file__).resolve().parent
RUN=ROOT/'data/windows-client'
TOOLS=RUN/'tools'
OUTPUT=RUN/'release'
CSC=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
DEPS=json.loads((SOURCE/'dependencies.json').read_text(encoding='utf-8'))
VERSION=re.search(r'Current\s*=\s*"(\d+\.\d+\.\d+)"',(SOURCE/'ClientVersion.cs').read_text()).group(1)
FILES=('MHP.exe','MHP.exe.config','Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll',
       'WebView2Loader.dll','mhp.ico','README.txt','WebView2-LICENSE.txt','MicrosoftEdgeWebview2Setup.exe')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_dependencies():
    for entry in DEPS.values():
        path=TOOLS/entry['file']
        if not path.is_file() or digest(path)!=entry['sha256']:
            raise ValueError('Dependency missing or checksum mismatch: '+entry['file'])
    script="$s=Get-AuthenticodeSignature -LiteralPath '"+str(TOOLS/DEPS['runtime_bootstrapper']['file'])+"'; if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation,'){exit 1}"
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    environment=os.environ.copy()
    environment.pop('PSModulePath',None)
    shell=shutil.which('pwsh') or shutil.which('powershell.exe')
    result=subprocess.run([shell,'-NoProfile','-EncodedCommand',encoded],check=False,capture_output=True,env=environment)
    if result.returncode:raise ValueError('Microsoft runtime bootstrapper signature check failed: '+result.stderr.decode(errors='replace')[-1500:])


def extract_tools():
    with zipfile.ZipFile(TOOLS/DEPS['nsis']['file']) as archive:
        for entry in archive.infolist():
            target=(TOOLS/entry.filename).resolve()
            if not target.is_relative_to(TOOLS.resolve()):raise ValueError('Unsafe archive path')
        archive.extractall(TOOLS)


def prepare(folder):
    from PIL import Image,ImageOps
    folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(TOOLS/DEPS['webview2']['file']) as archive:
        for name in ('Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll'):
            (folder/name).write_bytes(archive.read('lib/net462/'+name))
        (folder/'WebView2Loader.dll').write_bytes(archive.read('runtimes/win-x64/native/WebView2Loader.dll'))
        (folder/'WebView2-LICENSE.txt').write_bytes(archive.read('LICENSE.txt'))
    with Image.open(ROOT/'frontend/src/assets/icons/icon-brand.png') as original:
        image=ImageOps.pad(original.convert('RGBA'),(256,256),color=(0,0,0,0))
        image.save(folder/'mhp.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)],bitmap_format='bmp')
    shutil.copyfile(SOURCE/'MHP.exe.config',folder/'MHP.exe.config')
    shutil.copyfile(TOOLS/DEPS['runtime_bootstrapper']['file'],folder/'MicrosoftEdgeWebview2Setup.exe')
    shutil.copyfile(SOURCE/'README.txt',folder/'README.txt')
    ElementTree.parse(SOURCE/'app.manifest');ElementTree.parse(SOURCE/'MHP.exe.config')


def bundle_frontend(folder):
    environment=os.environ.copy()
    environment.pop('VITE_API_BASE',None)
    environment['VITE_API_BASE']=''
    subprocess.run([shutil.which('npm.cmd') or 'npm','run','build'],cwd=ROOT/'frontend',env=environment,check=True)
    dist=ROOT/'frontend/dist'
    files=[dist/'index.html']+[p for p in (dist/'assets').rglob('*') if p.is_file()]
    allowed={'.html','.js','.css','.png','.jpg','.jpeg','.webp','.svg','.woff','.woff2','.ttf','.ico'}
    for path in files:
        if path.is_symlink() or path.suffix.lower() not in allowed or not path.resolve().is_relative_to(dist.resolve()):
            raise ValueError('Unexpected frontend resource: '+path.name)
    with zipfile.ZipFile(folder/'frontend.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):archive.write(path,path.relative_to(dist).as_posix())
    return {'mode':'bundled-in-executable','sha256':digest(folder/'frontend.zip'),
            'files':{p.relative_to(dist).as_posix():digest(p) for p in files}}


def compile_client(folder,qa=False):
    from release_signing import prepare_key
    prepare_key()
    name='MHP-QA.exe' if qa else 'MHP.exe'
    command=[str(CSC),'/nologo','/target:winexe','/platform:x64','/optimize+','/codepage:65001',
        '/win32manifest:'+str(SOURCE/'app.manifest'),'/win32icon:'+str(folder/'mhp.ico'),
        '/out:'+str(folder/name),'/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
        '/resource:'+str(folder/'frontend.zip')+',MHP.Frontend.zip',
        '/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',
        '/reference:System.Core.dll','/reference:System.Net.Http.dll','/reference:System.Web.Extensions.dll','/reference:'+str(folder/'Microsoft.Web.WebView2.Core.dll'),
        '/reference:'+str(folder/'Microsoft.Web.WebView2.WinForms.dll')]
    if qa:command.append('/define:QA')
    command.append(str(SOURCE/'MhpClient.cs'))
    command.extend([str(SOURCE/'UpdateClient.cs'),str(SOURCE/'UpdateKey.cs')])
    command.extend([str(SOURCE/'ClientVersion.cs'),str(SOURCE/'BundledFrontend.cs')])
    subprocess.run(command,cwd=folder,check=True)
    if qa:shutil.copyfile(SOURCE/'MHP.exe.config',folder/'MHP-QA.exe.config')
    return folder/name


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--qa',action='store_true');args=parser.parse_args()
    checked_dependencies()
    folder=RUN/('qa-app' if args.qa else 'app')
    prepare(folder)
    frontend=bundle_frontend(folder)
    app=compile_client(folder,args.qa)
    # Compilation validates both source and API bindings before running any client code.
    subprocess.run([str(app),'--check-runtime'],check=True)
    subprocess.run([str(app),'--verify-bundle'],check=True)
    if args.qa:
        print(json.dumps({'qa_client':str(app),'compiled':True,'runtime_available':True}));return
    extract_tools();OUTPUT.mkdir(parents=True,exist_ok=True)
    previous=OUTPUT/'build-manifest.json'
    if previous.exists():
        old=json.loads(previous.read_text())['version']
        if old!=VERSION and re.fullmatch(r'\d+\.\d+\.\d+',old):
            backup=RUN/'archive'/old;backup.mkdir(parents=True,exist_ok=True)
            for name in ['build-manifest.json','SHA256SUMS','client-release.json','README.txt']:
                if (OUTPUT/name).exists() and not (backup/name).exists():shutil.copy2(OUTPUT/name,backup/name)
    installer=RUN/'installer-utf8.nsi'
    installer.write_text((SOURCE/'installer.nsi').read_text(encoding='utf-8'),encoding='utf-8-sig')
    subprocess.run([str(TOOLS/'nsis-3.12/makensis.exe'),'/V2','/DVERSION='+VERSION,'/DVERSIONQUAD='+VERSION+'.0','/DSOURCE='+str(folder),'/DOUTPUT='+str(OUTPUT),str(installer)],check=True)
    package=OUTPUT/f'MHP-Setup-{VERSION}-x64.exe'
    portable=OUTPUT/f'MHP-{VERSION}-x64-portable.zip'
    with zipfile.ZipFile(portable,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:archive.write(folder/name,'MHP/'+name)
    manifest={'version':VERSION,'server':'https://118.178.92.58/','architecture':'x64','signed':False,'frontend':frontend,
              'files':{name:digest(folder/name) for name in FILES},'dependencies':DEPS,
              'packages':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in (package,portable)}}
    (OUTPUT/'build-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (OUTPUT/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in (package,portable)),encoding='ascii')
    shutil.copyfile(SOURCE/'README.txt',OUTPUT/'README.txt')
    from release_signing import sign
    release=sign({'version':VERSION,'url':'/downloads/windows/'+package.name,'sha256':digest(package),'size_bytes':package.stat().st_size,
        'notes':VERSION+'：前端界面内置到 Windows 程序，本机加载页面和资源；登录、历史和 AI 生成继续使用原云端服务。保留账户资料，安装前需确认。'})
    (OUTPUT/'client-release.json').write_text(json.dumps(release),encoding='utf-8')
    subprocess.run([str(app),'--verify-update',str(OUTPUT/'client-release.json')],check=True)
    print(json.dumps({'installer':str(package),'bytes':package.stat().st_size,'signed':False,'server':manifest['server']}))


if __name__=='__main__':main()

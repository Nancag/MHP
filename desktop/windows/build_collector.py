"""Compile the offline, unprivileged Edge extension helper; never launch its UI."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'extensions/mhp-collector'
NAMES = ('manifest.json', 'popup.html', 'popup.css', 'popup.js', 'extractor.js', 'bridge.js', 'background.js', 'README.md')
CSC = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')


def build():
    work = ROOT / 'work/mkhp-plugin-upgrade-20261025/build'
    work.mkdir(parents=True, exist_ok=True)
    payload = work / 'collector.zip'
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in NAMES:
            entry = zipfile.ZipInfo(name, (2026, 10, 25, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (PLUGIN / name).read_bytes())
    output = PLUGIN / 'MHP-Collector-Setup.exe'
    subprocess.run([str(CSC), '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+', '/codepage:65001',
                    '/out:' + str(output), '/resource:' + str(payload) + ',MHP.Collector.zip',
                    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
                    '/reference:System.IO.Compression.dll', '/reference:System.Core.dll',
                    str(ROOT / 'desktop/windows/CollectorSetup.cs')], check=True)
    report = {'version': json.loads((PLUGIN / 'manifest.json').read_text(encoding='utf-8'))['version'],
              'exe_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'files': {name: hashlib.sha256((PLUGIN / name).read_bytes()).hexdigest() for name in NAMES},
              'signed': False}
    (PLUGIN / 'installer-build.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), **report}, indent=2))


if __name__ == '__main__':
    build()

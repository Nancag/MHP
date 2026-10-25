"""Offline inventory: metadata only for private files; no app.main import."""
import argparse,ast,json,os,sqlite3,sys,tarfile,tempfile
from collections import defaultdict
from pathlib import Path
from contextlib import closing

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/audit-20261025'
def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--verify-package',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    groups=defaultdict(lambda:{'files':0,'bytes':0});entries=[];errors=[];links=[]
    for folder,dirs,files in os.walk(ROOT,followlinks=False):
        for name in list(dirs):
            path=Path(folder)/name
            if path.is_symlink() or path.is_junction():
                links.append(str(path.relative_to(ROOT)));dirs.remove(name)
        for name in files:
            path=Path(folder)/name
            if path.is_symlink():links.append(str(path.relative_to(ROOT)));continue
            try:
                rel=path.relative_to(ROOT).as_posix();size=path.stat().st_size
                group=rel.split('/')[0] if '/' in rel else '(root)'
                groups[group]['files']+=1;groups[group]['bytes']+=size
                entries.append({'path':rel,'bytes':size})
            except OSError:errors.append(str(path.relative_to(ROOT)))
    syntax=[]
    for folder in ('app','deploy','launcher','desktop/windows','tests'):
        for path in (ROOT/folder).rglob('*.py'):
            try:ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
            except (SyntaxError,UnicodeError) as exc:syntax.append({'path':str(path.relative_to(ROOT)),'error_type':type(exc).__name__})
    with closing(sqlite3.connect((ROOT/'data/mhp.db').as_uri()+'?mode=ro',uri=True)) as db:
        integrity=[row[0] for row in db.execute('PRAGMA quick_check')]
    report={'groups':dict(groups),'files':len(entries),'scan_errors':errors,'skipped_links':links,'syntax_errors':syntax,'database_quick_check':integrity}
    if args.verify_package:
        from deploy import build_bundle
        with tempfile.TemporaryDirectory(prefix='mhp-package-audit-',dir=OUT) as directory:
            build_bundle.OUTPUT=Path(directory)
            build_bundle.run()
            with tarfile.open(Path(directory)/'mhp-cloud-code.tar.gz') as archive:
                names=set(archive.getnames())
                required={'deploy/publish_downloads.py','deploy/backup_worker.py','deploy/Dockerfile.api','deploy/preflight.py','extensions/mhp-collector/manifest.json','extensions/mhp-collector/bridge.js','extensions/mhp-collector/background.js'}
                assert required<=names,'Required deploy files missing'
                assert not any(name.startswith('tests/') for name in names),'Tests unexpectedly packaged'
                assert not any(Path(name).name=='.env' or Path(name).suffix in ('.db','.pem','.key') for name in names),'Private file packaged'
            report['package_required_files']='ok'
            report['package_tests_or_private_data_included']=False
    (OUT/'inventory.json').write_text(json.dumps({'summary':report,'entries':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':run()

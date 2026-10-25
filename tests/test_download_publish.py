import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'deploy/publish_downloads.py'
spec = importlib.util.spec_from_file_location('download_publish', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DownloadPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.bundle = Path(self.temp.name) / 'bundle'
        self.root.mkdir()
        self.bundle.mkdir()
        (self.root / 'compose.json').write_text('{}')
        (self.root / 'frontend/dist').mkdir(parents=True)
        self.index = b'<html><body><div id="app"></div></body></html>'
        (self.root / 'frontend/dist/index.html').write_bytes(self.index)
        (self.root / 'data').mkdir()
        (self.root / 'data/mhp.db').write_bytes(b'unchanged database')
        names = ['download.html', 'download-entry.js', 'download-entry.css', 'downloads/windows/README.txt',
                 'downloads/windows/SHA256SUMS', 'downloads/windows/MHP-Setup-0.1.0-x64.exe',
                 'downloads/windows/MHP-0.1.0-x64-portable.zip']
        self.files = {name: name.encode() for name in names}
        for name, data in self.files.items():
            path = self.bundle / 'public' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.records = {'version': '0.1.0', 'files': {name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()}}
        (self.bundle / 'release.json').write_text(json.dumps(self.records))
        self.remote = {'index.html': self.index, 'download.html': b'previous download page'}
        self.commands = []
        self.fail_hash_once = False

    def fake_run(self, args, allow_missing=False):
        self.commands.append(args)
        if args[1] == 'compose':
            data, code = b'a' * 64, 0
        elif args[1] == 'cp':
            if args[2].startswith('a' * 64 + ':'):
                name = args[2].split('/srv/mhp/')[1]
                Path(args[3]).write_bytes(self.remote[name])
            else:
                self.remote[args[3].split('/srv/mhp/')[1]] = Path(args[2]).read_bytes()
            data, code = b'', 0
        elif args[3] == 'cat':
            data, code = self.remote['index.html'], 0
        elif args[3] == 'test':
            data, code = b'', 0 if args[4] == '!' or args[-1].split('/srv/mhp/')[1] in self.remote else 1
        elif args[3] == 'sha256sum':
            name = args[-1].split('/srv/mhp/')[1]
            data, code = (hashlib.sha256(self.remote[name]).hexdigest() + '  file').encode(), 0
            if self.fail_hash_once:
                self.fail_hash_once = False
                data = b'bad  file'
        elif args[3] == 'rm':
            self.remote.pop(args[-1].split('/srv/mhp/')[1], None)
            data, code = b'', 0
        elif args[3] == 'mkdir':
            data, code = b'', 0
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, stdout=data, stderr=b'')

    def invoke(self, *arguments):
        with patch.object(module, '__file__', str(self.bundle / 'publish_downloads.py')), \
             patch.object(module, 'os', types.SimpleNamespace(name='posix', geteuid=lambda: 0)), \
             patch.object(module, 'run', self.fake_run), \
             patch('sys.argv', ['publish_downloads.py', '--root', str(self.root), *arguments]), \
             contextlib.redirect_stdout(io.StringIO()):
            module.main()

    def test_publish_preserves_application_and_database(self):
        self.invoke()
        self.assertEqual(self.remote['download.html'], self.files['download.html'])
        self.assertIn(b'MHP_DOWNLOAD_ENTRY_START', self.remote['index.html'])
        self.assertEqual((self.root / 'data/mhp.db').read_bytes(), b'unchanged database')
        self.assertFalse(any('restart' in command or 'up' in command for command in self.commands))
        for name, data in self.files.items():
            self.assertEqual((self.root / 'frontend/public' / name).read_bytes(), data)
        self.invoke()
        self.assertEqual(self.remote['index.html'].count(b'MHP_DOWNLOAD_ENTRY_START'), 1)

    def test_preflight_does_not_publish(self):
        before = self.remote.copy()
        self.invoke('--check')
        self.assertEqual(self.remote, before)
        self.assertFalse((self.root / 'data/backups').exists())

    def test_checksum_failure_rolls_back_new_and_previous_files(self):
        before = self.remote.copy()
        self.fail_hash_once = True
        with self.assertRaisesRegex(ValueError, 'Published checksum'):
            self.invoke()
        self.assertEqual(self.remote, before)
        self.assertEqual((self.root / 'frontend/dist/index.html').read_bytes(), self.index)
        self.assertFalse((self.root / 'frontend/dist/download.html').exists())

    def test_invalid_source_is_rejected_before_backup(self):
        (self.bundle / 'public/download.html').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.invoke()
        self.assertFalse((self.root / 'data/backups').exists())

    def test_cloud_host_mismatch_does_not_publish(self):
        self.remote['index.html'] = b'other cloud version'
        with self.assertRaisesRegex(ValueError, 'differ'):
            self.invoke()
        self.assertFalse((self.root / 'data/backups').exists())


if __name__ == '__main__':
    unittest.main()

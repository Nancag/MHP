import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from app.services import curl_transport as transport


class CurlTransportTests(unittest.TestCase):
    def request(self,url='https://api.openai-next.com/v1/messages',key='offline-key-only-in-stdin'):
        return urllib.request.Request(url,data=b'{"messages":[]}',headers={'x-api-key':key,'Content-Type':'application/json'})

    def test_secret_only_in_stdin_and_default_dual_stack(self):
        captured={}
        def execute(command,configuration,timeout,limit):
            config=configuration.decode();captured.update(command=command,config=config)
            self.assertNotIn('offline-key-only-in-stdin',' '.join(command))
            self.assertIn('header = "X-api-key: offline-key-only-in-stdin"',config)
            self.assertNotIn('ipv4',config);self.assertNotIn('ipv6',config)
            self.assertNotIn('insecure',config);self.assertNotIn('location',config)
            self.assertIn('retry = 0',config);self.assertIn('noproxy = "*"',config)
            path=config.split('data-binary = "@')[1].split('"')[0]
            captured['path']=Path(path)
            self.assertEqual(captured['path'].read_bytes(),b'{"messages":[]}')
            self.assertNotIn(b'offline-key-only-in-stdin',captured['path'].read_bytes())
            return b'{"ok":true}'+transport.MARKER+b'200'
        with patch.object(transport,'executable',return_value='trusted-curl'),patch.object(transport,'_execute',side_effect=execute) as run:
            with transport.build_opener(limit=300000).open(self.request()) as result:self.assertEqual(result.read(),b'{"ok":true}')
        run.assert_called_once();self.assertFalse(captured['path'].exists())
        self.assertEqual(captured['command'],['trusted-curl','--disable','--config','-'])

    def test_http_failures_and_redirects_do_not_repeat(self):
        for status in (302,403,500):
            with patch.object(transport,'executable',return_value='curl'),patch.object(transport,'_execute',return_value=b'{}'+transport.MARKER+str(status).encode()) as run:
                with self.assertRaises(urllib.error.HTTPError) as caught:transport.build_opener(limit=300).open(self.request())
                self.assertEqual(caught.exception.code,status);run.assert_called_once()

    def test_endpoint_header_missing_binary_and_response_guards(self):
        with patch.object(transport,'_execute') as run:
            with self.assertRaises(transport.TransportError):transport.build_opener(limit=300).open(self.request('https://untrusted.example/messages'))
            with patch.object(transport,'executable',return_value=None),self.assertRaises(transport.TransportError):transport.build_opener(limit=300).open(self.request())
            with patch.object(transport,'executable',return_value='curl'),self.assertRaises(transport.TransportError):transport.build_opener(limit=300).open(self.request(key='header\r\ninjection'))
            run.assert_not_called()
        for response in (b'bad-status',b'xxxxxxxxxxx'+transport.MARKER+b'200'):
            with patch.object(transport,'executable',return_value='curl'),patch.object(transport,'_execute',return_value=response),self.assertRaises(transport.TransportError):
                transport.build_opener(limit=10).open(self.request())

    def test_payload_temp_file_is_removed_on_transport_failure(self):
        paths=[]
        def fail(command,configuration,*args):
            paths.append(Path(configuration.decode().split('data-binary = "@')[1].split('"')[0]))
            raise transport.TransportError('offline failure')
        with patch.object(transport,'executable',return_value='curl'),patch.object(transport,'_execute',side_effect=fail),self.assertRaises(transport.TransportError):
            transport.build_opener(limit=100).open(self.request())
        self.assertFalse(paths[0].exists())

    def test_binary_multipart_is_not_reencoded(self):
        request=self.request('https://api.openai-next.com/v1/images/edits')
        request.data=b'--boundary\r\nPNG\x00\xff\x80\r\n--boundary--'
        def execute(command,configuration,*args):
            path=Path(configuration.decode().split('data-binary = "@')[1].split('"')[0])
            self.assertEqual(path.read_bytes(),request.data)
            return b'{}'+transport.MARKER+b'200'
        with patch.object(transport,'executable',return_value='curl'),patch.object(transport,'_execute',side_effect=execute):
            transport.build_opener(limit=100).open(request).close()

    def test_real_subprocess_buffers_are_bounded_without_network(self):
        command=[sys.executable,'-c','import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"ok")']
        self.assertEqual(transport._execute(command,b'offline',2,100),b'ok')
        command=[sys.executable,'-c','import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"x"*200000)']
        with self.assertRaises(transport.TransportError):transport._execute(command,b'offline',2,100)

    def test_child_environment_excludes_backend_keys_and_stderr_is_not_exposed(self):
        command=[sys.executable,'-c','import sys,os;sys.stdin.buffer.read();sys.stdout.write(str("MHP_TEXT_API_KEY" in os.environ));sys.stderr.write("never expose upstream secret");sys.exit(7)']
        with patch.dict(os.environ,{'MHP_TEXT_API_KEY':'offline-env-secret'}),self.assertRaises(transport.TransportError) as error:
            transport._execute(command,b'offline',2,100)
        self.assertIn('7',str(error.exception));self.assertNotIn('secret',str(error.exception))
        command=[sys.executable,'-c','import sys,os;sys.stdin.buffer.read();sys.stdout.write(str("MHP_TEXT_API_KEY" in os.environ))']
        with patch.dict(os.environ,{'MHP_TEXT_API_KEY':'offline-env-secret'}):self.assertEqual(transport._execute(command,b'offline',2,100),b'False')

    def test_config_quote_preserves_literal_backslashes_quotes_and_newlines(self):
        self.assertEqual(transport._quote('a"b\\c\nd'),'"a\\"b\\\\c\\nd"')

import asyncio
import json
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from app.services import auth_service as service

class Client:
    def __init__(self, app):
        self.app, self.cookie, self.headers = app, '', []

    def call(self, method, path, data=None, origin='http://127.0.0.1:5173'):
        async def run():
            messages = []
            parsed = urlsplit(path)
            body = json.dumps(data).encode() if data is not None else b''
            headers = [(b'content-type', b'application/json')]
            if origin:
                headers.append((b'origin', origin.encode()))
            if self.cookie:
                headers.append((b'cookie', self.cookie.encode()))

            async def receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}

            async def send(message):
                messages.append(message)

            await self.app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version':'2.4'}, 'http_version': '1.1',
                'method': method, 'scheme': 'http', 'path': parsed.path, 'raw_path': parsed.path.encode(),
                'query_string': parsed.query.encode(), 'root_path': '', 'headers': headers,
                'client': ('127.0.0.1', 1234), 'server': ('test', 80)}, receive, send)
            self.headers = messages[0]['headers']
            for key, value in self.headers:
                if key == b'set-cookie':
                    jar = SimpleCookie(); jar.load(value.decode())
                    morsel = jar[service.COOKIE_NAME]
                    self.cookie = f'{service.COOKIE_NAME}={morsel.value}' if morsel.value else ''
            raw = b''.join(message.get('body', b'') for message in messages[1:])
            content_type = next((v for k,v in self.headers if k == b'content-type'), b'')
            return messages[0]['status'], (json.loads(raw) if b'application/json' in content_type else raw) if raw else None
        return asyncio.run(run())

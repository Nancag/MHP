"""Direct ASGI test requests; no sockets, httpx dependency, or application lifespan.

Used only with fixture apps that mount routers and initialize their own temporary DB.
Like support_client.Client, this executes real routing, validation, and responses.
"""
import asyncio
import json as jsonlib
from urllib.parse import urlencode,urlsplit


class Response:
    def __init__(self,status,content,headers):
        self.status_code,self.content=status,content
        self.headers={k.decode():v.decode() for k,v in headers}
        self.text=content.decode('utf-8',errors='replace')

    def json(self):
        return jsonlib.loads(self.content)


class TestClient:
    def __init__(self,app):self.app=app
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def close(self):pass

    def request(self,method,path,*,json=None,data=None,files=None):
        if files:
            boundary='mhp-offline-fixture-boundary'
            parts=[]
            for name,value in (data or {}).items():
                parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
            for name,(filename,content,kind) in files.items():
                parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {kind}\r\n\r\n').encode()+content+b'\r\n')
            parts.append(f'--{boundary}--\r\n'.encode())
            body=b''.join(parts)
            content_type='multipart/form-data; boundary='+boundary
        elif json is not None:
            body=jsonlib.dumps(json).encode();content_type='application/json'
        else:
            body=urlencode(data or {}).encode();content_type='application/x-www-form-urlencoded'
        parsed=urlsplit(path)

        async def run():
            messages=[]
            async def receive():return {'type':'http.request','body':body,'more_body':False}
            async def send(message):messages.append(message)
            scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
                'method':method,'scheme':'http','path':parsed.path,'raw_path':parsed.path.encode(),
                'query_string':parsed.query.encode(),'root_path':'',
                'headers':[(b'host',b'testserver'),(b'content-type',content_type.encode()),(b'content-length',str(len(body)).encode())],
                'client':('127.0.0.1',1234),'server':('testserver',80)}
            await asyncio.wait_for(self.app(scope,receive,send),timeout=30)
            start=next(m for m in messages if m['type']=='http.response.start')
            return Response(start['status'],b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'),start['headers'])
        return asyncio.run(run())

    def get(self,path,**kwargs):return self.request('GET',path,**kwargs)
    def post(self,path,**kwargs):return self.request('POST',path,**kwargs)
    def put(self,path,**kwargs):return self.request('PUT',path,**kwargs)
    def delete(self,path,**kwargs):return self.request('DELETE',path,**kwargs)

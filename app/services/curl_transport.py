"""Backend-only curl transport. Default dual stack, one POST, no redirects/retry."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import urllib.error

ENDPOINTS={'https://api.openai-next.com/v1/messages',
           'https://api.openai-next.com/v1/images/edits'}
MARKER=b'\nMHP_CURL_STATUS:'


class TransportError(Exception):
    """Public-safe message only; never include request/config/stderr."""


def executable():
    if os.name=='nt':
        path=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/curl.exe'
        return str(path) if path.is_file() else None
    return shutil.which('curl')


def available():return executable() is not None


def _quote(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('\r','\\r').replace('\n','\\n')+'"'


def _execute(command,configuration,timeout,limit):
    # Only bounded response buffers remain in memory. The key is never an argument.
    chunks=[];size=0;overflow=threading.Event()
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('MHP_') or key in ('SMTP_AUTH_CODE','RESEND_API_KEY','AUTH_SECRET'):
            env.pop(key,None)
    try:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except OSError:
        raise TransportError('无法启动后端curl，请检查系统依赖') from None
    def output():
        nonlocal size
        try:
            while True:
                part=process.stdout.read(65536)
                if not part:break
                size+=len(part)
                if size>limit+len(MARKER)+3:
                    overflow.set()
                    try:process.kill()
                    except OSError:pass
                    break
                chunks.append(part)
        except OSError:pass
    def discard_errors():
        # curl error output is never logged: it can include upstream details.
        try:
            while process.stderr.read(4096):pass
        except OSError:pass
    readers=[threading.Thread(target=output,daemon=True),threading.Thread(target=discard_errors,daemon=True)]
    for thread in readers:thread.start()
    try:
        try:
            process.stdin.write(configuration);process.stdin.close()
        except (BrokenPipeError,OSError):pass
        try:code=process.wait(timeout=timeout+10)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)
            raise TransportError('后端curl请求超时；上游可能已计费，未自动重试') from None
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        if not process.stdin.closed:process.stdin.close()
        for thread in readers:thread.join(timeout=5)
        process.stdout.close();process.stderr.close()
    if overflow.is_set():raise TransportError('后端curl响应超过大小上限；未自动重试')
    if any(thread.is_alive() for thread in readers):raise TransportError('后端curl响应读取未结束；未自动重试')
    if code!=0:raise TransportError(f'后端curl连接或传输失败（退出码{code}）；上游可能已计费，未自动重试')
    return b''.join(chunks)


class CurlOpener:
    def __init__(self,limit):self.limit=limit

    def open(self,request,timeout=60):
        if request.full_url not in ENDPOINTS or request.get_method()!='POST':
            raise TransportError('curl仅允许已授权的模型POST接口')
        binary=executable()
        if not binary:raise TransportError('后端缺少curl运行依赖')
        if not isinstance(request.data,bytes) or len(request.data)>64*1024*1024:
            raise TransportError('模型请求内容无效或过大')
        allowed={'x-api-key','anthropic-version','authorization','content-type','accept'}
        headers=[]
        for name,value in request.header_items():
            if name.lower() not in allowed or any(c in value for c in '\r\n\x00') or len(value)>8192:
                raise TransportError('模型请求头无效')
            headers.append('header = '+_quote(name+': '+value))
        # Payload contains product data only. Secret headers exist only in stdin.
        with tempfile.TemporaryDirectory(prefix='mhp-model-') as directory:
            body=Path(directory)/'body.bin';body.write_bytes(request.data)
            options=['url = '+_quote(request.full_url),'request = "POST"',*headers,
                     'data-binary = '+_quote('@'+body.as_posix()),'silent','show-error',
                     'noproxy = "*"','proto = "=https"','retry = 0','max-redirs = 0',
                     'connect-timeout = 20','max-time = '+str(timeout),
                     'max-filesize = '+str(self.limit),
                     'write-out = '+_quote(MARKER.decode()+'%{http_code}')]
            # No -4/-6: retain curl default dual stack selected by the user.
            configuration=('\n'.join(options)+'\n').encode('utf-8')
            raw=_execute([binary,'--disable','--config','-'],configuration,timeout,self.limit)
        data,separator,status=raw.rpartition(MARKER)
        if not separator or len(status)!=3 or not status.isdigit():
            raise TransportError('curl未返回有效HTTP状态；未自动重试')
        if len(data)>self.limit:raise TransportError('后端curl响应超过大小上限；未自动重试')
        code=int(status)
        if code<200 or code>=300:
            raise urllib.error.HTTPError(request.full_url,code,'模型接口请求未成功',{},io.BytesIO(data))
        return io.BytesIO(data)


def build_opener(*,limit):return CurlOpener(limit)

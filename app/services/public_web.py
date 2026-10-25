"""Bounded public HTTP fetches; pin validated DNS addresses for every redirect.

No cookies, credentials, ambient proxy, browser execution or private IP access.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, quote


def normalize_url(value):
    if len(value) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('网址过长或包含无效字符')
    parts = urlsplit(value.strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('仅支持不含账号密码的 HTTP / HTTPS 商品网址')
    try:
        host = parts.hostname.encode('idna').decode('ascii')
        port = parts.port
    except (ValueError, UnicodeError):
        raise ValueError('网址主机或端口无效') from None
    if port not in (None, 80 if parts.scheme == 'http' else 443):
        raise ValueError('仅支持标准网页端口')
    if host.lower() == 'localhost' or host.lower().endswith(('.localhost', '.local', '.internal')):
        raise ValueError('不允许访问本机或内网网址')
    netloc = f'[{host}]' if ':' in host else host
    return urlunsplit((parts.scheme, netloc, parts.path or '/', parts.query, ''))


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection(self.address, self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_public(url, *, limit, deadline=None):
    deadline = deadline or time.monotonic() + 25
    current = normalize_url(url)
    for _ in range(6):
        if time.monotonic() >= deadline:
            raise ValueError('网页读取超时')
        p = urlsplit(current)
        port = 443 if p.scheme == 'https' else 80
        resolved = socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
        addresses = [ipaddress.ip_address(r[4][0]) for r in resolved]
        if not addresses or any(not a.is_global or a.is_multicast or a.is_reserved for a in addresses):
            raise ValueError('网址解析到非公网地址，已拒绝访问')
        address = (resolved[0][4][0], port)
        timeout = max(.1, min(12, deadline - time.monotonic()))
        if p.scheme == 'https':
            con = _PinnedHTTPS(p.hostname, address, timeout)
        else:
            con = http.client.HTTPConnection(address[0], port, timeout=timeout)
        try:
            path = quote(p.path or '/', safe="/%:@!$&'()*+,;=-._~")
            if p.query:
                path += '?' + quote(p.query, safe="%=&/?@:!$'()*+,;~-._")
            con.request('GET', path, headers={'Host': p.netloc, 'User-Agent': 'MHP/1.0 ProductReader',
                                            'Accept-Encoding': 'identity', 'Accept': '*/*'})
            response = con.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    raise ValueError('网页重定向缺少地址')
                current = normalize_url(urljoin(current, location))
                continue
            if response.status != 200:
                raise ValueError(f'网站返回 HTTP {response.status}，可能需要登录或限制自动访问')
            if response.getheader('Content-Encoding', 'identity').lower() not in ('identity', ''):
                raise ValueError('网页压缩格式不受支持')
            size = response.getheader('Content-Length')
            if size and (not size.isdigit() or int(size) > limit):
                raise ValueError('网页或图片超过读取上限')
            chunks, total = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError('读取超时')
                chunk = response.read(min(65536, limit + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError('网页或图片超过读取上限')
                chunks.append(chunk)
            return b''.join(chunks), response.getheader('Content-Type', ''), current
        finally:
            con.close()
    raise ValueError('网页重定向次数过多')

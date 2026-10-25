"""Address fallback only before application bytes; no request or mail retries."""
import http.client
import smtplib
import socket
import ssl
import time
import urllib.request


def connect_tls(host,port,timeout,context,source_address=None):
    """Try resolved addresses under a shared connection budget, retaining SNI."""
    timeout=float(timeout) if isinstance(timeout,(int,float)) else 20.0
    if timeout<=0:raise TimeoutError('TLS connection timeout must be positive')
    addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    deadline=time.monotonic()+min(timeout,20.0)
    seen=set();last=None
    for family,kind,proto,_,address in addresses:
        if family not in (socket.AF_INET,socket.AF_INET6) or (family,address) in seen:continue
        seen.add((family,address))
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        raw=None;secure=None
        try:
            raw=socket.socket(family,kind,proto)
            raw.settimeout(min(5.0,remaining))
            if source_address:raw.bind(source_address)
            raw.connect(address)
            raw.settimeout(min(5.0,max(.001,deadline-time.monotonic())))
            secure=context.wrap_socket(raw,server_hostname=host)
            secure.settimeout(timeout)
            return secure
        except ssl.SSLCertVerificationError:
            # Certificate rejection is not treated as a route failure.
            if secure is not None:secure.close()
            if raw is not None:raw.close()
            raise
        except OSError as error:
            last=error
            if secure is not None:secure.close()
            if raw is not None:raw.close()
    if last is not None:raise last
    raise TimeoutError('No reachable TLS address within connection budget')


class HTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        if self._tunnel_host:raise OSError('Proxy tunnels are not configured for this transport')
        self.sock=connect_tls(self.host,self.port,self.timeout,self._context,self.source_address)


class HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self,req):
        return self.do_open(HTTPSConnection,req,context=self._context)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


class SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self,host,port,timeout):
        return connect_tls(host,port,timeout,self.context,self.source_address)

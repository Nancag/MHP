"""Run integration tests with temporary fixtures and external networking blocked."""
import ipaddress
import os
from pathlib import Path
import socket
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

def main():
    os.chdir(ROOT)
    sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
    for key in list(os.environ):
        if key.startswith(('MHP_TEXT_','MHP_IMAGE_','SMTP_','RESEND_','ALIPAY_')):
            del os.environ[key]
    os.environ.update(AUTH_EMAIL_PROVIDER='disabled',MEMBERSHIP_REMINDERS_ENABLED='0',ALIPAY_ENABLED='0')
    original_connect=socket.socket.connect

    def offline_connect(sock,address):
        if isinstance(address,tuple) and ipaddress.ip_address(address[0]).is_loopback:
            return original_connect(sock,address)
        raise RuntimeError('Outbound network forbidden during offline verification')

    socket.socket.connect=offline_connect
    try:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        socket.socket.connect=original_connect
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':sys.exit(main())

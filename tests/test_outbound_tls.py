import socket,ssl,unittest
from unittest.mock import Mock,patch
from app.services import outbound_tls as transport


class OutboundTests(unittest.TestCase):
    addresses=[(socket.AF_INET6,socket.SOCK_STREAM,6,'',('::1',443,0,0)),
               (socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]

    def test_fallback_occurs_before_application_bytes_and_keeps_sni(self):
        first,second,secured=Mock(),Mock(),Mock()
        context=Mock();context.wrap_socket.side_effect=[ConnectionResetError('route'),secured]
        with patch.object(transport.socket,'getaddrinfo',return_value=self.addresses),patch.object(transport.socket,'socket',side_effect=[first,second]):
            self.assertIs(transport.connect_tls('example.com',443,15,context),secured)
        first.close.assert_called_once();second.connect.assert_called_once_with(('127.0.0.1',443))
        self.assertEqual([c.kwargs['server_hostname'] for c in context.wrap_socket.call_args_list],['example.com','example.com'])
        first.sendall.assert_not_called();second.sendall.assert_not_called();secured.sendall.assert_not_called()
        secured.settimeout.assert_called_once_with(15.0)

    def test_certificate_failure_never_falls_back(self):
        context=Mock();context.wrap_socket.side_effect=ssl.SSLCertVerificationError('certificate rejected')
        raw=Mock()
        with patch.object(transport.socket,'getaddrinfo',return_value=self.addresses),patch.object(transport.socket,'socket',return_value=raw) as factory:
            with self.assertRaises(ssl.SSLCertVerificationError):transport.connect_tls('example.com',443,15,context)
        self.assertEqual(factory.call_count,1);raw.close.assert_called_once()

    def test_timeout_budget_stops_address_loop(self):
        with patch.object(transport.socket,'getaddrinfo',return_value=self.addresses),patch.object(transport.time,'monotonic',side_effect=[0,21]),patch.object(transport.socket,'socket') as factory:
            with self.assertRaises(TimeoutError):transport.connect_tls('example.com',443,15,Mock())
        factory.assert_not_called()

    def test_http_send_failure_does_not_reconnect_or_repeat_request(self):
        sock=Mock();sock.sendall.side_effect=ConnectionResetError('after request starts')
        with patch.object(transport,'connect_tls',return_value=sock) as connect:
            connection=transport.HTTPSConnection('example.com',timeout=15)
            with self.assertRaises(ConnectionResetError):connection.request('POST','/messages',body=b'test')
        connect.assert_called_once();sock.sendall.assert_called_once()

    def test_smtp_uses_same_verified_tls_before_login(self):
        connection=transport.SMTP_SSL(context=ssl.create_default_context())
        with patch.object(transport,'connect_tls',return_value=Mock()) as connect:
            connection._get_socket('smtp.example.com',465,15)
        args=connect.call_args.args
        self.assertEqual(args[:3],('smtp.example.com',465,15))
        self.assertTrue(args[3].check_hostname);self.assertEqual(args[3].verify_mode,ssl.CERT_REQUIRED)

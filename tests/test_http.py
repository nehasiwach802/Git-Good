import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from reasoning.server import Handler


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def call(self, method, path, body=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body, {'Content-Type':'application/json'})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_health(self):
        self.assertEqual(self.call('GET','/health'),(200,{'status':'ok'}))

    def test_diagnose_fixture(self):
        code, result = self.call('POST','/v1/diagnose',Path('examples/rc.json').read_bytes())
        self.assertEqual(code,200)
        self.assertEqual(result['status'],'evaluated')

    def test_invalid_and_not_found(self):
        self.assertEqual(self.call('POST','/v1/diagnose','{')[0],400)
        self.assertEqual(self.call('POST','/v1/diagnose','[]')[0],400)
        self.assertEqual(self.call('POST','/unknown','{}')[0],404)

    def test_body_limit(self):
        # Send only headers: rejected uploads need not race a Windows socket
        # reset caused by a server closing with unread oversized body bytes.
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.putrequest('POST','/v1/diagnose')
            conn.putheader('Content-Length','262145')
            conn.endheaders()
            response = conn.getresponse()
            self.assertEqual(response.status,413)
            response.read()
        finally:
            conn.close()

    def test_path_error_and_strict_json(self):
        code, body = self.call('POST','/v1/diagnose','{}')
        self.assertEqual(code,400)
        self.assertEqual(body['path'],'$.schema_version')
        for payload in ('{"schema_version":"1.0","schema_version":"1.0"}', '{"x":NaN}'):
            self.assertEqual(self.call('POST','/v1/diagnose',payload)[0],400)

"""Software tests only: no physical ESP32 is involved."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).with_name('bridge.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
JOB = {'id':'12345678-1234-1234-1234-123456789abc', 'choice':2}

class FakeSerial:
    is_open = True
    writes = 0
    def write(self, data):
        self.writes += 1
        self.id = data.decode().split()[1]
    def flush(self): pass
    def readline(self, limit): return f'APPLIED {self.id}\n'.encode()
    def close(self): self.is_open = False

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.controller = bridge.Controller(str(Path(self.tmp.name)/'jobs.db'), 'unused', 'a'*64)
    def tearDown(self): self.tmp.cleanup()

    def test_validation(self):
        for value in ({'id':'x','choice':0}, {**JOB,'choice':True}, {**JOB,'choice':4}, {**JOB,'extra':'x'}):
            with self.assertRaises(ValueError): bridge.validate(value)
        bridge.validate(JOB)

    def test_durable_duplicate_and_conflict(self):
        device = FakeSerial()
        self.controller.serial = device
        with patch.dict('sys.modules', {'serial':object()}):
            self.assertEqual(self.controller.apply(JOB)['state'], 'applied')
            self.assertEqual(self.controller.apply(JOB)['state'], 'applied')
        self.assertEqual(device.writes, 1)
        reopened = bridge.Controller(self.controller.db, 'unused', 'a'*64)
        self.assertEqual(reopened.apply(JOB)['state'], 'applied')
        with self.assertRaises(ValueError): reopened.apply({**JOB,'choice':1})

    def test_unknown_blocks_new_round(self):
        with patch.dict('sys.modules', {'serial':object()}):
            with self.assertRaises(Exception): self.controller.apply(JOB)
        other = {**JOB, 'id':'aaaaaaaa-1234-1234-1234-123456789abc'}
        with self.assertRaises(ValueError): self.controller.apply(other)
        self.controller.serial = FakeSerial()
        with patch.dict('sys.modules', {'serial':object()}):
            self.assertEqual(self.controller.apply(JOB)['state'], 'applied')

    def test_http_auth_origin_and_private_files(self):
        server = ThreadingHTTPServer(('127.0.0.1',0), bridge.handler_class(self.controller,'b'*64,'placeholder'))
        origin = f'http://127.0.0.1:{server.server_port}'
        server.RequestHandlerClass = bridge.handler_class(self.controller,'b'*64,origin)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            def get(path, headers=None):
                return urllib.request.urlopen(urllib.request.Request(origin+path,headers=headers or {}))
            with self.assertRaises(urllib.error.HTTPError) as error: get('/api/health')
            self.assertEqual(error.exception.code,401)
            headers={'Authorization':'Bearer '+'b'*64}
            self.assertEqual(json.load(get('/api/health',headers))['hardware'],'not-checked')
            with self.assertRaises(urllib.error.HTTPError) as error: get('/api/health',{**headers,'Origin':'https://evil.example'})
            self.assertEqual(error.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as error: get('/control/bridge.py')
            self.assertEqual(error.exception.code,404)
            self.assertIn(b'SILENT BREACH', get('/feira/').read())
        finally: server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()

"""Local HTTPS PWA + authenticated USB serial control. Never run on public hosting."""
import argparse
from contextlib import closing
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def validate(data):
    if not isinstance(data, dict) or set(data) != {'id', 'choice'}:
        raise ValueError('Formato inválido.')
    if not isinstance(data['id'], str) or not ID.fullmatch(data['id']):
        raise ValueError('Identificador inválido.')
    if type(data['choice']) is not int or not 0 <= data['choice'] < 4:
        raise ValueError('Escolha inválida.')

class Controller:
    def __init__(self, db, port, key):
        self.db, self.port, self.key = db, port, key
        self.serial = None
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, choice INTEGER, state TEXT)')

    def apply(self, data):
        validate(data)
        with LOCK, closing(sqlite3.connect(self.db)) as conn, conn:
            row = conn.execute('SELECT choice,state FROM jobs WHERE id=?', (data['id'],)).fetchone()
            if row and row[0] != data['choice']:
                raise ValueError('Identificador já associado a outra escolha.')
            if row and row[1] == 'applied':
                return {'id':data['id'], 'state':'applied'}
            unresolved = conn.execute("SELECT id FROM jobs WHERE state='uncertain' AND id<>?", (data['id'],)).fetchone()
            if unresolved:
                raise ValueError('Resolva a escolha anterior no tablet antes de iniciar outra rodada.')
            conn.execute("INSERT OR IGNORE INTO jobs VALUES (?,?,'uncertain')", (data['id'], data['choice']))
            conn.commit() # Persist before touching hardware: timeout never means not applied.
            try:
                import serial
                if self.serial is None or not self.serial.is_open:
                    self.serial = serial.Serial()
                    self.serial.port = self.port
                    self.serial.baudrate = 115200
                    self.serial.timeout = 0.2
                    self.serial.dtr = False
                    self.serial.rts = False
                    self.serial.open()
                    time.sleep(2)
                command = f"SET {data['id']} {data['choice']} {self.key}\n"
                self.serial.write(command.encode('ascii'))
                self.serial.flush()
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    line = self.serial.readline(256).decode('ascii', errors='ignore').strip()
                    if line == f"APPLIED {data['id']}":
                        conn.execute("UPDATE jobs SET state='applied' WHERE id=?", (data['id'],))
                        conn.commit()
                        return {'id':data['id'], 'state':'applied'}
                    if line.startswith(f"ERROR {data['id']} "):
                        raise RuntimeError('Placa recusou ou falhou. Estado ainda não confirmado.')
                raise TimeoutError('Sem confirmação da placa. Verifique a mesma escolha novamente.')
            except Exception:
                if self.serial:
                    self.serial.close()
                    self.serial = None
                raise

def handler_class(controller, token, origin):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / 'feira'), **kwargs)

        def log_message(self, *args):
            pass # Do not log credentials or audience choices.

        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            super().end_headers()

        def reply(self, status, data):
            payload = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self):
            if self.headers.get('Host') != origin.split('://', 1)[1]:
                self.reply(403, {'error':'Host inválido.'})
                return False
            if self.headers.get('Origin') not in (None, origin):
                self.reply(403, {'error':'Origem recusada.'})
                return False
            supplied = self.headers.get('Authorization', '')
            if not hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode()):
                self.reply(401, {'error':'Código recusado.'})
                return False
            return True

        def do_GET(self):
            if self.path == '/api/health':
                if self.authorized():
                    self.reply(200, {'bridge':'ready', 'hardware':'not-checked'})
                return
            if self.path.startswith('/api/'):
                self.reply(404, {'error':'Rota inexistente.'}); return
            # Serve only public PWA assets, never secrets, firmware or database.
            if self.path in ('/', '/feira', '/feira/'):
                self.path = '/index.html'
            elif self.path.startswith('/feira/'):
                self.path = self.path[len('/feira'):]
            if self.path not in {'/index.html','/app.js','/app.css','/sw.js','/manifest.webmanifest','/icon.svg','/icon-192.png','/icon-512.png'}:
                self.send_error(404); return
            super().do_GET()

        def do_POST(self):
            if self.path != '/api/select':
                self.reply(404, {'error':'Rota inexistente.'}); return
            if not self.authorized(): return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 512 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Corpo inválido.')
                data = json.loads(self.rfile.read(length))
                result = controller.apply(data)
                self.reply(200, result)
            except (ValueError, json.JSONDecodeError) as error:
                self.reply(409, {'error':str(error)})
            except Exception:
                self.reply(503, {'error':'Sem confirmação de aplicação. Confira USB, alimentação e firmware; verifique a mesma escolha novamente.'})
    return Handler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='COM5 or /dev/ttyUSB0')
    parser.add_argument('--cert', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--origin', required=True, help='Exact tablet origin, e.g. https://192.168.1.20:8443')
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--listen', type=int, default=8443)
    parser.add_argument('--db', default=str(Path.home() / '.scct-jobs.sqlite3'))
    args = parser.parse_args()
    token, device_key = os.environ.get('SCCT_TOKEN', ''), os.environ.get('SCCT_DEVICE_KEY', '')
    if any(not re.fullmatch(r'[0-9a-f]{64}', key) for key in (token, device_key)):
        parser.error('SCCT_TOKEN e SCCT_DEVICE_KEY devem conter 64 caracteres hexadecimais aleatórios, distintos.')
    if token == device_key:
        parser.error('Use chaves diferentes para navegador e USB.')
    if not args.origin.startswith('https://') or args.origin.endswith('/'):
        parser.error('Origin deve ser HTTPS sem barra final.')
    controller = Controller(args.db, args.port, device_key)
    server = ThreadingHTTPServer((args.bind, args.listen), handler_class(controller, token, args.origin))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print('Ponte iniciada. Abra ' + args.origin + '/feira/ no tablet. Hardware ainda não verificado.')
    server.serve_forever()

if __name__ == '__main__':
    main()

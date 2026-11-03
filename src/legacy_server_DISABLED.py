"""Local-only fictional-data prototype; NOT a production or client-data service."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import uuid
from .engine import Engine, ValidationError, ConflictError, NotFoundError

ROOT=Path(__file__).resolve().parent
class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,engine):
        super().__init__(address,Handler)
        self.engine=engine
class Handler(BaseHTTPRequestHandler):
    def send_app_headers(self,code=200,kind='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type',kind)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Referrer-Policy','no-referrer')
        self.end_headers()
    def respond(self,code,data):
        body=json.dumps(data).encode()
        self.send_app_headers(code)
        self.wfile.write(body)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/':
            self.send_app_headers(200,'text/html; charset=utf-8')
            self.wfile.write((ROOT/'index.html').read_bytes())
        elif p=='/app.js':
            self.send_app_headers(200,'text/javascript; charset=utf-8')
            self.wfile.write((ROOT/'app.js').read_bytes())
        elif p=='/api/dashboard':self.respond(200,self.server.engine.dashboard())
        elif p=='/api/audit':self.respond(200,{'hash_chain_valid':self.server.engine.verify_audit(),'note':'Internal hash-chain check only; not independent or tamper-proof custody'})
        else:self.respond(404,{'error':'Not found'})
    def do_POST(self):
        p=urlparse(self.path).path
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n<2 or n>10000:raise ValidationError('Payload size invalid')
            data=json.loads(self.rfile.read(n))
            if not isinstance(data,dict):raise ValidationError('Object required')
            key=self.headers.get('Idempotency-Key') or str(uuid.uuid4())
            if p=='/api/matters':result=self.server.engine.create_matter(data.get('title'),key)
            elif p=='/api/entries':result=self.server.engine.add_entry(data.get('matter_id'),data.get('kind'),data.get('text'),data.get('occurred_at'),data.get('minutes',0),key)
            elif p=='/api/tasks/complete':result=self.server.engine.complete_task(data.get('entry_id'),data.get('expected_version'),key)
            else:return self.respond(404,{'error':'Not found'})
            self.respond(201,result)
        except (ValidationError,ValueError,TypeError) as e:self.respond(400,{'error':str(e)})
        except ConflictError as e:self.respond(409,{'error':str(e)})
        except NotFoundError as e:self.respond(404,{'error':str(e)})
    def log_message(self,*args): pass

def run():
    engine=Engine(Path(os.getcwd())/'demo.sqlite')
    server=Server(('127.0.0.1',8765),engine)
    print('Fictional-data prototype: http://127.0.0.1:8765',flush=True)
    server.serve_forever()
if __name__=='__main__':run()

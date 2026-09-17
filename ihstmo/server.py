from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import csv
import io
import json
import mimetypes
import threading
import webbrowser
from .data import ROOT, DATA, read_csv
from .model import Model, validate_case, stamp

class Application:
    def __init__(self):
        self.cases=read_csv(DATA/'synthetic_india_cases.csv')
        for row in self.cases: validate_case(row)
        self.model=Model(json.loads((ROOT/'outputs/model.json').read_text(encoding='utf-8')),read_csv(DATA/'multilingual_mo_lexicon.csv'))
        self.by_id={c['case_id']:c for c in self.cases}
    def handler(self):
        app=self
        class Handler(BaseHTTPRequestHandler):
            server_version='I-HSTMO/1.0'
            def send(self,body,status=200,content_type='application/json; charset=utf-8'):
                if not isinstance(body,bytes): body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8')
                self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(body)))
                self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store')
                self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
                self.end_headers(); self.wfile.write(body)
            def do_GET(self):
                path=urlparse(self.path).path; args=parse_qs(urlparse(self.path).query)
                try:
                    if path=='/api/health': return self.send(dict(status='ok',version='1.0.0',cases=len(app.cases),mode='synthetic_research'))
                    if path=='/api/manifest': return self.send(json.loads((DATA/'manifest.json').read_text(encoding='utf-8')))
                    if path=='/api/evaluation': return self.send(json.loads((ROOT/'outputs/evaluation.json').read_text(encoding='utf-8')))
                    if path=='/api/regional': return self.send(dict(rows=read_csv(DATA/'india_state_trends.csv'),source='https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241336&lang=1&reg=1',notice='Registered case counts; not population-normalised risk.'))
                    if path=='/api/cases':
                        city=args.get('city',[''])[0]; q=args.get('q',[''])[0].lower()
                        rows=[c for c in app.cases if (not city or c['city']==city) and (not q or q in (c['case_id']+' '+c['narrative']).lower())]
                        return self.send(dict(cases=rows,total=len(rows),cities=sorted({c['city'] for c in app.cases})))
                    if path=='/api/link':
                        cid=args.get('case_id',[''])[0]
                        if cid not in app.by_id: return self.send({'error':'Unknown case_id'},404)
                        k=int(args.get('limit',['10'])[0])
                        if not 1<=k<=100: raise ValueError('limit must be 1..100')
                        return self.send(dict(query=app.by_id[cid],results=app.model.rank(app.by_id[cid],app.cases,k),notice=app.model.p['label_warning']))
                    if path.startswith('/download/'):
                        name=path.removeprefix('/download/')
                        allowed={p.name:p for p in DATA.glob('*.csv')}; allowed['manifest.json']=DATA/'manifest.json'; allowed['evaluation.json']=ROOT/'outputs/evaluation.json'
                        if name not in allowed: return self.send({'error':'Unknown dataset'},404)
                        return self.send(allowed[name].read_bytes(),content_type='application/octet-stream')
                    static={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css'}
                    if path not in static: return self.send({'error':'Not found'},404)
                    file=ROOT/'web'/static[path]
                    return self.send(file.read_bytes(),content_type=(mimetypes.guess_type(file.name)[0] or 'text/plain')+'; charset=utf-8')
                except (ValueError,TypeError) as e: self.send({'error':str(e)},400)
                except Exception:
                    import traceback; traceback.print_exc(); self.send({'error':'Internal error; see server log'},500)
            def do_POST(self):
                if urlparse(self.path).path!='/api/analyze': return self.send({'error':'Not found'},404)
                origin=self.headers.get('Origin')
                if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}: return self.send({'error':'Origin not allowed'},403)
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if size<=0 or size>2_000_000: raise ValueError('Request must be 1 byte to 2 MB')
                    body=json.loads(self.rfile.read(size)); rows=body.get('cases')
                    if rows is None: rows=list(csv.DictReader(io.StringIO(body.get('csv','').lstrip('\ufeff'))))
                    if not isinstance(rows,list) or not 2<=len(rows)<=1000: raise ValueError('Provide 2 to 1,000 case records')
                    ids=set()
                    for row in rows:
                        validate_case(row)
                        if row['case_id'] in ids: raise ValueError('Duplicate case_id')
                        ids.add(row['case_id'])
                    qid=body.get('query_id') or max(rows,key=lambda c:stamp(c['incident_start']))['case_id']
                    query=next((r for r in rows if r['case_id']==qid),None)
                    if query is None: raise ValueError('Query ID not in imported cases')
                    # Per-request model avoids retaining uploaded narrative text in token caches.
                    model=Model(app.model.p,app.model.lexicon)
                    return self.send(dict(query=query,results=model.rank(query,rows,20),records=len(rows),notice='Uploaded records processed in memory. Scoring model is synthetic-trained and not validated for real cases.'))
                except (ValueError,TypeError,KeyError,AttributeError) as e: self.send({'error':str(e)},400)
            def log_message(self,fmt,*args):
                print('%s %s'%(self.address_string(),fmt%args),flush=True)
        return Handler

def serve(port=8765,open_browser=False):
    app=Application(); server=ThreadingHTTPServer(('127.0.0.1',port),app.handler())
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'I-HSTMO India running at {url}',flush=True)
    if open_browser: threading.Timer(.8,lambda:webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

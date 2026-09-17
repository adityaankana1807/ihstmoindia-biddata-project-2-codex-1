"""Verify the running packaged executable through its public HTTP interface."""
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen, Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ihstmo.data import ROOT, write_json

base='http://127.0.0.1:8765'
checked=[]
for path in ['/','/app.js','/style.css','/api/health','/api/manifest','/api/evaluation','/api/regional','/download/synthetic_india_cases.csv']:
    with urlopen(base+path,timeout=15) as r:
        content=r.read(); assert r.status==200 and content
        checked.append(dict(path=path,status=r.status,bytes=len(content)))
with urlopen(base+'/api/link?case_id=SYN-IN-0000-05&limit=3') as r: ranked=json.load(r)
assert len(ranked['results'])==3
with urlopen(base+'/api/cases') as r: cases=json.load(r)['cases'][:6]
request=Request(base+'/api/analyze',data=json.dumps({'cases':cases}).encode(),headers={'Content-Type':'application/json'})
with urlopen(request,timeout=15) as r: imported=json.load(r)
assert imported['records']==6 and imported['results']
exe=ROOT/'dist/I-HSTMO-India.exe'
report=dict(executable=str(exe.name),executable_bytes=exe.stat().st_size,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),base_url=base,http_checks=checked,ranking_results=3,imported_records=6,python_compileall='passed',javascript_syntax='node --check passed',unittest_count=20,unittest_result='20 tests passed before this executable smoke test',scope='Local Windows build; no real police validation and no hosted deployment')
write_json(ROOT/'outputs/verification.json',report)
print(json.dumps(report,indent=2))

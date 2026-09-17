import copy
import json
import math
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from ihstmo.data import DATA, ROOT, read_csv
from ihstmo.model import Model, FEATURES, MO_FIELDS, validate_case, distance, time_gap, stamp
from ihstmo.evaluate import pair_metrics
from ihstmo.server import Application

class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=read_csv(DATA/'synthetic_india_cases.csv')
        cls.model=Model(json.loads((ROOT/'outputs/model.json').read_text()),read_csv(DATA/'multilingual_mo_lexicon.csv'))
    def test_official_national_reconciliation(self):
        rows=read_csv(DATA/'india_cybercrime_state_year.csv')
        self.assertEqual(len(rows),108)
        self.assertEqual(len({r['state_ut'] for r in rows}),36)
        self.assertEqual({y:sum(int(r['registered_cases']) for r in rows if r['year']==str(y)) for y in [2021,2022,2023]}, {2021:52974,2022:65893,2023:86420})
    def test_all_cases_valid_unique_synthetic(self):
        self.assertEqual(len(self.cases),840)
        self.assertEqual(len({c['case_id'] for c in self.cases}),840)
        for c in self.cases:
            validate_case(c); self.assertEqual(c['data_kind'],'synthetic')
    def test_no_offender_overlap(self):
        splits=read_csv(DATA/'synthetic_india_splits.csv'); observed={}
        for r in splits:
            observed.setdefault(r['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in observed.values()))
        self.assertEqual({r['split'] for r in splits},{'train','validation','test'})
    def test_no_ground_truth_predictors(self):
        a,b=copy.deepcopy(self.cases[:2]); expected=self.model.features(a,b)
        a.update(offender_id='SECRET-A',series_id='A',known_offender_id='B',forensic_link_flag=True)
        b.update(offender_id='SECRET-A',series_id='A',known_offender_id='B',forensic_link_flag=True)
        self.assertEqual(expected,self.model.features(a,b))
    def test_missing_mo_is_finite(self):
        a,b=copy.deepcopy(self.cases[:2])
        for k in MO_FIELDS: a[k]=''; b[k]=''
        x=self.model.features(a,b)
        self.assertEqual(x[2],0); self.assertEqual(x[-1],0)
        self.assertTrue(all(math.isfinite(v) for v in x))
    def test_all_zero_mo_weights(self):
        m=Model(copy.deepcopy(self.model.p),self.model.lexicon); m.p['mo_weights']={k:0 for k in MO_FIELDS}
        self.assertEqual(m.features(*self.cases[:2])[2],0)
    def test_interval_overlap(self):
        a=copy.deepcopy(self.cases[0]); b=copy.deepcopy(a)
        self.assertEqual(time_gap(a,b),0)
        self.assertAlmostEqual(distance(a,b),0)
    def test_timezone_validation(self):
        with self.assertRaises(ValueError): stamp('2025-01-01T00:00:00')
        self.assertEqual(stamp('2025-01-01T05:30:00+05:30'),stamp('2025-01-01T00:00:00+00:00'))
    def test_reject_invalid_coordinates(self):
        for value in ['nan','inf',91]:
            c=dict(self.cases[0],latitude=value)
            with self.assertRaises(ValueError): validate_case(c)
    def test_lexicon_equivalence(self):
        self.assertAlmostEqual(self.model.text_similarity('cash forced lock','नकदी ताला तोड़ा'),self.model.text_similarity('cash forced lock','cash forced lock'))
    def test_historical_only(self):
        q=max(self.cases,key=lambda c:stamp(c['incident_start'])); chosen=self.model.candidates(q,self.cases)
        self.assertTrue(chosen)
        self.assertTrue(all(stamp(c['incident_end'])<stamp(q['incident_start']) and c['case_id']!=q['case_id'] for c in chosen))
    def test_known_metric_values_and_ties(self):
        good=pair_metrics([0,1],[0,1]); tied=pair_metrics([0,1],[.5,.5])
        self.assertEqual(good['roc_auc'],1); self.assertEqual(good['average_precision'],1)
        self.assertEqual(tied['roc_auc'],.5); self.assertEqual(tied['average_precision'],.5)
    def test_manifest_hashes(self):
        import hashlib
        m=json.loads((DATA/'manifest.json').read_text())
        for r in m['files']:
            self.assertEqual(hashlib.sha256((DATA/r['file']).read_bytes()).hexdigest(),r['sha256'])
    def test_cli_unicode_on_windows_console(self):
        import os,subprocess,sys,tempfile
        with tempfile.TemporaryDirectory() as folder:
            result=subprocess.run([sys.executable,'-m','ihstmo.cli','--query','SYN-IN-0000-05','--top','3','--out',folder+'/result.json'],cwd=ROOT,env=dict(os.environ,PYTHONIOENCODING='cp1252'),capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout.decode('utf-8'))['query']['case_id'],'SYN-IN-0000-05')

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=Application(); cls.server=ThreadingHTTPServer(('127.0.0.1',0),cls.app.handler())
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def test_all_read_endpoints_and_assets(self):
        for path in ['/','/app.js','/style.css','/api/health','/api/manifest','/api/cases','/api/regional','/api/evaluation','/download/synthetic_india_cases.csv']:
            with urlopen(self.base+path) as response: self.assertEqual(response.status,200); self.assertTrue(response.read())
    def test_query_ranking(self):
        q=max(self.app.cases,key=lambda c:stamp(c['incident_start']))
        with urlopen(self.base+'/api/link?case_id='+q['case_id']) as r: data=json.load(r)
        self.assertTrue(data['results']); self.assertEqual(data['query']['case_id'],q['case_id'])
        scores=[r['score'] for r in data['results']]; self.assertEqual(scores,sorted(scores,reverse=True))
    def test_unknown_path_and_case(self):
        for p in ['/download/../outputs/model.json','/api/link?case_id=missing','/does-not-exist']:
            with self.assertRaises(HTTPError) as e: urlopen(self.base+p)
            self.assertEqual(e.exception.code,404)
    def post(self,payload):
        req=Request(self.base+'/api/analyze',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        return urlopen(req)
    def test_import_csv(self):
        import io,csv
        rows=self.app.cases[:6]; buff=io.StringIO(); writer=csv.DictWriter(buff,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        with self.post({'csv':buff.getvalue()}) as r: data=json.load(r)
        self.assertEqual(data['records'],6); self.assertTrue(data['results'])
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(HTTPError) as e: self.post({'cases':[self.app.cases[0]]*2})
        self.assertEqual(e.exception.code,400)
    def test_bad_input_returns_400(self):
        for body in [{'cases':[]},{'cases':[dict(self.app.cases[0],latitude='nan'),self.app.cases[1]]},{'csv':'not,a,case\n1,2,3'}]:
            with self.assertRaises(HTTPError) as e: self.post(body)
            self.assertEqual(e.exception.code,400)

if __name__=='__main__': unittest.main()

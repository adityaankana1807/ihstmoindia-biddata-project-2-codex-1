"""Interpretable I-HSTMO baseline. No identity, series, or forensic labels are predictors."""
from collections import Counter, defaultdict
from datetime import datetime
import math
import re
import statistics

MO_FIELDS=['target_type','entry_method','tool_weapon','property_stolen','escape_mode']
FEATURES=['space','time','mo','text','interaction','crime_compatibility','mo_coverage']

def stamp(value):
    d=datetime.fromisoformat(value)
    if d.tzinfo is None: raise ValueError('incident times must include timezone, e.g. +05:30')
    return d.timestamp()

def validate_case(row):
    for key in ['case_id','incident_start','crime_family','narrative','latitude','longitude','city','state_ut']:
        if key not in row or str(row[key]).strip()=='': raise ValueError(f'Missing {key}')
    if not isinstance(row['case_id'],str) or len(row['case_id'])>100: raise ValueError('Invalid case_id')
    if len(str(row['narrative']))>10000: raise ValueError('Narrative exceeds 10,000 characters')
    lat,lon=float(row['latitude']),float(row['longitude'])
    if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180): raise ValueError('Invalid coordinates')
    start=stamp(row['incident_start'])
    if row.get('incident_end') and stamp(row['incident_end'])<start: raise ValueError('incident_end precedes start')
    return row

def distance(a,b):
    p,q=math.radians(float(a['latitude'])),math.radians(float(b['latitude']))
    dl=math.radians(float(b['longitude'])-float(a['longitude']))
    h=math.sin((q-p)/2)**2+math.cos(p)*math.cos(q)*math.sin(dl/2)**2
    return 6371.0088*2*math.asin(math.sqrt(min(1,max(0,h))))

def time_gap(a,b):
    sa,sb=stamp(a['incident_start']),stamp(b['incident_start'])
    ea=stamp(a.get('incident_end') or a['incident_start'])
    eb=stamp(b.get('incident_end') or b['incident_start'])
    return max(0,sa-eb,sb-ea)/86400

def sigmoid(x): return 1/(1+math.exp(-max(-40,min(40,x))))

def fit_logistic(xs,ys,steps=350,rate=.4,balanced=True,l2=.01):
    if not xs or len(set(ys))<2: raise ValueError('Training needs positive and negative examples')
    w=[0.]*(len(xs[0])+1); n=len(xs); pos=sum(ys)
    weights=[n/(2*pos) if y else n/(2*(n-pos)) for y in ys] if balanced else [1.]*n
    for _ in range(steps):
        grad=[0.]*len(w)
        for x,y,weight in zip(xs,ys,weights):
            err=(sigmoid(w[0]+sum(a*b for a,b in zip(w[1:],x)))-y)*weight
            grad[0]+=err
            for k,v in enumerate(x,1): grad[k]+=err*v
        w=[v-rate*(g/n+(l2*v if k else 0)) for k,(v,g) in enumerate(zip(w,grad))]
    return w

class Model:
    def __init__(self, payload=None, lexicon=None):
        self.p=payload or {}; self.lexicon=lexicon or []
        self._token_cache={}
    def tokens(self,text):
        if text in self._token_cache: return self._token_cache[text]
        original=text
        text=text.lower(); concepts=[]
        for item in sorted(self.lexicon,key=lambda r:len(r['phrase']),reverse=True):
            if item['phrase'] in text:
                text=text.replace(item['phrase'],' '); concepts.append(item['concept'])
        stop={'incident','reported','evening','time','of','occurrence','uncertain','entry','described','by','witness','the','a','and'}
        ts=concepts+[t for t in re.findall(r'[^\W\d_]+',text,flags=re.UNICODE) if t not in stop and len(t)>1]
        self._token_cache[original]=ts
        return ts
    def text_similarity(self,a,b):
        ca,cb=Counter(self.tokens(a)),Counter(self.tokens(b)); idf=self.p.get('idf',{})
        va={t:n*idf.get(t,0) for t,n in ca.items()}; vb={t:n*idf.get(t,0) for t,n in cb.items()}
        norm=math.sqrt(sum(v*v for v in va.values())*sum(v*v for v in vb.values()))
        cosine=sum(v*vb.get(t,0) for t,v in va.items())/norm if norm else 0
        def bm(q,d):
            length=sum(d.values()); avg=self.p.get('average_length',1)
            return sum(idf.get(t,0)*(d.get(t,0)*2.2)/(d.get(t,0)+1.2*(.25+.75*length/avg)) for t in q)
        raw=(bm(ca,cb)+bm(cb,ca))/2
        return .7*cosine+.3*raw/(raw+5)
    def fit_features(self,cases,labels):
        df=Counter(); lengths=[]
        for c in cases:
            ts=self.tokens(c['narrative']); df.update(set(ts)); lengths.append(len(ts))
        self.p['idf']={t:math.log(1+(len(cases)-n+.5)/(n+.5)) for t,n in df.items()}
        self.p['average_length']=max(1,statistics.mean(lengths))
        observed={k:[0,0,0,0] for k in MO_FIELDS}; distances=[]; gaps=[]; local=defaultdict(lambda:[[],[]]); comp=defaultdict(lambda:[0,0])
        for i,a in enumerate(cases):
            for b in cases[:i]:
                y=int(labels[a['case_id']]==labels[b['case_id']])
                key='|'.join(sorted([a['crime_family'],b['crime_family']]))
                comp[key][1]+=1; comp[key][0]+=y
                for k in MO_FIELDS:
                    if a.get(k) and b.get(k):
                        observed[k][2*y]+=int(a[k]==b[k]); observed[k][2*y+1]+=1
                if y:
                    d=distance(a,b); t=time_gap(a,b); distances.append(d); gaps.append(t)
                    key=a['city']+'|'+a['crime_family']; local[key][0].append(d); local[key][1].append(t)
        self.p['mo_weights']={k:math.log(((v[2]+1)/(v[3]+2))/((v[0]+1)/(v[1]+2))) for k,v in observed.items()}
        gs=max(.25,statistics.median(distances)); gt=max(1,statistics.median(gaps))
        self.p['global_scales']=[gs,gt]
        self.p['local_scales']={k:[(len(ds)*statistics.median(ds)+20*gs)/(len(ds)+20),(len(ts)*statistics.median(ts)+20*gt)/(len(ts)+20)] for k,(ds,ts) in local.items()}
        self.p['compatibility']={k:(v[0]+1)/(v[1]+2) for k,v in comp.items()}
        self.p['global_compatibility']=(sum(v[0] for v in comp.values())+1)/(sum(v[1] for v in comp.values())+2)
    def features(self,a,b):
        d=distance(a,b); t=time_gap(a,b)
        scales=[self.p['local_scales'].get(c['city']+'|'+c['crime_family'],self.p['global_scales']) for c in (a,b)]
        spatial=math.exp(-d/max(.25,(scales[0][0]+scales[1][0])/2))
        temporal=math.exp(-t/max(1,(scales[0][1]+scales[1][1])/2))
        observed=[k for k in MO_FIELDS if a.get(k) and b.get(k)]
        denom=sum(abs(self.p['mo_weights'][k]) for k in observed)
        mo=sum(self.p['mo_weights'][k]*(a[k]==b[k]) for k in observed)/denom if denom else 0
        text=self.text_similarity(a['narrative'],b['narrative'])
        compatibility=self.p['compatibility'].get('|'.join(sorted([a['crime_family'],b['crime_family']])),self.p['global_compatibility'])
        return [spatial,temporal,mo,text,spatial*temporal*(1+max(0,mo)+text),compatibility,len(observed)/len(MO_FIELDS)]
    def raw_score(self,x): return self.p['weights'][0]+sum(w*v for w,v in zip(self.p['weights'][1:],x))
    def probability(self,x):
        raw=self.raw_score(x); c=self.p.get('calibration',[0,1]); return sigmoid(c[0]+c[1]*raw)
    def candidates(self,query,cases,top=50):
        historical=[c for c in cases if c['case_id']!=query['case_id'] and stamp(c.get('incident_end') or c['incident_start'])<stamp(query['incident_start'])]
        geographic=sorted(historical,key=lambda c:distance(query,c))[:top]
        textual=sorted(historical,key=lambda c:self.text_similarity(query['narrative'],c['narrative']),reverse=True)[:top]
        # Cross-crime candidates remain eligible; the pool never reads labels.
        temporal=sorted(historical,key=lambda c:time_gap(query,c))[:top]
        ids={c['case_id'] for c in geographic+textual+temporal}
        return [c for c in historical if c['case_id'] in ids]
    def rank(self,query,cases,limit=10):
        validate_case(query); results=[]
        for other in self.candidates(query,cases):
            x=self.features(query,other)
            factors=[dict(feature=k,value=round(v,5),logit_contribution=round(v*w,5)) for k,v,w in zip(FEATURES,x,self.p['weights'][1:])]
            results.append(dict(case_id=other['case_id'],city=other['city'],crime_family=other['crime_family'],incident_start=other['incident_start'],score=round(self.probability(x),6),distance_km=round(distance(query,other),3),gap_days=round(time_gap(query,other),2),mo_coverage=x[-1],factors=factors,low_evidence=x[-1]<.4))
        results.sort(key=lambda r:(-r['score'],r['case_id']))
        return results[:limit]

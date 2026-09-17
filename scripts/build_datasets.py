"""Deterministic synthetic fixtures plus parsed, reconciled official aggregate data."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import random
import sys
from pathlib import Path
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ihstmo.data import ROOT, DATA, write_csv, write_json

URL = 'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241336&lang=1&reg=1'
SEED = 20260916

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=[]; self.cell=None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row=[]
        if tag in ('td','th'): self.cell=[]
    def handle_data(self, value):
        if self.cell is not None: self.cell.append(value)
    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split())); self.cell=None
        if tag == 'tr' and self.row: self.rows.append(self.row)

def official(refresh=False):
    path=ROOT/'data/raw/pib_2241336.html'
    if refresh or not path.exists():
        request=urllib.request.Request(URL, headers={'User-Agent':'I-HSTMO-Research/1.0'})
        content=urllib.request.urlopen(request, timeout=45).read()
        # Validate before replacing the offline snapshot.
        check=Tables(); check.feed(content.decode('utf-8-sig'))
        if not any('TOTAL (ALL INDIA)' in ' '.join(r) for r in check.rows):
            raise ValueError('Official source table missing; no data overwritten')
        path.write_bytes(content)
    parser=Tables(); parser.feed(path.read_text(encoding='utf-8-sig'))
    rows=[]; seen=set(); totals={}
    for r in parser.rows:
        if len(r)!=5: continue
        if 'TOTAL (ALL INDIA)' in ' '.join(r):
            totals={year:int(r[i+2].replace(',','')) for i,year in enumerate((2021,2022,2023))}
        if not r[0].isdigit() or not 1<=int(r[0])<=36 or r[1] in seen: continue
        seen.add(r[1])
        for i,year in enumerate((2021,2022,2023)):
            rows.append(dict(state_ut=r[1],year=year,crime_family='cybercrime',registered_cases=int(r[i+2].replace(',','')),data_kind='official_aggregate',source_url=URL,source_release_date='2026-03-17'))
    assert len(seen)==36 and len(rows)==108, (len(seen),len(rows))
    actual={year:sum(x['registered_cases'] for x in rows if x['year']==year) for year in totals}
    assert actual==totals=={2021:52974,2022:65893,2023:86420}, (actual,totals)
    write_csv(DATA/'india_cybercrime_state_year.csv',rows)
    trends=[]
    for state in sorted(seen):
        vals={r['year']:r['registered_cases'] for r in rows if r['state_ut']==state}
        baseline=vals[2022]; observed=vals[2023]
        trends.append(dict(state_ut=state,cases_2021=vals[2021],cases_2022=baseline,cases_2023=observed,change_2022_2023=observed-baseline,growth_pct='' if baseline==0 else round(100*(observed-baseline)/baseline,4),national_share_2023_pct=round(100*observed/totals[2023],4),naive_2023_prediction=baseline,naive_absolute_error=abs(observed-baseline),data_kind='derived_official_aggregate',source_url=URL))
    write_csv(DATA/'india_state_trends.csv',trends)
    return actual

# Approximate city centres are generator anchors, not measured crime locations or GIS boundaries.
CITIES=[('Delhi','Delhi',28.61,77.21,'hi'),('Mumbai','Maharashtra',19.08,72.88,'hi'),('Bengaluru','Karnataka',12.97,77.59,'kn'),('Hyderabad','Telangana',17.39,78.49,'te'),('Chennai','Tamil Nadu',13.08,80.27,'ta'),('Kolkata','West Bengal',22.57,88.36,'bn'),('Pune','Maharashtra',18.52,73.86,'hi'),('Jaipur','Rajasthan',26.91,75.79,'hi')]
LEXICON={
 'forced_lock':['forced lock','ताला तोड़ा','తాళం పగలగొట్టి','பூட்டை உடைத்து','ಬೀಗ ಒಡೆದು','তালা ভেঙে'],
 'window':['window','खिड़की','కిటికీ','ஜன்னல்','ಕಿಟಕಿ','জানালা'],
 'cash':['cash','नकदी','నగదు','பணம்','ನಗದು','নগদ'],
 'jewellery':['jewellery','गहने','నగలు','நகை','ಆಭರಣ','গয়না'],
 'motorcycle':['motorcycle','मोटरसाइकिल','మోటార్ సైకిల్','மோட்டார் சைக்கிள்','ಮೋಟಾರ್ ಸೈಕಲ್','মোটরসাইকেল'],
 'foot':['on foot','पैदल','కాలినడక','நடந்து','ನಡೆದು','পায়ে হেঁটে']}

def synthetic():
    rng=random.Random(SEED); rows=[]; truth=[]; splits=[]
    groups=list(range(240)); rng.shuffle(groups)
    assignments={g:('train' if i<144 else 'validation' if i<192 else 'test') for i,g in enumerate(groups)}
    for group in range(240):
        city,state,lat,lon,language=CITIES[group%len(CITIES)]
        n=6 if group<120 else 1
        base=datetime(2023,1,1,tzinfo=timezone(timedelta(hours=5,minutes=30)))+timedelta(days=rng.randrange(700))
        anchor=(lat+rng.uniform(-.06,.06),lon+rng.uniform(-.06,.06))
        profile=[rng.choice(['house','shop','warehouse']),rng.choice(['forced_lock','window','open_door']),rng.choice(['crowbar','cutter','none']),rng.choice(['cash','jewellery','electronics']),rng.choice(['motorcycle','foot','car'])]
        for j in range(n):
            cid=f'SYN-IN-{group:04d}-{j:02d}'
            mo=[v if rng.random()>.22 else rng.choice(opts) for v,opts in zip(profile,[['house','shop','warehouse'],['forced_lock','window','open_door'],['crowbar','cutter','none'],['cash','jewellery','electronics'],['motorcycle','foot','car']])]
            dt=base+timedelta(days=j*rng.randint(3,22),hours=rng.randrange(24))
            lang=rng.choice(['en',language]); li=['en','hi','te','ta','kn','bn'].index(lang)
            concepts=[mo[1],mo[3],mo[4]]
            phrase='; '.join(LEXICON[c][li] if c in LEXICON else c.replace('_',' ') for c in concepts)
            # No group/series identifiers in narrative or model input.
            narrative=f'{phrase}. {rng.choice(["Evening incident reported.","Time of occurrence uncertain.","Entry described by witness."])}'
            observed=[v if rng.random()>.12 else '' for v in mo]
            rows.append(dict(case_id=cid,incident_start=dt.isoformat(),incident_end=(dt+timedelta(hours=rng.choice([1,3,8]))).isoformat(),city=city,state_ut=state,latitude=round(anchor[0]+rng.gauss(0,.014),6),longitude=round(anchor[1]+rng.gauss(0,.014),6),crime_family=rng.choice(['burglary','theft']) if group%7==0 else 'burglary',target_type=observed[0],entry_method=observed[1],tool_weapon=observed[2],property_stolen=observed[3],escape_mode=observed[4],narrative=narrative,language=lang,data_kind='synthetic',generator_seed=SEED))
            truth.append(dict(case_id=cid,series_id=f'SYN-SERIES-{group:04d}',offender_id=f'SYN-OFFENDER-{group:04d}',label_basis='generator_latent_group_not_police_evidence',data_kind='synthetic'))
            splits.append(dict(case_id=cid,split=assignments[group],group_id=f'SYN-OFFENDER-{group:04d}',data_kind='synthetic'))
    write_csv(DATA/'synthetic_india_cases.csv',rows)
    write_csv(DATA/'synthetic_india_ground_truth.csv',truth)
    write_csv(DATA/'synthetic_india_splits.csv',splits)
    write_csv(DATA/'multilingual_mo_lexicon.csv',[dict(concept=k,language=lang,phrase=v[i],data_kind='handwritten_demo_lexicon') for k,v in LEXICON.items() for i,lang in enumerate(['en','hi','te','ta','kn','bn'])])
    return len(rows)

def manifest(totals,count):
    entries=[]
    for path in sorted(DATA.glob('*.csv')):
        import csv
        with path.open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
        entries.append(dict(file=path.name,rows=len(rows),columns=list(rows[0]) if rows else [],sha256=hashlib.sha256(path.read_bytes()).hexdigest(),kind=rows[0].get('data_kind','derived_synthetic') if rows else 'empty'))
    write_json(DATA/'manifest.json',dict(version='1.0.0',seed=SEED,generated_at_utc=datetime.now(timezone.utc).isoformat(),official_source=URL,source_snapshot_sha256=hashlib.sha256((ROOT/'data/raw/pib_2241336.html').read_bytes()).hexdigest(),official_totals=totals,synthetic_cases=count,files=entries,limitations=['Official data are state-year cybercrime counts, not population-normalised risk or individual cases.','Synthetic property-crime cases are independent of official cybercrime counts; no disaggregation is performed.','Demo language phrases and city anchors are authored fixtures, not a representative Indian police corpus.','Third-party source ownership and terms remain with the original provider.']))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--refresh',action='store_true'); args=p.parse_args()
    totals=official(args.refresh); count=synthetic(); manifest(totals,count)
    print(f'Official: 108 state-year rows, reconciled totals {totals}; synthetic: {count} cases; seed {SEED}')

if __name__=='__main__': main()

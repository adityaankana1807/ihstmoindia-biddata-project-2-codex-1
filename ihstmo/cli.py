import argparse
import json
import sys
from .data import ROOT, DATA, read_csv, write_json
from .model import Model, validate_case

def main():
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description='Rank historical case candidates using the synthetic-trained research baseline')
    p.add_argument('--cases',default=str(DATA/'synthetic_india_cases.csv'))
    p.add_argument('--query',required=True); p.add_argument('--top',type=int,default=10)
    p.add_argument('--out',default='outputs/ranking.json'); args=p.parse_args()
    cases=read_csv(args.cases)
    for c in cases: validate_case(c)
    query=next((c for c in cases if c['case_id']==args.query),None)
    if query is None: p.error('Query case ID not found')
    model=Model(json.loads((ROOT/'outputs/model.json').read_text(encoding='utf-8')),read_csv(DATA/'multilingual_mo_lexicon.csv'))
    result=dict(query=query,results=model.rank(query,cases,args.top),notice=model.p['label_warning'])
    write_json(args.out,result); print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()

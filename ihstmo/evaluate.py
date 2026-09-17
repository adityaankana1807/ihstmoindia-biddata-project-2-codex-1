"""All performance here measures synthetic fixtures, never real police effectiveness."""
from itertools import combinations
import math
import random
import statistics
from .data import DATA, ROOT, read_csv, write_csv, write_json
from .model import Model, FEATURES, distance, stamp, fit_logistic

def pair_metrics(y,scores):
    n=len(y); positives=sum(y); negatives=n-positives
    if not positives or not negatives: return {'n':n,'positives':positives,'roc_auc':None,'average_precision':None}
    # Tie-aware ROC AUC and threshold-grouped average precision.
    groups={}
    for label,score in zip(y,scores): groups.setdefault(score,[]).append(label)
    below=0; wins=0
    for score in sorted(groups):
        labels=groups[score]; p=sum(labels); neg=len(labels)-p
        wins+=p*(below+.5*neg); below+=neg
    tp=fp=0; ap=0
    for score in sorted(groups,reverse=True):
        labels=groups[score]; p=sum(labels); tp+=p; fp+=len(labels)-p
        ap+=(p/positives)*(tp/(tp+fp))
    bins=[]
    for i in range(10):
        selected=[(a,b) for a,b in zip(y,scores) if i/10<=b<(i+1)/10 or (i==9 and b==1)]
        if selected: bins.append(dict(low=i/10,count=len(selected),mean_score=statistics.mean(b for a,b in selected),observed_fraction=statistics.mean(a for a,b in selected)))
    return dict(n=n,positives=positives,prevalence=positives/n,roc_auc=wins/(positives*negatives),average_precision=ap,brier=sum((a-b)**2 for a,b in zip(y,scores))/n,reliability=bins)

def historical_pairs(cases):
    for a,b in combinations(cases,2):
        if stamp(a.get('incident_end') or a['incident_start'])<stamp(b['incident_start']): yield b,a
        elif stamp(b.get('incident_end') or b['incident_start'])<stamp(a['incident_start']): yield a,b

def train_and_evaluate():
    cases=read_csv(DATA/'synthetic_india_cases.csv'); truth={r['case_id']:r['offender_id'] for r in read_csv(DATA/'synthetic_india_ground_truth.csv')}
    split={r['case_id']:r['split'] for r in read_csv(DATA/'synthetic_india_splits.csv')}
    pools={s:[c for c in cases if split[c['case_id']]==s] for s in ['train','validation','test']}
    groups={s:{truth[c['case_id']] for c in cs} for s,cs in pools.items()}
    assert all(not groups[a]&groups[b] for a,b in combinations(groups,2))
    model=Model(lexicon=read_csv(DATA/'multilingual_mo_lexicon.csv')); model.fit_features(pools['train'],truth)
    positive=[]; negative=[]
    for a,b in historical_pairs(pools['train']):
        (positive if truth[a['case_id']]==truth[b['case_id']] else negative).append((a,b))
    rng=random.Random(42)
    hard=[p for p in negative if p[0]['city']==p[1]['city']]
    selected={tuple(sorted((a['case_id'],b['case_id']))):(a,b) for a,b in rng.sample(negative,min(len(negative),len(positive)*4))+rng.sample(hard,min(len(hard),len(positive)*4))}
    pairs=positive+list(selected.values()); rng.shuffle(pairs)
    xs=[model.features(a,b) for a,b in pairs]; ys=[int(truth[a['case_id']]==truth[b['case_id']]) for a,b in pairs]
    model.p['weights']=fit_logistic(xs,ys)
    validation=list(historical_pairs(pools['validation']))
    vx=[model.features(a,b) for a,b in validation]; vy=[int(truth[a['case_id']]==truth[b['case_id']]) for a,b in validation]
    raw=[model.raw_score(x) for x in vx]
    model.p['calibration']=fit_logistic([[v] for v in raw],vy,steps=600,rate=.15,balanced=False,l2=.0001)
    model.p.update(version='1.0.0',features=FEATURES,training_kind='synthetic_only',training_cases=len(pools['train']),training_pairs=len(pairs),label_warning='Scores calibrated on synthetic validation pairs only; not real-world probabilities.',calibration_population='all non-overlapping within-validation historical pairs; retrieval selection changes this population')
    write_json(ROOT/'outputs/model.json',model.p)
    test=list(historical_pairs(pools['test'])); tx=[model.features(a,b) for a,b in test]; ty=[int(truth[a['case_id']]==truth[b['case_id']]) for a,b in test]
    scores=[model.probability(x) for x in tx]
    write_csv(DATA/'synthetic_test_pairs.csv',[dict(query_case=a['case_id'],candidate_case=b['case_id'],same_generated_offender=y,score=round(s,8),data_kind='synthetic_evaluation') for (a,b),y,s in zip(test,ty,scores)])
    per_query=[]
    for q in pools['test']:
        historical=[c for c in pools['test'] if stamp(c.get('incident_end') or c['incident_start'])<stamp(q['incident_start'])]
        relevant={c['case_id'] for c in historical if truth[c['case_id']]==truth[q['case_id']]}
        if not relevant: continue
        candidates=model.candidates(q,pools['test']); available={c['case_id'] for c in candidates}
        ranked=sorted(candidates,key=lambda c:model.probability(model.features(q,c)),reverse=True)
        hit_ranks=[i for i,c in enumerate(ranked,1) if c['case_id'] in relevant]
        row=dict(case_id=q['case_id'],relevant_historical=len(relevant),candidate_recall=len(relevant&available)/len(relevant),mrr=1/min(hit_ranks) if hit_ranks else 0,first_rank=min(hit_ranks) if hit_ranks else None)
        for k in (10,50,100): row['recall_at_'+str(k)]=sum(c['case_id'] in relevant for c in ranked[:k])/len(relevant)
        per_query.append(row)
    ranking={k:statistics.mean(r[k] for r in per_query) for k in ['candidate_recall','mrr','recall_at_10','recall_at_50','recall_at_100']}
    ranking.update(eligible_queries=len(per_query),excluded_no_historical_partner=len(pools['test'])-len(per_query),median_first_rank_among_retrieved=statistics.median(r['first_rank'] for r in per_query if r['first_rank'] is not None))
    # Each ablation is retrained on exactly the same training pairs, evaluated on same test pairs.
    ablations=[]
    for name,indices in [('Space',[0]),('Space + time',[0,1]),('Space + time + MO',[0,1,2,6]),('Add multilingual lexical text',[0,1,2,3,6]),('Full baseline',list(range(7)))]:
        if len(indices)==7: s=scores
        else:
            w=fit_logistic([[x[i] for i in indices] for x in xs],ys,steps=250)
            s=[1/(1+math.exp(-max(-40,min(40,w[0]+sum(w[j+1]*x[i] for j,i in enumerate(indices)))))) for x in tx]
        m=pair_metrics(ty,s); ablations.append(dict(model=name,roc_auc=m['roc_auc'],average_precision=m['average_precision']))
    report=dict(dataset_kind='synthetic_only',warning='These scores validate software on generated fixtures. They do not measure Indian police linkage accuracy.',splits={s:dict(cases=len(cs),offenders=len(groups[s])) for s,cs in pools.items()},offender_overlap=0,pair_metrics=pair_metrics(ty,scores),ranking=ranking,ablations=ablations,limitations=['Synthetic generator deliberately repeats patterns; distribution is not empirically estimated.','Calibration is for all historical validation pairs, not retrieval-conditioned deployment probabilities.','No held-out city/state or real language-corpus evaluation has been performed.','No neural embeddings, learned network features, or IPC-BNS mapping are claimed.'])
    write_json(ROOT/'outputs/evaluation.json',report)
    write_csv(ROOT/'outputs/query_metrics.csv',per_query)
    print('Synthetic evaluation:',{k:v for k,v in report['pair_metrics'].items() if k!='reliability'},ranking)
    return report

if __name__=='__main__': train_and_evaluate()

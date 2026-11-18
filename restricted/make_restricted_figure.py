#!/usr/bin/env python3
"""Generate same-population RESTRICTED figure from hashed audit CSV. Never publish."""
import argparse, csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('restricted_evidence'));a=p.parse_args()
    before=[];after=[]
    with (a.out/'fixed_population_before_after.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            (before if r['representation']=='before' else after).append((r['label'],int(r['row_count'])))
    assert sum(n for _,n in before)==sum(n for _,n in after), 'different observation universes'
    fig,axes=plt.subplots(1,2,figsize=(13,5.3))
    for ax,groups,title in zip(axes,[before,after],['Before: raw-code groups (same source-B rows)','After: approved existing-code harmonization']):
        x=list(range(len(groups))); vals=[n for k,n in groups]
        ax.bar(x,vals);ax.set_xticks(x,[k for k,n in groups],rotation=30,ha='right');ax.set_ylabel('Records (restricted operational data)');ax.set_title(title,fontsize=11)
        ax.grid(axis='y',alpha=.2)
        for k,n in enumerate(vals):ax.text(k,n+1500,f'{n:,}',ha='center',va='bottom',fontsize=8)
    fig.suptitle('RESTRICTED — fixed-population mapping census; missing-code recovery not demonstrated',fontsize=12)
    fig.text(.5,.01,'Same selected observations in both panels; unresolved original codes remain unresolved. NOT FOR PUBLIC RELEASE.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.93))
    fig.savefig(a.out/'figure1_fixed_population_RESTRICTED.png',dpi=170,bbox_inches='tight')
    fig.savefig(a.out/'figure1_fixed_population_RESTRICTED.pdf',bbox_inches='tight')
    plt.close(fig)
    print('PASS: same-population figure generated, private only')
if __name__=='__main__':main()

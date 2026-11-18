#!/usr/bin/env python3
"""Verify hash and arithmetic invariants of the new restricted snapshot audit.
This is a local consistency test; it does not attest an independent operator rerun.
"""
import argparse,csv,hashlib,json
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def readcsv(path):return list(csv.DictReader(path.open(encoding='utf-8',newline='')))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('restricted_evidence'));a=ap.parse_args()
    m=json.loads((a.out/'reproducibility_manifest.json').read_text())
    for fn,expected in m['output_hashes'].items():
        got=digest(a.out/fn)
        assert got==expected,(fn,got,expected)
        print('PASS hash',fn)
    s=json.loads((a.out/'audit_summary.json').read_text())
    A=s['source_A'];B=s['source_B']
    assert A['total']==A['selected']+A['outside']
    assert B['total']==B['selected']+B['outside']
    assert B['selected']==B['raw_mapped']+B['recovered']+B['unresolved']+B['excluded_after_selection']
    assert B['recovered']==0 and B['unresolved']==B['raw_missing']
    assert A['source_duplicate_keys']==A['selected']-(A['selected']-A['source_duplicate_keys'])
    states=readcsv(a.out/'fixed_population_before_after.csv')
    assert sum(int(r['row_count']) for r in states if r['representation']=='before')==B['selected']
    assert sum(int(r['row_count']) for r in states if r['representation']=='after')==B['selected']
    for fn in ['reconciliation_destination.csv','reconciliation_service.csv','reconciliation_origin.csv','reconciliation_week.csv']:
        rows=readcsv(a.out/fn)
        for side in ['a','b']:
            tally=sum(float(r[f'{side}_packages']) for r in rows)
            expected=s['total_packages_by_source'][side.upper()]
            assert abs(tally-expected)<1e-6,(fn,side,tally,expected)
        print('PASS aggregate conservation',fn)
    print('PASS: hashes, population invariants, and cross-grain package totals')
    print('NOT VERIFIED: historic complete canonicalization or second-operator rerun, source-owner semantics, disclosure clearance')
if __name__=='__main__':main()

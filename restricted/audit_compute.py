#!/usr/bin/env python3
"""Restricted read-only XLSX snapshot arithmetic for FedEx data-engineering case.

Uses Python standard library; no modification of the original snapshots and no
proprietary data is written to a public repository. This is a new independent
source-snapshot arithmetic audit, NOT a rerun of the historical Bronze pipeline.

Usage:
 python audit_compute.py --weekly 'Weekly 202201-202412(1)(1).xlsx' \
   --aug 'Aug actuals with DOM (1)(1).xlsx' \
   --xlsb 'Fedex data version 1 (1)(1).xlsb' --out restricted_evidence
"""
import argparse, collections, csv, datetime, hashlib, json, platform, re, sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
MAPPING={'EU':'Europe','AS':'APAC','ME':'MEISA','NA':'Americas','LA':'Americas'}
START=datetime.date(2024,8,1); END=datetime.date(2024,8,31)

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def colidx(ref):
    v=0
    for c in re.match(r'[A-Z]+',ref).group(0):v=v*26+ord(c)-64
    return v-1

def rows_xlsx(path):
    """Yield header dictionary then data dictionaries from first physical sheet."""
    with ZipFile(path) as z:
        strs=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for ev,e in ET.iterparse(z.open('xl/sharedStrings.xml'),events=('end',)):
                if e.tag==NS+'si':
                    strs.append(''.join(t.text or '' for t in e.iter() if t.tag==NS+'t'))
                    e.clear()
        names=None
        with z.open('xl/worksheets/sheet1.xml') as fp:
            for ev,e in ET.iterparse(fp,events=('end',)):
                if e.tag!=NS+'row':continue
                cells={}
                for c in e:
                    if c.tag!=NS+'c':continue
                    v=c.find(NS+'v')
                    val=v.text if v is not None else None
                    if c.get('t')=='s' and val is not None:val=strs[int(val)]
                    if c.get('t')=='inlineStr':val=''.join(t.text or '' for t in c.iter() if t.tag==NS+'t')
                    cells[colidx(c.get('r'))]=val
                if names is None:
                    names={k:v for k,v in cells.items()}
                    yield {'_HEADERS_':sorted(names.values())}
                else:
                    yield {name:cells.get(k) for k,name in names.items()}
                e.clear()

def exceldate(s):
    if s is None or s=='':return None
    try: return datetime.date(1899,12,30)+datetime.timedelta(days=float(s))
    except (ValueError,TypeError,OverflowError):
        try:return datetime.date.fromisoformat(str(s)[:10])
        except ValueError:return None

def normalized(v):return (str(v).strip() if v is not None else '')
def num(v):
    try:return float(v)
    except (ValueError,TypeError):return 0.0

def audit(path,datecol,source):
    d={'source':source,'total':0,'selected':0,'outside':0,'date_unparseable':0,
       'raw_missing':0,'raw_mapped':0,'raw_unknown':0,'recovered':0,'unresolved':0,
       'excluded_after_selection':0,'source_duplicate_keys':0}
    counts=collections.defaultdict(lambda:collections.defaultdict(float))
    keys=set()
    before=collections.Counter();after=collections.Counter()
    weeks=collections.defaultdict(lambda:collections.defaultdict(float))
    headers=None
    for r in rows_xlsx(path):
        if '_HEADERS_' in r:headers=r['_HEADERS_'];continue
        d['total']+=1
        dt=exceldate(r.get(datecol))
        if dt is None:d['date_unparseable']+=1
        if dt is None or not START<=dt<=END:
            d['outside']+=1;continue
        d['selected']+=1
        if source=='A':
            raw=normalized(r.get('Dest_Lane'))
            dest=MAPPING.get(raw,raw) if raw else '<UNRESOLVED>'
            service=normalized(r.get('Product_Code')) or '<UNRESOLVED>'
            site=normalized(r.get('ORIG_RAMP')) or '<NA>'
            pk=num(r.get('PACKS'))
            shp=num(r.get('Shipments'))
            weight=num(r.get('aPounds'))
            key=(normalized(r.get('FY')),normalized(r.get('WeekNbr')),normalized(r.get('Orig_Ctry')),site,normalized(r.get('Business_Region')),dest,service)
            if key in keys:d['source_duplicate_keys']+=1
            else:keys.add(key)
        else:
            raw=normalized(r.get('Lane_'))
            descr=normalized(r.get('Lane'))
            if not raw:
                d['raw_missing']+=1
                # No owner-authorized code inference is applied to this audit.
                # A description alone does not demonstrate historical recovery.
                dest='<UNRESOLVED>'
                d['unresolved']+=1
            elif raw in MAPPING:
                dest=MAPPING[raw]
                d['raw_mapped']+=1
            else:
                dest='<UNRESOLVED>'
                d['raw_unknown']+=1
                d['unresolved']+=1
            service=normalized(r.get('Product')) or '<UNRESOLVED>'
            site=normalized(r.get('ORIG_RAMP')) or '<NA>'
            pk=num(r.get('Packs'))
            shp=num(r.get('Shipments'))
            weight=num(r.get('aLbs'))
        before[raw or '<MISSING>']+=1
        after[dest]+=1
        for gran,grp in (('destination',dest),('service',service),('origin',site)):
            counts[(gran,grp)]['packages']+=pk
            counts[(gran,grp)]['shipments']+=shp
            counts[(gran,grp)]['weight_source_units']+=weight
        weeks[normalized(r.get('WeekNbr'))]['packages']+=pk
    d['retained']=d['selected']-d['excluded_after_selection']
    d['accounting_identity_pass']=d['selected']==(d['raw_mapped']+d['recovered']+d['unresolved']+d['excluded_after_selection']) if source=='B' else d['selected']+d['outside']==d['total']
    return d,counts,before,after,weeks,headers

def write_csv(p,header,rows):
    with open(p,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--weekly',required=True,type=Path);ap.add_argument('--aug',required=True,type=Path);ap.add_argument('--xlsb',type=Path);ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sa,ga,ba,aa,wa,ha=audit(a.weekly,'shp_dt','A')
    sb,gb,bb,ab,wb,hb=audit(a.aug,'ShipDate','B')
    if not (sa['accounting_identity_pass'] and sb['accounting_identity_pass']):raise RuntimeError('population ledger conservation FAILED')
    ledger=[['A','input',sa['total']],['A','inside date window',sa['selected']],['A','outside/invalid date',sa['outside']],['B','input',sb['total']],['B','inside date window',sb['selected']],['B','outside/invalid date',sb['outside']],['B','mapped original code',sb['raw_mapped']],['B','successfully recovered missing code',sb['recovered']],['B','unresolved raw code',sb['unresolved']],['B','excluded after date selection',sb['excluded_after_selection']],['B','post-rule retained (mapped + unresolved)',sb['retained']]]
    write_csv(a.out/'count_ledger.csv',['source','stage','rows'],ledger)
    write_csv(a.out/'fixed_population_before_after.csv',['representation','label','row_count'],[
        *(('before',k,v) for k,v in sorted(bb.items())),
        *(('after',k,v) for k,v in sorted(ab.items()))])
    for gran in ['destination','service','origin']:
        groups=sorted({k[1] for k in ga if k[0]==gran}|{k[1] for k in gb if k[0]==gran})
        rows=[]
        for k in groups:
            A=ga.get((gran,k),{}); B=gb.get((gran,k),{})
            pA=A.get('packages',0);pB=B.get('packages',0)
            rows.append([k,round(pA,6),round(pB,6),round(pB-pA,6),'' if pA==0 else round(100*(pB-pA)/pA,8),round(A.get('shipments',0),6),round(B.get('shipments',0),6)])
        write_csv(a.out/f'reconciliation_{gran}.csv',['group','a_packages','b_packages','delta_packages','delta_pct_a_denominator','a_shipments','b_shipments'],rows)
    weekkeys=sorted(set(wa)|set(wb),key=lambda z:int(z) if str(z).isdigit() else 9999)
    weekrows=[]
    for k in weekkeys:
        pA=wa.get(k,{}).get('packages',0.0);pB=wb.get(k,{}).get('packages',0.0)
        weekrows.append([k,round(pA,6),round(pB,6),round(pB-pA,6),'' if pA==0 else round(100*(pB-pA)/pA,8)])
    write_csv(a.out/'reconciliation_week.csv',['week','a_packages','b_packages','delta_packages','delta_pct_a_denominator'],weekrows)
    sumA=sum(v.get('packages',0) for (gran,k),v in ga.items() if gran=='destination')
    sumB=sum(v.get('packages',0) for (gran,k),v in gb.items() if gran=='destination')
    out={'audit_scope':'Independent direct XLSX source-snapshot arithmetic. No historical Bronze pipeline rerun or source-owner semantic validation.',
       'window_inclusive':['2024-08-01','2024-08-31'],
       'source_A':sa,'source_B':sb,
       'source_A_columns':ha,'source_B_columns':hb,
       'total_packages_by_source':{'A':sumA,'B':sumB,'relative_pct_A_denominator':100*(sumB-sumA)/sumA if sumA else None},
       'figure1_same_population':{'source':'B','original_rows':sb['selected'],'original_code_present_mapped':sb['raw_mapped'],'original_code_missing_or_unknown':sb['unresolved'],'actually_recovered':sb['recovered'],'excluded':sb['excluded_after_selection'],'after_mapped':sb['raw_mapped']+sb['recovered'],'after_unresolved':sb['unresolved'],'conservation_pass':sb['accounting_identity_pass']},
       'interpretation_notes':['Source A filter uses reporting date, Source B filter uses shipment date; no shipment-identity crosswalk demonstrated.', 'Source B unresolved rows are not recoveries.', 'The literal NA origin-group value is ambiguous without an owner taxonomy; it is separately counted, neither dropped nor assigned to a named site.', 'Measure semantics for weight need authoritative source dictionary.', 'Per-source aggregates intentionally NOT concatenated/additively summed across overlapping windows.', 'No row-level Bronze QA identifiers in these two source snapshots; marginal flags and overlap not independently verifiable.']}
    (a.out/'audit_summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    manifest={'classification':'RESTRICTED / Centre-approval required; never publish with public manuscript','audit_type':'NEW READ-ONLY SNAPSHOT ARITHMETIC (NOT full historical pipeline)','date_window':'2024-08-01 through 2024-08-31 inclusive',
      'inputs':[{'filename':p.name,'sha256':sha256(p),'source_owner_authorized_location':'PENDING: institution-controlled location and access grant','role':role} for p,role in [(a.weekly,'Source A: weekly reporting aggregate'),(a.aug,'Source B: August event-date extract')]+([(a.xlsb,'Supplementary Source C, excluded pending provenance and field-dictionary confirmation')] if a.xlsb and a.xlsb.exists() else [])],
      'environment':{'python_version':platform.python_version(),'implementation':'Python standard library: zipfile, xml.etree.ElementTree, datetime, csv, json, hashlib','platform':platform.platform()},
      'execution':'python audit_compute.py --weekly <authorized_weekly.xlsx> --aug <authorized_aug.xlsx> --xlsb <authorized_optional.xlsb> --out <restricted_dir>',
      'script':{'path':'audit_compute.py','sha256':sha256(Path(__file__))},
      'repository':'https://github.com/brpuneet898/fedex-supply-chain','repository_tree_sha_observed':'4f18a2fc2d1bd0f568ad9e074da81d5c1f0ed6f9',
      'historical_bronze_execution':'NOT CERTIFIED: existing repository canonicalization scripts differ on mapping, zero-filling, and duplicate handling; no historical fully locked end-to-end run given.',
      'independent_second_operator_rerun':'PENDING authorized independent reviewer',
      'source_dictionary_weight_comparability':'PENDING written source-owner confirmation',
      'calendar_month_event_population_equivalence':'NOT ESTABLISHED without period-allocation crosswalk',
      'source_C_included_in_main_reconciliation':False,
      'output_hashes':{name:sha256(a.out/name) for name in ['count_ledger.csv','fixed_population_before_after.csv','reconciliation_destination.csv','reconciliation_service.csv','reconciliation_origin.csv','reconciliation_week.csv','audit_summary.json']}}
    (a.out/'reproducibility_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'summary':out,'manifest_input_hashes':[(v['filename'],v['sha256']) for v in manifest['inputs']]},indent=2)[:8000])

if __name__=='__main__':main()

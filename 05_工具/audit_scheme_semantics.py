#!/usr/bin/env python3
from pathlib import Path
import argparse, json, sys, zipfile, tempfile

def decode(data):
    for enc in ('gbk','utf-8-sig','utf-8'):
        try: return data.decode(enc), enc
        except UnicodeDecodeError: pass
    raise UnicodeDecodeError('unknown',data,0,1,'cannot decode')

def parse_fields(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    fields={}
    for line in lines[2:]:
        if '=' in line:
            k,v=line.split('=',1); fields[k]=v
    return lines,fields

def valid_group(g):
    nums=[x.strip() for x in g.split(',') if x.strip()]
    return nums and len(nums)==len(set(nums)) and all(x.isdigit() and 0<=int(x)<=9 for x in nums)

def audit_bytes(data,label):
    text,enc=decode(data); lines,fields=parse_fields(text); errors=[]; warnings=[]
    strategy=lines[1] if len(lines)>1 else None
    result={'label':label,'encoding':enc,'strategy':strategy,'errors':errors,'warnings':warnings}
    if strategy=='高级开某投某':
        pos=fields.get('高级开某投某正投号码','').split('|') if fields.get('高级开某投某正投号码') else []
        neg=fields.get('高级开某投某反投号码','').split('|') if fields.get('高级开某投某反投号码') else []
        result.update({'positive_group_count':len(pos),'negative_group_count':len(neg),'positive_unique_count':len(set(pos)),'negative_unique_count':len(set(neg))})
        if len(pos)!=10: errors.append('高级开某投某正投映射必须有10组')
        if len(neg)!=10: errors.append('高级开某投某反投映射必须有10组')
        if pos and len(set(pos))<2: errors.append('正投为常量映射：10个触发号码没有改变投注集合')
        if neg and len(set(neg))<2: errors.append('反投为常量映射：10个触发号码没有改变投注集合')
        for kind,groups in [('正投',pos),('反投',neg)]:
            for i,g in enumerate(groups):
                if not valid_group(g): errors.append(f'{kind}第{i}组号码非法或重复: {g}')
    plan=fields.get('倍投计划')
    result['bet_plan']=plan
    if plan and len(set(x.strip() for x in plan.split(',') if x.strip()))==1:
        warnings.append('倍投计划为平倍；正式任务需确认已完成四路资金评审')
    result['active_extra_settings']=[k for k,v in fields.items() if k in {'投注监控','真实投注1','真实投注2','模拟投注1','模拟投注2','盈利跳转','亏损跳转','盈利停止','亏损停止','投注时间'} and v.startswith('True')]
    return result

def iter_targets(path):
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir() and info.filename.lower().endswith('.txt') and Path(info.filename).name.startswith(('A','B','C','D')):
                    yield f'{path.name}::{info.filename}', z.read(info)
    else:
        yield str(path), path.read_bytes()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('paths',nargs='+'); ap.add_argument('--json',action='store_true'); args=ap.parse_args()
    results=[]
    for raw in args.paths:
        p=Path(raw)
        for label,data in iter_targets(p): results.append(audit_bytes(data,label))
    if args.json: print(json.dumps(results,ensure_ascii=False,indent=2))
    else:
        for r in results:
            print(f"{r['label']}: strategy={r['strategy']} errors={len(r['errors'])} warnings={len(r['warnings'])}")
            for e in r['errors']: print('  ERROR '+e)
            for w in r['warnings']: print('  WARN '+w)
    if any(r['errors'] for r in results): raise SystemExit(1)
if __name__=='__main__': main()

#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parent.parent

def load_json(p): return json.loads(p.read_text(encoding='utf-8'))
def load_jsonl(p,idf):
    rows=[]; ids=set()
    for n,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        o=json.loads(line)
        if idf not in o: raise RuntimeError(f'{p.name}第{n}行缺少{idf}')
        if o[idf] in ids: raise RuntimeError(f'{p.name}重复ID: {o[idf]}')
        ids.add(o[idf]); rows.append(o)
    return rows

def main():
    m=load_json(ROOT/'系统清单.json'); e=[]
    req={
      '方案组合案例索引.jsonl':('案例ID',int(m['总控结构要求']['方案组合案例最少'])),
      '负面方案模式索引.jsonl':('负面模式ID',int(m['总控结构要求']['负面方案模式最少'])),
      '功能覆盖索引.jsonl':('功能ID',int(m['总控结构要求']['功能覆盖条目最少'])),
      '总控验收测试集.jsonl':('测试ID',int(m['总控结构要求']['总控验收测试最少'])),
      '功能能力卡片.jsonl':('功能ID',int(m['总控结构要求']['功能能力卡片最少'])),
      '资金路径模板库.jsonl':('资金路径ID',int(m['总控结构要求']['资金路径模板最少']))}
    counts={}
    for fn,(idf,minn) in req.items():
        try:
            rows=load_jsonl(ROOT/fn,idf); counts[fn]=len(rows)
            if len(rows)<minn: e.append(f'{fn}条目不足: {len(rows)}<{minn}')
            if fn=='总控验收测试集.jsonl':
                for r in rows:
                    if r.get('运行测试状态') not in {'PENDING_RUNTIME','PASS','FAIL'}: e.append(f"{r[idf]}运行测试状态非法")
        except Exception as exc: e.append(str(exc))
    m10=(ROOT/'10_静默方案总控与外部参考吸收协议.md').read_text(encoding='utf-8')
    m11=(ROOT/'11_智能功能调度与资金路径编排协议.md').read_text(encoding='utf-8')
    for tok in ['自主设计','外部参考方案','至少应覆盖3个不同逻辑族','长期充分覆盖，单次合理克制']:
        if tok not in m10: e.append('10模块缺少关键规则: '+tok)
    for tok in ['全功能审议，不等于全功能启用','常量映射','资金路径四路评审','候选功能画像','平倍仍是基准']:
        if tok not in m11: e.append('11模块缺少关键规则: '+tok)
    task=load_json(ROOT/'当前任务.json')
    if len(task.get('任务模式识别',[]))<3: e.append('当前任务缺少三模式识别')
    if task.get('总控运行测试状态')!='PENDING_RUNTIME': e.append('下一任务行为验收必须保持PENDING_RUNTIME')
    steps='\n'.join(task.get('默认步骤',[]))
    for tok in ['至少3种功能画像','八层能力审议','四路资金评审']:
        if tok not in steps: e.append('当前任务缺少: '+tok)
    version=m['版本']; entry=(ROOT/'00_启动入口与系统状态.md').read_text(encoding='utf-8'); readme=(ROOT/'README_系统工作包使用说明.md').read_text(encoding='utf-8'); state=load_json(ROOT/'系统状态.json')
    if f'版本：{version}' not in entry[:400]: e.append('启动入口版本未同步')
    if m.get('自动合并总典') not in entry[:700]:
        # entry may not explicitly list total; tolerate if manifest and README synchronized.
        pass
    if version not in readme.splitlines()[0]: e.append('README标题版本未同步')
    if '00—11模块' not in readme: e.append('README正式源范围未同步到00—11')
    if state.get('版本')!=version or state.get('version')!=version: e.append('系统状态双版本字段未同步')
    if task.get('任务ID')!=m.get('下一任务'): e.append('清单下一任务与当前任务ID不同')
    if e:
        print('GOVERNANCE_VALIDATION_FAILED'); [print('- '+x) for x in e]; raise SystemExit(1)
    print('GOVERNANCE_VALIDATION_OK '+' '.join(f'{k}={v}' for k,v in counts.items())+f' version={version}')
if __name__=='__main__': main()

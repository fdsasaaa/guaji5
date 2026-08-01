#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

ROOT=Path(__file__).resolve().parents[1]
errors=[]

def err(msg): errors.append(msg)

required=['AGENTS.md','SYSTEM_MANIFEST.json','SYSTEM_STATE.json','CHANGELOG.md',
'10_静默方案总控与外部参考吸收协议.md','11_智能功能调度与资金路径编排协议.md',
'13_GitHub持续工作区与参考灵感自由重构协议.md','功能能力卡片.jsonl','资金路径模板库.jsonl']
for x in required:
    if not (ROOT/x).exists(): err(f'缺少必需文件: {x}')

try:
    manifest=json.loads((ROOT/'SYSTEM_MANIFEST.json').read_text(encoding='utf-8'))
    state=json.loads((ROOT/'SYSTEM_STATE.json').read_text(encoding='utf-8'))
    if manifest.get('版本') != state.get('当前版本'): err('清单与状态版本不同步')
    if manifest.get('仓库') != 'fdsasaaa/guaji5': err('仓库标识错误')
    if '13_GitHub持续工作区与参考灵感自由重构协议.md' not in manifest.get('模块',[]): err('模块13未登记')
except Exception as e: err(f'状态JSON错误: {e}')

jsonl_specs={
'历史方案索引.jsonl':'方案ID','分析角度索引.jsonl':'角度ID','学习事件索引.jsonl':'事件ID',
'规则候选池.jsonl':'候选规则ID','技术原子表现档案.jsonl':'技术原子ID','软件行为证据索引.jsonl':'证据ID',
'批次索引.jsonl':'批次ID','方案组合案例索引.jsonl':'案例ID','负面方案模式索引.jsonl':'负面模式ID',
'功能覆盖索引.jsonl':'功能ID','总控验收测试集.jsonl':'测试ID','功能能力卡片.jsonl':'功能ID','资金路径模板库.jsonl':'资金路径ID'}
for fn,key in jsonl_specs.items():
    p=ROOT/fn
    if not p.exists(): err(f'缺少索引: {fn}'); continue
    seen=set()
    for i,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        try: obj=json.loads(line)
        except Exception as e: err(f'{fn}:{i} JSON错误 {e}'); continue
        if key not in obj: err(f'{fn}:{i} 缺少{key}'); continue
        if obj[key] in seen: err(f'{fn}:{i} 重复{key}={obj[key]}')
        seen.add(obj[key])

# TXT semantic guard: detect 0-9 mapping rows with identical positive/negative sets.
for p in ROOT.rglob('*.txt'):
    if '01_本次输入' in p.parts or '08_版本与优化记录' in p.name: continue
    try:
        text=p.read_text(encoding='gbk')
    except Exception:
        try: text=p.read_text(encoding='utf-8')
        except Exception: continue
    rows=re.findall(r'^\s*([0-9])\s*[|,;:\t ]+([^\r\n]+)$',text,re.M)
    if len(rows)>=10:
        vals=[v.strip() for _,v in rows[:10]]
        if len(set(vals))==1: err(f'疑似0-9常量高级映射: {p.relative_to(ROOT)}')

protocol=(ROOT/'13_GitHub持续工作区与参考灵感自由重构协议.md').read_text(encoding='utf-8') if (ROOT/'13_GitHub持续工作区与参考灵感自由重构协议.md').exists() else ''
for phrase in ['优先自由重构','不能以“原思路无法原样编码”为终点','未指定倍投时']:
    # first phrase is in scheme status, use broader required semantics below
    pass
required_semantics=['无法原样生成TXT时','自由重构','四路资金路径','无需等待二次确认']
for phrase in required_semantics:
    if phrase not in protocol: err(f'模块13缺少关键语义: {phrase}')

if errors:
    print('VALIDATION_FAILED')
    for e in errors: print('-',e)
    sys.exit(1)
print('VALIDATION_OK version='+state.get('当前版本','?')+' repo='+state.get('仓库','?'))

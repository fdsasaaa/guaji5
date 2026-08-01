#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, subprocess, sys, zipfile

ROOT=Path(__file__).resolve().parent.parent

def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load_json(path): return json.loads(path.read_text(encoding='utf-8'))
def parse_jsonl(path,id_field):
    ids=set(); count=0
    for lineno,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        obj=json.loads(line)
        if id_field not in obj: raise RuntimeError(f'{path.name}第{lineno}行缺少{id_field}')
        if obj[id_field] in ids: raise RuntimeError(f'{path.name}重复ID: {obj[id_field]}')
        ids.add(obj[id_field]); count+=1
    return count

def decode_scheme(data):
    for enc in ('gbk','utf-8-sig','utf-8'):
        try: return data.decode(enc)
        except UnicodeDecodeError: pass
    raise RuntimeError('无法解码方案TXT')

def check_creator(text,label,allow,errors):
    vals=[x.split('=',1)[1].strip() for x in text.splitlines() if x.startswith('SchemeCreator=')]
    if not vals: errors.append(f'方案缺少SchemeCreator字段: {label}'); return
    if len(vals)!=1: errors.append(f'方案SchemeCreator字段数量异常: {label}')
    if any(vals) and not allow: errors.append(f'默认未加密规则失败：SchemeCreator非空: {label}')

def main():
    m=load_json(ROOT/'系统清单.json'); errors=[]
    for name in m['模块']:
        if not (ROOT/name).is_file(): errors.append(f'缺少模块: {name}')
    for item in m['总典附录']:
        if not (ROOT/item['file']).is_file(): errors.append(f"缺少附录: {item['file']}")
    for name in m['必需目录']:
        if not (ROOT/name).is_dir(): errors.append(f'缺少目录: {name}')
    for name in m['工具']:
        if not (ROOT/name).is_file(): errors.append(f'缺少工具: {name}')
    try:
        counts={
          'history':parse_jsonl(ROOT/'历史方案索引.jsonl','方案ID'),'angles':parse_jsonl(ROOT/'分析角度索引.jsonl','角度ID'),
          'learning':parse_jsonl(ROOT/'学习事件索引.jsonl','事件ID'),'rules':parse_jsonl(ROOT/'规则候选池.jsonl','候选规则ID'),
          'atoms':parse_jsonl(ROOT/'技术原子表现档案.jsonl','技术原子ID'),'software':parse_jsonl(ROOT/'软件行为证据索引.jsonl','证据ID'),
          'batches':parse_jsonl(ROOT/'批次索引.jsonl','批次ID'),'cases':parse_jsonl(ROOT/'方案组合案例索引.jsonl','案例ID'),
          'negative_patterns':parse_jsonl(ROOT/'负面方案模式索引.jsonl','负面模式ID'),'coverage':parse_jsonl(ROOT/'功能覆盖索引.jsonl','功能ID'),
          'director_tests':parse_jsonl(ROOT/'总控验收测试集.jsonl','测试ID'),'function_cards':parse_jsonl(ROOT/'功能能力卡片.jsonl','功能ID'),
          'money_paths':parse_jsonl(ROOT/'资金路径模板库.jsonl','资金路径ID')}
    except Exception as exc: errors.append(str(exc)); counts={}

    delivery=ROOT/'02_本次输出'; scheme_zips=[p for p in delivery.glob('*.zip') if '方案' in p.name or 'SET' in p.name]
    scheme_txts=[p for p in delivery.rglob('*.txt') if p.name.startswith(('A','B','C','D'))]
    ppts=list(delivery.glob('*.pptx')); build_type=m.get('本次构建类型','STANDARD_SCHEME_TASK')
    req=m.get('交付完整性要求',{}).get(build_type,{})
    if len(scheme_zips)<int(req.get('方案包ZIP最少',0)): errors.append('交付不完整：缺少实际挂机方案ZIP')
    if len(scheme_txts)<int(req.get('挂机方案TXT最少',0)): errors.append('交付不完整：缺少可直接导入TXT')
    if len(ppts)<int(req.get('讲解PPTX最少',0)): errors.append('交付不完整：缺少讲解PPTX')
    if build_type=='SYSTEM_UPGRADE_ONLY':
        upgrades=list(delivery.glob('*升级说明*.md'))
        if len(upgrades)<int(req.get('升级说明最少',1)): errors.append('系统升级任务缺少升级说明')

    task=load_json(ROOT/'当前任务.json'); allow=bool(task.get('允许SchemeCreator非空',False))
    targets=[]
    for p in scheme_txts:
        try: text=decode_scheme(p.read_bytes()); check_creator(text,p.relative_to(ROOT).as_posix(),allow,errors); targets.append(str(p))
        except Exception as exc: errors.append(f'无法检查方案TXT: {p}: {exc}')
    for zpath in scheme_zips:
        try:
            with zipfile.ZipFile(zpath) as z:
                members=[i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith('.txt') and Path(i.filename).name.startswith(('A','B','C','D'))]
                if not members: errors.append(f'方案ZIP内缺少可导入TXT: {zpath.name}')
                for info in members: check_creator(decode_scheme(z.read(info)),f'{zpath.name}::{info.filename}',allow,errors)
            targets.append(str(zpath))
        except Exception as exc: errors.append(f'无法检查方案ZIP: {zpath.name}: {exc}')
    if targets:
        proc=subprocess.run([sys.executable,str(ROOT/'05_工具/audit_scheme_semantics.py'),*targets],text=True,capture_output=True)
        if proc.returncode!=0: errors.append('方案语义审计失败: '+(proc.stdout.strip() or proc.stderr.strip()))

    state=load_json(ROOT/'系统状态.json')
    if state.get('版本')!=m.get('版本'): errors.append('系统状态版本与系统清单不同')
    if state.get('当前任务ID')!=task.get('任务ID'): errors.append('系统状态当前任务ID与当前任务.json不同')
    if state.get('正式源已同步') is not True: errors.append('系统状态未标记正式源同步')
    for tool in ['build_total.py','validate_governance.py']:
        proc=subprocess.run([sys.executable,str(ROOT/'05_工具'/tool),'--check'] if tool=='build_total.py' else [sys.executable,str(ROOT/'05_工具'/tool)],text=True,capture_output=True)
        if proc.returncode!=0: errors.append(f'{tool}失败: '+(proc.stderr.strip() or proc.stdout.strip()))
    hp=ROOT/'系统哈希清单.sha256'
    if not hp.exists(): errors.append('缺少系统哈希清单')
    else:
        for line in hp.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            expected,rel=line.split('  ',1); p=ROOT/rel
            if not p.exists(): errors.append(f'哈希目标缺失: {rel}')
            elif sha256(p)!=expected: errors.append(f'哈希不一致: {rel}')
    if errors:
        print('VALIDATION_FAILED'); [print('- '+e) for e in errors]; raise SystemExit(1)
    print('VALIDATION_OK '+' '.join(f'{k}={v}' for k,v in counts.items())+f" version={m['版本']} build_type={build_type} task={task['任务ID']}")
if __name__=='__main__': main()

#!/usr/bin/env python3
from pathlib import Path
import argparse, json, sys, zipfile

PLAY_TYPES={
    '定位胆','前三','后三','中三','前二','后二','任二','任三','任四',
    '前四','后四','五星','不定位','龙虎','新龙虎','趣味','混合组选'
}
COMMON_REQUIRED=[
    '软件名称','玩法类型','玩法名称','金额模式','投注监控','投注监控模式',
    '任选中奖','任选位置','换号规则','换号期数','翻倍方式','正集',
    '倍投类型','倍投计划','倍投方案','显示更多',
    '真实投注1','真实投注2','模拟投注1','模拟投注2',
    '盈利跳转','亏损跳转','盈利停止','亏损停止',
    '投注时间','投注时间类型','范围开始时间','范围停止时间',
    '范围停止类型','倒计时停止时间','倒计时停止类型','SchemeCreator'
]
ADVANCED_FIELD_ORDER=[
    '软件名称','ID','倍数','中后ID','挂后ID','中后监控','中后跳转','挂后监控','挂后跳转'
]

def decode(data):
    if data.startswith(b'\xef\xbb\xbf'):
        return data.decode('utf-8-sig'), 'utf-8-sig'
    for enc in ('gbk','utf-8'):
        try: return data.decode(enc), enc
        except UnicodeDecodeError: pass
    raise UnicodeDecodeError('unknown',data,0,1,'cannot decode')

def only_crlf(data):
    body=data[3:] if data.startswith(b'\xef\xbb\xbf') else data
    return b'\n' not in body.replace(b'\r\n',b'') and b'\r' not in body.replace(b'\r\n',b'')

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

def parse_positive_sequence(raw):
    vals=[]
    for item in raw.split(','):
        item=item.strip()
        if not item or not item.isdigit() or int(item)<=0: return None
        vals.append(int(item))
    return vals or None

def audit_advanced_config(data,label,config_name):
    errors=[]
    if not data.startswith(b'\xef\xbb\xbf'): errors.append('高级倍投配置必须为UTF-8 BOM')
    if not only_crlf(data): errors.append('高级倍投配置必须全部使用CRLF换行')
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        return {'label':label,'errors':[f'高级倍投配置无法按UTF-8 BOM解码: {exc}']}
    rows=[x for x in text.split('\r\n') if x.strip()]; parsed=[]
    for row_no,row in enumerate(rows,1):
        parts=row.split(';')
        if len(parts)!=9:
            errors.append(f'高级倍投第{row_no}局必须有9个字段，实际{len(parts)}个'); continue
        keys=[]; vals={}
        for part in parts:
            if '=' not in part:
                errors.append(f'高级倍投第{row_no}局字段缺少等号: {part}'); continue
            k,v=part.split('=',1); keys.append(k); vals[k]=v
        if keys!=ADVANCED_FIELD_ORDER:
            errors.append(f'高级倍投第{row_no}局字段顺序错误: {keys}'); continue
        parsed.append(vals)
    ids=[]
    for row_no,vals in enumerate(parsed,1):
        for key in ('ID','倍数','中后ID','挂后ID'):
            if not vals[key].isdigit(): errors.append(f'高级倍投第{row_no}局{key}必须为正整数')
        if vals['ID'].isdigit(): ids.append(int(vals['ID']))
        if vals['倍数'].isdigit() and int(vals['倍数'])<=0: errors.append(f'高级倍投第{row_no}局倍数不得小于1')
        for key in ('中后监控','挂后监控'):
            if vals[key]!='False': errors.append(f'高级倍投第{row_no}局{key}=True尚未达到正式证据门槛')
        for key in ('中后跳转','挂后跳转'):
            expected=f'False-{config_name}'
            if vals[key]!=expected: errors.append(f'高级倍投第{row_no}局{key}必须为{expected}')
    if ids:
        if ids!=list(range(1,len(ids)+1)): errors.append(f'高级倍投ID必须从1连续递增: {ids}')
        idset=set(ids)
        for row_no,vals in enumerate(parsed,1):
            for key in ('中后ID','挂后ID'):
                if vals[key].isdigit() and int(vals[key]) not in idset:
                    errors.append(f'高级倍投第{row_no}局{key}指向不存在的ID={vals[key]}')
    return {'label':label,'row_count':len(rows),'errors':errors}

def audit_bytes(data,label,advanced_lookup=None):
    text,enc=decode(data); lines,fields=parse_fields(text); errors=[]; warnings=[]
    strategy=lines[1] if len(lines)>1 else None
    result={'label':label,'encoding':enc,'strategy':strategy,'errors':errors,'warnings':warnings}
    if enc!='gbk': errors.append(f'主方案必须为GBK无BOM，实际{enc}')
    if not only_crlf(data): errors.append('主方案必须全部使用CRLF换行')
    if not data.endswith(b'\r\n\r\n'): errors.append('主方案末尾必须保留两个CRLF')
    if not lines or lines[0] not in {'True','False'}: errors.append('主方案第1行必须为True或False')
    if not strategy: errors.append('主方案缺少第2行一级策略名')
    elif strategy in PLAY_TYPES: errors.append(f'主方案第2行误用玩法类型“{strategy}”，必须填写一级策略名')
    for key in COMMON_REQUIRED:
        if key not in fields: errors.append(f'主方案缺少通用字段: {key}')
    if '投注内容' in fields: errors.append('检测到未验证的通用字段“投注内容”；必须使用对应一级策略的专属内容字段')
    if strategy=='定码轮换':
        if not fields.get('定码轮换内容','').strip(): errors.append('定码轮换缺少非空的定码轮换内容')
        if '定码轮换单组' not in fields: errors.append('定码轮换缺少定码轮换单组字段')
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
    plan=fields.get('倍投计划',''); result['bet_plan']=plan
    seq=parse_positive_sequence(plan) if plan else None
    if not seq: errors.append('倍投计划必须为非空正整数逗号序列')
    elif len(set(seq))==1: warnings.append('倍投计划为平倍；正式任务需确认已完成四路资金评审')
    betting_type=fields.get('倍投类型'); betting_scheme=fields.get('倍投方案','').strip()
    if betting_type=='1':
        if not betting_scheme: errors.append('高级倍投的倍投方案不得为空')
        elif ',' in betting_scheme: errors.append('高级倍投的倍投方案必须是配置名，不能写倍率序列')
        elif advanced_lookup is None: errors.append('高级倍投主方案缺少可核验的GJBTScheme上下文')
        else:
            advanced_data=advanced_lookup(betting_scheme)
            if advanced_data is None: errors.append(f'缺少GJBTScheme/{betting_scheme}.txt')
            else:
                ar=audit_advanced_config(advanced_data,f'{label}::GJBTScheme/{betting_scheme}.txt',betting_scheme)
                result['advanced_config']=ar; errors.extend(ar['errors'])
    elif betting_type=='0':
        if not betting_scheme: warnings.append('普通倍投的倍投方案为空，部分软件版本可能解析异常')
    elif betting_type is not None: errors.append(f'倍投类型只能为0或1，实际{betting_type}')
    result['active_extra_settings']=[k for k,v in fields.items() if k in {'投注监控','真实投注1','真实投注2','模拟投注1','模拟投注2','盈利跳转','亏损跳转','盈利停止','亏损停止','投注时间'} and v.startswith('True')]
    return result

def iter_targets(path):
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            members={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
            def lookup(name):
                wanted=f'GJBTScheme/{name}.txt'
                for member,data in members.items():
                    if member.replace('\\','/').endswith(wanted): return data
                return None
            for name,data in members.items():
                if name.lower().endswith('.txt') and Path(name).name.startswith(('A','B','C','D')):
                    yield f'{path.name}::{name}',data,lookup
    else:
        def lookup(name):
            p=path.parent/'GJBTScheme'/f'{name}.txt'
            return p.read_bytes() if p.is_file() else None
        yield str(path),path.read_bytes(),lookup

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('paths',nargs='+'); ap.add_argument('--json',action='store_true'); args=ap.parse_args()
    results=[]
    for raw in args.paths:
        for label,data,lookup in iter_targets(Path(raw)): results.append(audit_bytes(data,label,lookup))
    if args.json: print(json.dumps(results,ensure_ascii=False,indent=2))
    else:
        for r in results:
            print(f"{r['label']}: strategy={r['strategy']} errors={len(r['errors'])} warnings={len(r['warnings'])}")
            for e in r['errors']: print('  ERROR '+e)
            for w in r['warnings']: print('  WARN '+w)
    if any(r['errors'] for r in results): raise SystemExit(1)
if __name__=='__main__': main()

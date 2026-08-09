#!/usr/bin/env python3
from pathlib import Path
import argparse, json, re, sys, zipfile

ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY = ROOT / 'scheme_import_safety.json'


def load_registry(path=None):
    p = Path(path) if path else DEFAULT_REGISTRY
    if not p.exists():
        return {
            'invalid_second_line_tokens': ['定位胆','龙虎','新龙虎','五星','前三','后三','前二','后二','中三','任二','任三','任四','前四','组选24','组选120','直选复式','直选单式'],
            'required_common_fields': ['软件名称','玩法类型','玩法名称','金额模式','任选中奖','任选位置','换号规则','换号期数','翻倍方式','正集','倍投类型','倍投计划','倍投方案','显示更多','投注时间','SchemeCreator'],
            'strategy_required_fields': {
                '定码轮换':['定码轮换内容'],
                '高级定码轮换':['高级定码轮换内容'],
                '开某投某':['开某投某类型','开某投某号码','开某投某内容'],
                '组合方案出号':['组合方案出号内容','组合方案出号中几中奖'],
                '组合方案轮投':['组合方案轮投内容']
            },
            'advanced_betting': {
                'directory':'GJBTScheme',
                'fields':['软件名称','ID','倍数','中后ID','挂后ID','中后监控','中后跳转','挂后监控','挂后跳转']
            }
        }
    return json.loads(p.read_text(encoding='utf-8'))


def decode_scheme(data):
    if data.startswith(b'\xef\xbb\xbf'):
        return data.decode('utf-8-sig'), 'utf-8-sig'
    for enc in ('gbk','utf-8'):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError('unknown', data, 0, 1, 'cannot decode')


def has_strict_crlf(data):
    if b'\n' not in data:
        return False
    return data.replace(b'\r\n', b'').find(b'\n') < 0


def parse_fields(text):
    raw_lines = text.splitlines()
    lines = [x.strip() for x in raw_lines if x.strip()]
    pairs=[]; fields={}; duplicates=[]
    for line in lines[2:]:
        if '=' not in line:
            continue
        k,v=line.split('=',1)
        k=k.strip(); v=v.strip()
        if k in fields:
            duplicates.append(k)
        fields[k]=v
        pairs.append((k,v))
    return lines, fields, duplicates


def positive_number_list(value):
    vals=[x.strip() for x in value.split(',') if x.strip()]
    if not vals:
        return False
    try:
        return all(float(x)>0 for x in vals)
    except ValueError:
        return False


def valid_group(g):
    nums=[x.strip() for x in g.split(',') if x.strip()]
    return nums and len(nums)==len(set(nums)) and all(x.isdigit() and 0<=int(x)<=9 for x in nums)


def check_front2_content(content, errors, result):
    groups=[g.strip() for g in content.split(';') if g.strip()]
    counts=[]
    for idx,g in enumerate(groups,1):
        parts=g.split('-')
        if len(parts)!=2:
            errors.append(f'前二直选复式第{idx}段必须正好2个位置并用-分隔: {g}')
            continue
        if any(not p or not p.isdigit() for p in parts):
            errors.append(f'前二直选复式第{idx}段只能使用数字: {g}')
            continue
        if any(len(set(p))!=len(p) for p in parts):
            errors.append(f'前二直选复式第{idx}段单位置存在重复数字: {g}')
            continue
        if any(any(ch not in '0123456789' for ch in p) for p in parts):
            errors.append(f'前二直选复式第{idx}段存在非法数字: {g}')
            continue
        counts.append(len(parts[0])*len(parts[1]))
    if counts:
        result['estimated_bet_count_per_segment']=counts


def audit_scheme_bytes(data,label,registry):
    text,enc=decode_scheme(data)
    lines,fields,duplicates=parse_fields(text)
    errors=[]; warnings=[]
    strategy=lines[1] if len(lines)>1 else None
    result={'kind':'scheme','label':label,'encoding':enc,'strategy':strategy,'errors':errors,'warnings':warnings}

    if enc!='gbk':
        errors.append(f'主方案TXT必须GBK，当前={enc}')
    if not has_strict_crlf(data):
        errors.append('主方案TXT必须使用CRLF换行')
    if len(lines)<2:
        errors.append('方案至少需要第1行启用状态和第2行一级分类')
        return result
    if lines[0] not in {'True','False'}:
        errors.append(f'第1行必须为True或False，当前={lines[0]}')
    if not strategy:
        errors.append('第2行一级分类不能为空')
    invalid=set(registry.get('invalid_second_line_tokens',[]))
    if strategy in invalid:
        errors.append(f'第2行把玩法类型/玩法名称误作一级分类: {strategy}')

    if duplicates:
        errors.append('存在重复字段: '+','.join(sorted(set(duplicates))))
    for key in registry.get('required_common_fields',[]):
        if key not in fields:
            errors.append(f'缺少通用必填字段: {key}')
    for key in registry.get('strategy_required_fields',{}).get(strategy,[]):
        if not fields.get(key,''):
            errors.append(f'{strategy}缺少或留空专属字段: {key}')

    if fields.get('SchemeCreator',''):
        errors.append('SchemeCreator默认必须为空')

    bet_type=fields.get('倍投类型')
    result['bet_type']=bet_type
    plan=fields.get('倍投计划','')
    result['bet_plan']=plan
    if plan and not positive_number_list(plan):
        errors.append('倍投计划必须为逗号分隔的有效正数序列')
    if bet_type not in {None,'0','1'}:
        errors.append(f'倍投类型只能为0或1，当前={bet_type}')
    if bet_type=='1':
        if not fields.get('倍投方案','').strip():
            errors.append('高级倍投已启用但倍投方案为空')
        result['advanced_plan_name']=fields.get('倍投方案','').strip()
    elif bet_type=='0' and not fields.get('倍投方案','').strip():
        warnings.append('普通倍投的倍投方案为空；历史上该空值曾导致解析异常，建议保留有效值')

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

    if strategy=='定码轮换' and fields.get('玩法类型')=='前二' and fields.get('玩法名称')=='直选复式':
        check_front2_content(fields.get('定码轮换内容',''),errors,result)

    result['active_extra_settings']=[k for k,v in fields.items() if k in {'投注监控','真实投注1','真实投注2','模拟投注1','模拟投注2','盈利跳转','亏损跳转','盈利停止','亏损停止','投注时间'} and v.startswith('True')]
    return result


def parse_adv_line(line, expected_keys):
    parts=line.split(';')
    if len(parts)!=len(expected_keys):
        raise ValueError(f'应有{len(expected_keys)}字段，实际{len(parts)}')
    vals={}
    order=[]
    for part in parts:
        if '=' not in part:
            raise ValueError(f'字段缺少=: {part}')
        k,v=part.split('=',1)
        order.append(k); vals[k]=v
    if order!=expected_keys:
        raise ValueError('9字段顺序不匹配: '+','.join(order))
    return vals


def audit_advanced_bytes(data,label,registry):
    adv=registry.get('advanced_betting',{})
    keys=adv.get('fields',['软件名称','ID','倍数','中后ID','挂后ID','中后监控','中后跳转','挂后监控','挂后跳转'])
    errors=[]; warnings=[]
    result={'kind':'advanced','label':label,'encoding':None,'errors':errors,'warnings':warnings}
    if not data.startswith(b'\xef\xbb\xbf'):
        errors.append('高级倍投配置必须UTF-8 BOM')
        try: text=data.decode('utf-8')
        except UnicodeDecodeError:
            text=''
        result['encoding']='utf-8'
    else:
        text=data.decode('utf-8-sig')
        result['encoding']='utf-8-sig'
    if not has_strict_crlf(data):
        errors.append('高级倍投配置必须使用CRLF换行')
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    if not lines:
        errors.append('高级倍投配置不能为空')
        return result
    rows=[]
    for lineno,line in enumerate(lines,1):
        try:
            vals=parse_adv_line(line,keys)
            rows.append(vals)
        except Exception as exc:
            errors.append(f'第{lineno}行结构错误: {exc}')
    if not rows:
        return result
    ids=[]
    for lineno,r in enumerate(rows,1):
        for k in ('ID','倍数','中后ID','挂后ID'):
            if not re.fullmatch(r'\d+',r.get(k,'')):
                errors.append(f'第{lineno}行{k}必须为正整数: {r.get(k)}')
        try:
            sid=int(r['ID']); mult=int(r['倍数'])
            ids.append(sid)
            if sid<1: errors.append(f'第{lineno}行ID必须>=1')
            if mult<1: errors.append(f'第{lineno}行倍数必须>=1')
        except Exception:
            continue
        if r.get('软件名称')!='CXGGJ':
            warnings.append(f'第{lineno}行软件名称不是CXGGJ: {r.get("软件名称")}')
        if r.get('中后监控')!='False' or r.get('挂后监控')!='False':
            errors.append(f'第{lineno}行高级倍投监控必须False，当前规则禁止正式启用')
        if not r.get('中后跳转','').startswith('False-') or not r.get('挂后跳转','').startswith('False-'):
            errors.append(f'第{lineno}行高级倍投跳转必须False-方案名，当前规则禁止正式启用True跳转')
    if ids:
        expected=list(range(1,len(rows)+1))
        if ids!=expected:
            errors.append(f'高级倍投ID必须从1连续递增，当前前后={ids[:5]}...{ids[-5:]}')
        valid=set(ids)
        for lineno,r in enumerate(rows,1):
            try:
                if int(r['中后ID']) not in valid: errors.append(f'第{lineno}行中后ID越界: {r["中后ID"]}')
                if int(r['挂后ID']) not in valid: errors.append(f'第{lineno}行挂后ID越界: {r["挂后ID"]}')
            except Exception:
                pass
    result['state_count']=len(rows)
    result['max_multiplier']=max((int(r['倍数']) for r in rows if str(r.get('倍数','')).isdigit()), default=None)
    result['total_multiplier']=sum((int(r['倍数']) for r in rows if str(r.get('倍数','')).isdigit()), 0)
    return result


def is_probable_scheme_member(info):
    if info.is_dir() or not info.filename.lower().endswith('.txt'):
        return False
    p=Path(info.filename)
    if 'GJBTScheme' in p.parts:
        return False
    name=p.name
    if name.startswith(('README','YouTube','SHA256','说明','验证','资金','号码')):
        return False
    return name.startswith(('A','B','C','D'))


def audit_zip(path,registry):
    results=[]
    adv_dir=registry.get('advanced_betting',{}).get('directory','GJBTScheme')
    with zipfile.ZipFile(path) as z:
        infos=[i for i in z.infolist() if not i.is_dir()]
        names={i.filename:i for i in infos}
        scheme_results=[]
        for info in infos:
            p=Path(info.filename)
            if p.suffix.lower()=='.txt' and adv_dir in p.parts:
                results.append(audit_advanced_bytes(z.read(info),f'{path.name}::{info.filename}',registry))
            elif is_probable_scheme_member(info):
                r=audit_scheme_bytes(z.read(info),f'{path.name}::{info.filename}',registry)
                r['_member_path']=info.filename
                scheme_results.append(r); results.append(r)
        if not scheme_results:
            results.append({'kind':'bundle','label':path.name,'errors':['ZIP内未识别到A/B/C/D开头的主方案TXT'],'warnings':[]})
        for r in scheme_results:
            if r.get('bet_type')!='1':
                continue
            plan=r.get('advanced_plan_name')
            if not plan:
                continue
            p=Path(r['_member_path'])
            expected=(p.parent / adv_dir / f'{plan}.txt').as_posix()
            if expected not in names:
                r['errors'].append(f'高级倍投关联文件缺失: {expected}')
    for r in results:
        r.pop('_member_path',None)
    return results


def iter_file(path,registry):
    data=path.read_bytes()
    if path.parent.name==registry.get('advanced_betting',{}).get('directory','GJBTScheme'):
        return [audit_advanced_bytes(data,str(path),registry)]
    return [audit_scheme_bytes(data,str(path),registry)]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('paths',nargs='+'); ap.add_argument('--json',action='store_true'); ap.add_argument('--registry'); args=ap.parse_args()
    registry=load_registry(args.registry)
    results=[]
    for raw in args.paths:
        p=Path(raw)
        if not p.exists():
            results.append({'kind':'input','label':str(p),'errors':['目标不存在'],'warnings':[]}); continue
        if p.suffix.lower()=='.zip': results.extend(audit_zip(p,registry))
        else: results.extend(iter_file(p,registry))
    if args.json: print(json.dumps(results,ensure_ascii=False,indent=2))
    else:
        for r in results:
            print(f"{r['label']}: kind={r.get('kind')} strategy={r.get('strategy')} errors={len(r.get('errors',[]))} warnings={len(r.get('warnings',[]))}")
            for e in r.get('errors',[]): print('  ERROR '+e)
            for w in r.get('warnings',[]): print('  WARN '+w)
    if any(r.get('errors') for r in results): raise SystemExit(1)

if __name__=='__main__': main()

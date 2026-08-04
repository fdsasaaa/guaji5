#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
ROOT=Path(__file__).resolve().parents[1]; errors=[]
def err(x): errors.append(x)
def load_json(path):
 try: return json.loads(path.read_text(encoding='utf-8'))
 except Exception as e: err(f'{path.name} JSON错误: {e}'); return {}
def load_jsonl(path,key):
 out=[]; seen=set()
 if not path.exists(): err(f'缺少索引: {path.name}'); return out
 for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
  if not line.strip(): continue
  try: obj=json.loads(line)
  except Exception as e: err(f'{path.name}:{i} JSON错误 {e}'); continue
  if key not in obj: err(f'{path.name}:{i} 缺少{key}'); continue
  if obj[key] in seen: err(f'{path.name}:{i} 重复{key}={obj[key]}')
  seen.add(obj[key]); out.append(obj)
 return out

required=[
 'AGENTS.md','SYSTEM_MANIFEST.json','SYSTEM_STATE.json','系统状态.json','当前任务.json','CHANGELOG.md',
 '00A_当前强制覆盖与废止规则.md','02A_彩票开奖历史分析体系与方案路由.md',
 '05A_方案讲解PPT生产协议.md','05B_固定首页与末页协议.md','05D_PPT技术来源与号码证据协议.md',
 '11A_本金止盈止损设计与PPT披露协议.md','PPT页面类型卡片.jsonl','PPT讲解验收测试集.jsonl',
 'PPT技术来源验收测试集.jsonl','PPT压缩与精度规则.json','PPT技术来源与号码证据规则.json',
 '10_静默方案总控与外部参考吸收协议.md','11_智能功能调度与资金路径编排协议.md',
 '13_GitHub持续工作区与参考灵感自由重构协议.md','功能能力卡片.jsonl','资金路径模板库.jsonl',
 '.github/workflows/validate.yml'
]
for x in required:
 if not (ROOT/x).exists(): err(f'缺少必需文件: {x}')
if (ROOT/'05B_固定首页第二页末页协议.md').exists(): err('仍保留已废止的固定第二页协议文件')

m=load_json(ROOT/'SYSTEM_MANIFEST.json'); s=load_json(ROOT/'SYSTEM_STATE.json'); sc=load_json(ROOT/'系统状态.json')
task=load_json(ROOT/'当前任务.json'); precision=load_json(ROOT/'PPT压缩与精度规则.json')
source_rules=load_json(ROOT/'PPT技术来源与号码证据规则.json')
version=m.get('版本')
for label,value in [('SYSTEM_STATE.版本',s.get('版本')),('SYSTEM_STATE.version',s.get('version')),('SYSTEM_STATE.当前版本',s.get('当前版本')),('当前任务.版本',task.get('版本'))]:
 if value!=version: err(f'版本不同步: {label}={value!r}, expected={version!r}')
if s!=sc: err('SYSTEM_STATE.json 与 系统状态.json 内容不同步')
if m.get('仓库')!='fdsasaaa/guaji5' or s.get('仓库')!='fdsasaaa/guaji5': err('仓库标识错误')
if task.get('基线仓库')!='fdsasaaa/guaji5': err('当前任务基线仓库错误')
for module in ['00A_当前强制覆盖与废止规则.md','05A_方案讲解PPT生产协议.md','05B_固定首页与末页协议.md','11A_本金止盈止损设计与PPT披露协议.md','13_GitHub持续工作区与参考灵感自由重构协议.md']:
 if module not in m.get('模块',[]): err(f'模块未登记: {module}')

common_checks={
 'PPT规则修改必须回写GitHub':True,'PPT人工讲解审查':True,'PPT压缩审查':True,'PPT精度审查':True,
 'PPT页面价值门槛':True,'PPT先技术后案例':True,'PPT规则独立执行检查':True,
 'PPT技术缘由真实性检查':True,'PPT标题核心准确检查':True,'PPT自然语言转换':True,
 'PPT视觉去重':True,'挂机方案建议本金必须冻结':True,'PPT建议本金必须显示金额':True,
 'PPT启用止盈必须显示金额':True,'PPT启用止损必须显示金额':True,
 'PPT未启用止盈止损必须显示不设置':True,'PPT工程编号禁止可见':True,
 'PPT挂机前禁止结果结论':True,'PPT结果复盘必须来自实际挂机记录':True
}
for obj,label in [(m,'清单'),(s,'状态')]:
 for k,v in common_checks.items():
  if obj.get(k)!=v: err(f'{label}.{k}未启用')
 if obj.get('PPT金额单位')!='元': err(f'{label}.PPT金额单位不是元')
 if obj.get('PPT固定第二页') is not False: err(f'{label}.PPT固定第二页未关闭')
 if obj.get('PPT隐藏附录') is not False: err(f'{label}.PPT隐藏附录未关闭')
 if obj.get('PPT默认阶段')!='PRE_RUN_SETUP': err(f'{label}.PPT默认阶段错误')
if m.get('PPT单文件原则') is not True: err('清单.PPT单文件原则未启用')
if s.get('PPT唯一文件') is not True: err('状态.PPT唯一文件未启用')
if m.get('PPT止盈止损模式必须明确') is not True: err('清单.PPT止盈止损模式必须明确未启用')
if s.get('挂机方案止盈止损模式必须明确') is not True: err('状态.挂机方案止盈止损模式必须明确未启用')
if m.get('PPT页面类型数量')!=12 or s.get('PPT页面类型数量')!=12: err('PPT页面类型数量未同步为12')
if m.get('PPT讲解验收测试数量')!=49 or s.get('PPT讲解验收测试数量')!=49: err('PPT测试数量未同步为49')
allowed=['NONE','STOP_LOSS_ONLY','TAKE_PROFIT_ONLY','BOTH']
if m.get('PPT允许止盈止损模式')!=allowed or s.get('挂机方案允许止盈止损模式')!=allowed: err('止盈止损模式列表错误')
brand=m.get('PPT固定品牌结束页',{})
if brand.get('必须最后正常播放页') is not True or brand.get('网址')!='www.laocaimi.org' or brand.get('联系方式')!='https://t.me/laocaimi1314': err('固定品牌结束页配置错误')

jsonl_specs={
 '历史方案索引.jsonl':'方案ID','分析角度索引.jsonl':'角度ID','学习事件索引.jsonl':'事件ID',
 '规则候选池.jsonl':'候选规则ID','技术原子表现档案.jsonl':'技术原子ID','软件行为证据索引.jsonl':'证据ID',
 '批次索引.jsonl':'批次ID','方案组合案例索引.jsonl':'案例ID','负面方案模式索引.jsonl':'负面模式ID',
 '功能覆盖索引.jsonl':'功能ID','总控验收测试集.jsonl':'测试ID','功能能力卡片.jsonl':'功能ID',
 '资金路径模板库.jsonl':'资金路径ID','PPT页面类型卡片.jsonl':'页面类型ID',
 'PPT讲解验收测试集.jsonl':'测试ID','PPT技术来源验收测试集.jsonl':'测试ID'
}
loaded={n:load_jsonl(ROOT/n,k) for n,k in jsonl_specs.items()}
pt=loaded['PPT页面类型卡片.jsonl']; ids={x.get('页面类型ID') for x in pt}
required_ids={'COVER','TECH_DEFINE','TECH_REASON','RULE','STEP','CASE','DATA','COMPARE','RISK','ADVICE','CONCLUSION','BRAND_END'}
if ids!=required_ids: err(f'PPT页面类型集合错误: {sorted(ids)}')
if any(x.get('隐藏页') is not False for x in pt): err('PPT页面类型中仍存在隐藏页')
tests=loaded['PPT讲解验收测试集.jsonl']
if len(tests)!=49: err(f'PPT验收测试数量错误: {len(tests)}')
fstates={x.get('失败状态') for x in tests}
for x in ['PPT_ENGINEERING_ID_VISIBLE','PPT_CURRENCY_UNIT_NOT_YUAN','PPT_PREMATURE_RESULT_CONCLUSION','PPT_RESULT_SOURCE_NOT_RUNTIME','PPT_HIDDEN_APPENDIX_PRESENT','PPT_FIXED_SECOND_PAGE_PRESENT','PPT_BRAND_PAGE_NOT_LAST','PPT_RENDER_REVIEW_FAILED']:
 if x not in fstates: err(f'PPT验收测试缺少失败状态: {x}')

source_tests=loaded['PPT技术来源验收测试集.jsonl']
if len(source_tests)!=12: err(f'PPT技术来源验收测试数量错误: {len(source_tests)}')
source_states={x.get('失败状态') for x in source_tests}
for x in ['PPT_NUMBER_SOURCE_MISSING','PPT_NUMBER_CALCULATION_MISSING','PPT_NUMBER_REASON_NOT_REPRODUCIBLE','PPT_ANALYSIS_ANGLE_UNREGISTERED','PPT_STORY_BACKFILLED_AFTER_NUMBERS','PPT_ANALYSIS_EXECUTION_MISMATCH','PPT_CONTROL_GROUP_CONFUSED_WITH_MAIN','PPT_INTERNAL_CORRECTION_LANGUAGE_VISIBLE','PPT_NUMBER_EVIDENCE_MISMATCH']:
 if x not in source_states: err(f'PPT技术来源验收测试缺少失败状态: {x}')

if precision.get('状态')!='MANDATORY' or precision.get('正式源')!='GitHub main': err('PPT精度规则基础状态错误')
if precision.get('隐藏附录',{}).get('允许') is not False: err('PPT精度规则仍允许隐藏附录')
if precision.get('固定页面',{}).get('固定第二页') is not False: err('PPT精度规则仍启用固定第二页')
if precision.get('金额规则',{}).get('统一单位')!='元': err('PPT精度规则金额单位错误')
if precision.get('验证阶段',{}).get('默认')!='PRE_RUN_SETUP': err('PPT精度规则默认阶段错误')
tech=precision.get('技术来源与号码证据',{})
if tech.get('强制') is not True or tech.get('禁止倒推故事') is not True: err('PPT精度规则未强制号码来源或未禁止倒推故事')
if tech.get('动态逻辑必须由软件真实执行') is not True: err('PPT精度规则未约束分析与执行一致性')
if source_rules.get('状态')!='MANDATORY': err('PPT技术来源与号码证据规则未启用')
if len(source_rules.get('具体号码展示前必须冻结',[]))!=6: err('号码来源六要素数量错误')

workflow=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8') if (ROOT/'.github/workflows/validate.yml').exists() else ''
for cmd in ['tools/validate_repository.py','tools/validate_ppt_director_rules.py','tools/materialize_ppt_fixed_pages.py','tools/validate_ppt_fixed_pages.py']:
 if cmd not in workflow: err(f'长期校验工作流未调用: {cmd}')
for path in ['05D_PPT技术来源与号码证据协议.md','PPT技术来源与号码证据规则.json','PPT技术来源验收测试集.jsonl']:
 if path not in workflow: err(f'长期校验工作流未确认规则文件: {path}')

override=(ROOT/'00A_当前强制覆盖与废止规则.md').read_text(encoding='utf-8')
proto=(ROOT/'05A_方案讲解PPT生产协议.md').read_text(encoding='utf-8')
source_proto=(ROOT/'05D_PPT技术来源与号码证据协议.md').read_text(encoding='utf-8')
analysis=(ROOT/'02A_彩票开奖历史分析体系与方案路由.md').read_text(encoding='utf-8')
fixed=(ROOT/'05B_固定首页与末页协议.md').read_text(encoding='utf-8')
fund=(ROOT/'11A_本金止盈止损设计与PPT披露协议.md').read_text(encoding='utf-8')
for phrase in ['废止PPT隐藏附录','废止程序化命名和工程痕迹','金额单位统一为“元”','挂机前不预判验证结果','固定第二页已经取消','号码来源与技术缘由最高优先级闸门']:
 if phrase not in override: err(f'00A缺少关键规则: {phrase}')
for phrase in ['PRE_RUN_SETUP','POST_RUN_REVIEW','不存在“隐藏附录”这一去向','金额统一使用“元”','固定第二页已经取消','号码来源强制闸门','禁止内部纠错语言出现在客户页面']:
 if phrase not in proto: err(f'05A缺少关键规则: {phrase}')
for phrase in ['号码来源六要素','分析角度正式源','内部号码证据包','PPT_NUMBER_SOURCE_MISSING']:
 if phrase not in source_proto: err(f'05D缺少关键规则: {phrase}')
for phrase in ['24个分析类别','189个分析角度','分析角度不等于软件技术原子']:
 if phrase not in analysis: err(f'02A缺少分析体系关键内容: {phrase}')
for phrase in ['正文从第二页开始','固定第二页已经取消','PPT固定首页末页模板_V3.9.4.pptx']:
 if phrase not in fixed: err(f'05B缺少关键规则: {phrase}')
for phrase in ['建议本金：X元','PPT_CURRENCY_UNIT_NOT_YUAN','GitHub内部证据位置']:
 if phrase not in fund: err(f'11A缺少关键规则: {phrase}')

for path in ROOT.rglob('*.txt'):
 if '01_本次输入' in path.parts or '08_版本与优化记录' in path.name: continue
 try: text=path.read_text(encoding='gbk')
 except Exception:
  try: text=path.read_text(encoding='utf-8')
  except Exception: continue
 rows=re.findall(r'^\s*([0-9])\s*[|,;:\t ]+([^\r\n]+)$',text,re.M)
 if len(rows)>=10 and len({v.strip() for _,v in rows[:10]})==1: err(f'疑似0-9常量高级映射: {path.relative_to(ROOT)}')

if errors:
 print('VALIDATION_FAILED'); [print('-',x) for x in errors]; sys.exit(1)
print(f"VALIDATION_OK version={s.get('当前版本','?')} repo={s.get('仓库','?')} task={task.get('任务ID','?')} ppt_page_types={len(pt)} ppt_tests={len(tests)} source_tests={len(source_tests)} ppt=SOURCE_GATED_RUNTIME_GATED_YUAN_NO_APPENDIX")

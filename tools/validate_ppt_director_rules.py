#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
ROOT=Path(__file__).resolve().parents[1]; errors=[]
def fail(x): errors.append(x)
def load_json(name):
 try: return json.loads((ROOT/name).read_text(encoding='utf-8'))
 except Exception as e: fail(f'{name}读取失败: {e}'); return {}
def load_jsonl(name):
 out=[]
 try:
  for i,line in enumerate((ROOT/name).read_text(encoding='utf-8').splitlines(),1):
   if line.strip(): out.append(json.loads(line))
 except Exception as e: fail(f'{name}读取失败: {e}')
 return out

def read_text(name):
 try: return (ROOT/name).read_text(encoding='utf-8')
 except Exception as e: fail(f'{name}读取失败: {e}'); return ''

m=load_json('SYSTEM_MANIFEST.json'); s=load_json('SYSTEM_STATE.json'); sc=load_json('系统状态.json')
p=load_json('PPT压缩与精度规则.json'); source_rules=load_json('PPT技术来源与号码证据规则.json')
proto=read_text('05A_方案讲解PPT生产协议.md'); source_proto=read_text('05D_PPT技术来源与号码证据协议.md')
fixed=read_text('05B_固定首页与末页协议.md'); override=read_text('00A_当前强制覆盖与废止规则.md')
analysis_proto=read_text('02A_彩票开奖历史分析体系与方案路由.md')
pt=load_jsonl('PPT页面类型卡片.jsonl'); tests=load_jsonl('PPT讲解验收测试集.jsonl')
source_tests=load_jsonl('PPT技术来源验收测试集.jsonl')

if s!=sc: fail('SYSTEM_STATE.json 与 系统状态.json 不一致')
for obj,label in [(m,'MANIFEST'),(s,'STATE')]:
 checks={'PPT工程编号禁止可见':True,'PPT金额单位':'元','PPT固定第二页':False,'PPT隐藏附录':False,'PPT默认阶段':'PRE_RUN_SETUP','PPT挂机前禁止结果结论':True,'PPT结果复盘必须来自实际挂机记录':True}
 for k,v in checks.items():
  if obj.get(k)!=v: fail(f'{label}.{k}错误: {obj.get(k)!r}')

if m.get('PPT页面类型数量')!=12 or s.get('PPT页面类型数量')!=12: fail('PPT页面类型数量未同步为12')
if m.get('PPT讲解验收测试数量')!=49 or s.get('PPT讲解验收测试数量')!=49: fail('PPT验收测试数量未同步为49')
if len(pt)!=12: fail(f'页面类型应为12，实际{len(pt)}')
ids={x.get('页面类型ID') for x in pt}
required={'COVER','TECH_DEFINE','TECH_REASON','RULE','STEP','CASE','DATA','COMPARE','RISK','ADVICE','CONCLUSION','BRAND_END'}
if ids!=required: fail(f'页面类型集合错误: {sorted(ids)}')
if {'APPENDIX','APPENDIX_DIVIDER'} & ids: fail('仍存在隐藏附录页面类型')
for x in pt:
 if x.get('隐藏页') is not False: fail(f"页面类型{x.get('页面类型ID')}不应隐藏")
for rid in ['DATA','COMPARE','CONCLUSION']:
 x=next((y for y in pt if y.get('页面类型ID')==rid),{})
 if x.get('允许阶段')!=['POST_RUN_REVIEW']: fail(f'{rid}未限制为挂机后复盘')

if len(tests)!=49: fail(f'验收测试应为49，实际{len(tests)}')
fstates={x.get('失败状态') for x in tests}
for state in ['PPT_ENGINEERING_ID_VISIBLE','PPT_CURRENCY_UNIT_NOT_YUAN','PPT_PREMATURE_RESULT_CONCLUSION','PPT_RESULT_SOURCE_NOT_RUNTIME','PPT_HIDDEN_APPENDIX_PRESENT','PPT_FIXED_SECOND_PAGE_PRESENT','PPT_BRAND_LINK_NOT_CLICKABLE']:
 if state not in fstates: fail(f'验收测试缺少失败状态: {state}')

if len(source_tests)!=12: fail(f'技术来源验收测试应为12，实际{len(source_tests)}')
source_states={x.get('失败状态') for x in source_tests}
required_source_states={
 'PPT_NUMBER_SOURCE_MISSING','PPT_NUMBER_CALCULATION_MISSING','PPT_NUMBER_REASON_NOT_REPRODUCIBLE',
 'PPT_ANALYSIS_ANGLE_UNREGISTERED','PPT_STORY_BACKFILLED_AFTER_NUMBERS','PPT_ANALYSIS_EXECUTION_MISMATCH',
 'PPT_CONTROL_GROUP_CONFUSED_WITH_MAIN','PPT_INTERNAL_CORRECTION_LANGUAGE_VISIBLE','PPT_NUMBER_EVIDENCE_MISMATCH'
}
missing_source_states=required_source_states-source_states
if missing_source_states: fail(f'技术来源验收测试缺少失败状态: {sorted(missing_source_states)}')

for text,label in [(proto,'05A'),(override,'00A')]:
 for phrase in ['固定第二页已经取消','隐藏附录']:
  if phrase not in text: fail(f'{label}缺少关键说明: {phrase}')
if '固定第二页已经取消' not in fixed: fail('05B缺少固定第二页取消说明')
for phrase in ['PRE_RUN_SETUP','POST_RUN_REVIEW','PPT_ENGINEERING_ID_VISIBLE','PPT_CURRENCY_UNIT_NOT_YUAN','PPT_PREMATURE_RESULT_CONCLUSION','PPT_HIDDEN_APPENDIX_PRESENT']:
 if phrase not in proto: fail(f'05A缺少关键规则: {phrase}')
for phrase in ['号码来源强制闸门','历史数据中出现了什么现象','具体号码或状态怎样计算出来','先随意选定号码','PPT_NUMBER_SOURCE_MISSING','PPT_ANALYSIS_EXECUTION_MISMATCH']:
 if phrase not in proto: fail(f'05A缺少号码来源规则: {phrase}')
for phrase in ['号码来源与技术缘由最高优先级闸门','02A_彩票开奖历史分析体系与方案路由.md','PPT技术来源验收测试集.jsonl','禁止先随意找几组数字']:
 if phrase not in override: fail(f'00A缺少号码来源覆盖规则: {phrase}')
for phrase in ['号码来源六要素','分析角度正式源','不能先随意确定一组数字','内部号码证据包','PPT_STORY_BACKFILLED_AFTER_NUMBERS']:
 if phrase not in source_proto: fail(f'05D缺少关键规则: {phrase}')
for phrase in ['24个分析类别','189个分析角度','分析角度不等于软件技术原子','分析角度到方案套的转译模板']:
 if phrase not in analysis_proto: fail(f'02A分析体系缺少关键内容: {phrase}')
for phrase in ['正文从第二页开始','固定首页与末页','PPT固定首页末页模板_V3.9.4.pptx']:
 if phrase not in fixed: fail(f'05B缺少关键规则: {phrase}')

if p.get('隐藏附录',{}).get('允许') is not False: fail('结构化规则仍允许隐藏附录')
if p.get('固定页面',{}).get('固定第二页') is not False: fail('结构化规则仍启用固定第二页')
if p.get('金额规则',{}).get('统一单位')!='元': fail('结构化规则金额单位不是元')
if p.get('验证阶段',{}).get('默认')!='PRE_RUN_SETUP': fail('结构化规则默认阶段错误')
for forbidden in ['B001','B392_SET_001']:
 if forbidden not in p.get('命名规则',{}).get('禁止示例',[]): fail(f'命名规则未覆盖{forbidden}')

tech=p.get('技术来源与号码证据',{})
if tech.get('强制') is not True: fail('PPT压缩与精度规则未强制技术来源闸门')
for field in ['数据来源','观察对象','分析角度','计算过程','选取规则','最终结果']:
 if field not in tech.get('具体号码展示前必须具备',[]): fail(f'技术来源结构化规则缺少: {field}')
if tech.get('禁止倒推故事') is not True: fail('结构化规则未禁止先定号码后补故事')
if tech.get('动态逻辑必须由软件真实执行') is not True: fail('结构化规则未要求动态逻辑真实执行')
if tech.get('随机对照必须与主技术分层') is not True: fail('结构化规则未要求对照组分层')

if source_rules.get('状态')!='MANDATORY': fail('号码证据规则未设为MANDATORY')
for field in ['数据来源','观察对象','分析角度','计算过程','选取规则','最终结果']:
 if field not in source_rules.get('具体号码展示前必须冻结',[]): fail(f'号码证据规则缺少冻结项: {field}')
for state in required_source_states:
 if state not in source_rules.get('失败状态',[]): fail(f'号码证据规则缺少失败状态: {state}')
for bad in ['更严谨的说法','四组测试码预设','为了方便演示']:
 if bad not in source_rules.get('客户页面禁止措辞',[]): fail(f'客户页面禁止措辞缺少: {bad}')

if errors:
 print('PPT_DIRECTOR_RULES_FAILED'); [print('-',x) for x in errors]; sys.exit(1)
print('PPT_DIRECTOR_RULES_OK page_types=12 tests=49 source_tests=12 second=DISABLED appendix=DISABLED currency=YUAN stage=RUNTIME_GATED source_gate=MANDATORY')

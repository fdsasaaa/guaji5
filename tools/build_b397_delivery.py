#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json, math, re, shutil, sys
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'tools'))
import build_b394_delivery as base
PROJECT='三区冠军三码'; ID='B397-SET-001'; BATCH='BATCH-B397-ZONE-CHAMPION-001'; PERIODS=24; P0=.30
INPUT=ROOT/'01_本次输入'/'哈希分分彩_20260731_0181至0380.txt'; OUT=ROOT/'dist'/f'{PROJECT}_交付'; PKG=OUT/'package'
SCHEME=OUT/f'{PROJECT}_方案套.zip'; PPT=OUT/f'{PROJECT}_挂机前讲解.pptx'; EVIDENCE=OUT/f'{PROJECT}_验证记录.json'; MANIFEST=OUT/'DELIVERY_MANIFEST.json'; OUTER=OUT/f'{PROJECT}_完整交付.zip'
POS=[(2,'百位'),(3,'十位'),(4,'个位')]; ZONES=[('低区',(0,1,2)),('中区',(3,4,5,6)),('高区',(7,8,9))]

def choose(values):
 c=Counter(values); last={d:max((i for i,x in enumerate(values) if x==d),default=-1) for d in range(10)}; selected=[]; detail=[]
 for name,digits in ZONES:
  rank=sorted(digits,key=lambda d:(-c[d],-last[d],d)); selected.append(rank[0]); detail.append({'分区':name,'范围':list(digits),'排序':[{'数字':d,'出现次数':c[d],'最近位置':last[d]} for d in rank],'冠军':rank[0]})
 return selected,detail

def tail_p(n,h,p=P0): return min(1.0,sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(h,n+1)))
def miss(xs):
 best=run=0
 for x in xs: run=0 if x else run+1; best=max(best,run)
 return best
def summary(xs):
 n=len(xs); h=sum(xs); return {'预测次数':n,'命中次数':h,'命中比例':round(h/n,6),'随机三码理论基准':P0,'相对基准差':round(h/n-P0,6),'独立近似单侧二项P值':round(tail_p(n,h),6),'最大连续未中':miss(xs)}
def freeze(rows):
 out={}
 for i,n in POS:
  sel,detail=choose([x[i] for _,x in rows]); out[n]={'位置索引':i,'样本期数':len(rows),'固定分区':{'低区':[0,1,2],'中区':[3,4,5,6],'高区':[7,8,9]},'分区排序':detail,'冻结号码':sel,'运行中是否更新':False}
 return out
def audit(rows):
 seg={'校准段':[],'验证段':[],'审计段':[]}; per={n:[] for _,n in POS}; allx=[]
 for t in range(60,len(rows)):
  for i,n in POS:
   selected,_=choose([x[i] for _,x in rows[:t]]); hit=rows[t][1][i] in selected; allx.append(hit); per[n].append(hit); seg['校准段' if t<120 else '验证段' if t<160 else '审计段'].append(hit)
 return {'方法':'从第61期开始逐期扩展窗口；每次仅使用此前同位置数据，在固定低中高三区各取频次冠军。','总计':summary(allx),'分段':{k:summary(v) for k,v in seg.items()},'分位置':{k:summary(v) for k,v in per.items()},'统计边界':'二项P值仅作独立近似参考；位置间和时间上可能相关。','样本边界':'200期数据已被项目复用，不属于新的独立样本外。'}

def setv(lines,prefix,value):
 for i,line in enumerate(lines):
  if line.startswith(prefix): lines[i]=prefix+value; return
 raise ValueError('缺少字段:'+prefix)
def fixed_txt(play,digits,enabled=True):
 lines=base.common('定码轮换',play,enabled)+['换号规则=9',f'换号期数={PERIODS}']+base.tail()+[f"定码轮换内容={' '.join(map(str,digits))}",'定码轮换单组=True','SchemeCreator=']; return '\r\n'.join(lines)+'\r\n'
def probe_txt(play,digits,kind):
 lines=fixed_txt(play,digits,False).split('\r\n')[:-1]
 if kind=='monitor': setv(lines,'投注监控=','True-0'); setv(lines,'投注监控模式=','1')
 if kind=='simulation': setv(lines,'真实投注1=','True-2')
 if kind=='advanced': setv(lines,'倍投类型=','1'); setv(lines,'倍投计划=','1,1,1,1,1,1,1,1'); setv(lines,'倍投方案=','高级倍投主配置')
 return '\r\n'.join(lines)+'\r\n'
def advanced_config():
 name='高级状态倍投探针'; rows=[f'软件名称=CXGGJ;ID=1;倍数=1;中后ID=1;挂后ID=2;中后监控=False;中后跳转=False-{name};挂后监控=False;挂后跳转=False-{name}',f'软件名称=CXGGJ;ID=2;倍数=2;中后ID=1;挂后ID=3;中后监控=False;中后跳转=False-{name};挂后监控=False;挂后跳转=False-{name}',f'软件名称=CXGGJ;ID=3;倍数=1;中后ID=1;挂后ID=1;中后监控=False;中后跳转=False-{name};挂后监控=False;挂后跳转=False-{name}']; return ('\ufeff'+'\r\n'.join(rows)+'\r\n').encode('utf-8')

def build_package(g,issue):
 if PKG.exists(): shutil.rmtree(PKG)
 folders={k:PKG/v for k,v in {'formal':'01_正式主方案_三区冠军','control':'02_随机对照_单独运行','monitor':'90_隔离探针_仅开始监控','simulation':'91_隔离探针_模拟转真实','advanced':'92_隔离探针_高级状态倍投'}.items()}
 for p in folders.values(): p.mkdir(parents=True)
 for n in ['百位','十位','个位']:
  (folders['formal']/f'三区冠军{n}-定码轮换.txt').write_bytes(fixed_txt(n,g[n]['冻结号码']).encode('gbk')); (folders['control']/f'随机{n}-随机出号.txt').write_bytes(base.random_txt(n).encode('gbk'))
 digits=g['百位']['冻结号码']; (folders['monitor']/'仅开始监控探针-定码轮换.txt').write_bytes(probe_txt('百位',digits,'monitor').encode('gbk')); (folders['simulation']/'模拟转真实探针-定码轮换.txt').write_bytes(probe_txt('百位',digits,'simulation').encode('gbk')); (folders['advanced']/'高级状态倍投探针-定码轮换.txt').write_bytes(probe_txt('百位',digits,'advanced').encode('gbk'))
 gjbt=folders['advanced']/'GJBTScheme'; gjbt.mkdir(); (gjbt/'高级倍投主配置.txt').write_bytes(advanced_config())
 readme=f'''# {PROJECT}｜完整运行说明

固定分区：低区0—2、中区3—6、高区7—9。每个位置分别统计200期，每区取频次冠军；同频时优先最近出现，再取较小数字。

- 百位：{' '.join(map(str,g['百位']['冻结号码']))}
- 十位：{' '.join(map(str,g['十位']['冻结号码']))}
- 个位：{' '.join(map(str,g['个位']['冻结号码']))}
- 数据截止期：{issue}

正式运行：只启用01目录三份TXT，手工开启顶部方案轮投，运行{PERIODS}期。随后关闭主方案，单独运行02随机对照{PERIODS}期。每期3元，两阶段各72元，建议本金144元；止盈、止损均不设置，以每阶段24期硬停止替代；全程平倍，禁止改码和追损。

90—92目录均为TEST_ONLY且默认关闭，不能与正式方案或彼此同时运行：监控探针最多观察12期、真实最多3期、成本上限9元；模拟转真实探针以模拟连挂2次触发、真实最多3期、成本上限9元；高级状态探针仅跑1→2→1一个循环，最坏暴露12元。三者只有E1/E2证据，不得解释为成熟功能。
'''
 (PKG/'00_使用说明.md').write_text(readme,encoding='utf-8'); (PKG/'01_正式实验核对表.md').write_text(f'# 导入与运行核对表\n- [ ] 只启用正式主方案\n- [ ] 顶部方案轮投已开启\n- [ ] 每阶段满{PERIODS}期停止\n- [ ] 随机对照单独运行\n- [ ] 三个探针均默认关闭\n- [ ] 每期3元且全程平倍\n',encoding='utf-8'); (PKG/'02_实际挂机记录模板.csv').write_text('阶段,期号,实际方案名称,位置,冻结号码,开奖号,是否命中,备注\n',encoding='utf-8-sig'); (PKG/'93_隔离探针记录模板.csv').write_text('探针名称,期号,模拟或真实,当前局,实际倍数,是否投注,输赢,是否切换,重启后状态,备注\n',encoding='utf-8-sig')
 with ZipFile(SCHEME,'w',ZIP_DEFLATED) as z:
  for p in sorted(PKG.rglob('*')):
   if p.is_file(): z.write(p,arcname=p.relative_to(PKG).as_posix())

def countline(g,n): return '  ·  '.join(f"{x['分区']} {x['冠军']}（{x['排序'][0]['出现次数']}次）" for x in g[n]['分区排序'])
def build_ppt(g,issue,hist):
 cover=ROOT/'assets'/'ppt'/'fixed_pages'/'首页背景图谱.png'; end=ROOT/'assets'/'ppt'/'fixed_pages'/'固定最后一页_画面.png'; prs=base.fixed.new_prs(); ac={'百位':'gold','十位':'blue','个位':'green'}
 s=base.fixed.add_cover(prs,cover); base.fixed.add_text(s,Inches(.82),Inches(1.02),Inches(9.2),Inches(.72),PROJECT,34,base.COLORS['white'],True); base.fixed.add_text(s,Inches(.84),Inches(1.86),Inches(9.7),Inches(.38),'低中高三区，各选一名频次冠军',17,base.COLORS['gold'],True); base.fixed.add_text(s,Inches(.84),Inches(5.88),Inches(9.8),Inches(.34),'挂机前规则说明｜结论等待实际运行',14,base.COLORS['white']); base.fixed.set_notes(s,'研究固定分区后的频次冠军，不把历史频次包装成下一期预言。')
 s=base.body_slide(prs,'这次验证什么','研究问题'); base.card(s,Inches(.78),Inches(1.8),Inches(5.55),Inches(3.82),'分区后再竞争','把0—9固定分成低、中、高三区，每区只选一名历史频次冠军，避免三个号码挤在同一段。','gold',18,18); base.card(s,Inches(6.58),Inches(1.8),Inches(5.55),Inches(3.82),'先冻结，再向前跑','百位、十位、个位分别计算；正式运行24期，随后用同成本随机三码做对照。','blue',18,18); base.fixed.set_notes(s,'说明研究问题和前向可证伪边界。')
 s=base.body_slide(prs,'三区怎样划分','核心规则')
 for i,(t,b,c) in enumerate([('低区','0 1 2','gold'),('中区','3 4 5 6','blue'),('高区','7 8 9','green')]): base.card(s,Inches(.82+i*4.08),Inches(1.95),Inches(3.52),Inches(2.25),t,b,c,20,25)
 base.card(s,Inches(.82),Inches(4.52),Inches(11.68),Inches(1.34),'冠军规则','区内按出现次数降序；同频优先最近出现；仍相同取较小数字。每个位置最终得到3个号码。','gold',17,17); base.fixed.set_notes(s,'分区固定且并列规则预注册，防止事后挑号码。')
 s=base.body_slide(prs,'三组号码从哪里来','号码证据')
 for i,n in enumerate(['百位','十位','个位']): base.card(s,Inches(.72+i*4.05),Inches(1.82),Inches(3.82),Inches(3.95),n,f"{countline(g,n)}\n\n冻结号码：{' '.join(map(str,g[n]['冻结号码']))}",ac[n],19,17)
 base.fixed.add_text(s,Inches(.88),Inches(6.08),Inches(11.4),Inches(.3),f'数据：202607310181—{issue}｜200期｜运行中不更新',15,base.COLORS['gray'],True,PP_ALIGN.CENTER); base.fixed.set_notes(s,'PPT、TXT与验证JSON使用同一冻结结果。')
 s=base.body_slide(prs,'以百位完整复算一次','完整案例')
 for i,x in enumerate(g['百位']['分区排序']): base.card(s,Inches(.72+i*4.05),Inches(1.82),Inches(3.82),Inches(3.92),x['分区'],f"范围：{' '.join(map(str,x['范围']))}\n\n排序：\n"+' > '.join(f"{r['数字']}（{r['出现次数']}次）" for r in x['排序'])+f"\n\n冠军：{x['冠军']}",['gold','blue','green'][i],18,16)
 base.fixed.add_text(s,Inches(.9),Inches(6.02),Inches(11.5),Inches(.38),f"百位最终：{' '.join(map(str,g['百位']['冻结号码']))}",20,base.COLORS['white'],True,PP_ALIGN.CENTER); base.fixed.set_notes(s,'其他位置使用完全相同的计算方法。')
 s=base.body_slide(prs,'正式主方案怎样运行','执行规则')
 for i,n in enumerate(['百位','十位','个位']): base.card(s,Inches(.82+i*4.08),Inches(1.95),Inches(3.52),Inches(2.08),f'{i+1}  {n}',f"冻结：{' '.join(map(str,g[n]['冻结号码']))}",ac[n],18,22)
 base.card(s,Inches(.82),Inches(4.38),Inches(11.68),Inches(1.42),'软件设置','导入三份正式TXT → 手工开启顶部方案轮投 → 每期运行一个位置 → 连续24期后停止。','gold',17,18); base.fixed.set_notes(s,'软件只执行静态定码与顶部轮投，不会自动统计三区冠军。')
 s=base.body_slide(prs,'随机对照必须分开','对照设计'); base.card(s,Inches(.78),Inches(1.82),Inches(5.55),Inches(3.82),'第一阶段：三区冠军','三位置定码轮投\n24期\n每期3元，共72元','gold',18,20); base.card(s,Inches(6.58),Inches(1.82),Inches(5.55),Inches(3.82),'第二阶段：随机三码','关闭主方案后单独运行\n24期\n每期3元，共72元','blue',18,20); base.fixed.add_text(s,Inches(.9),Inches(6.02),Inches(11.5),Inches(.42),'两组不能并投，也不能中途换号码。',18,base.COLORS['red'],True,PP_ALIGN.CENTER); base.fixed.set_notes(s,'同成本、同期数、分阶段运行。')
 s=base.body_slide(prs,'三个探针只测软件行为','隔离实验')
 for i,(t,b,c) in enumerate([('仅开始监控','观察到1次未中状态后触发；最多观察12期，真实投注最多3期。','gold'),('模拟转真实','模拟连续未中2次后切真实；真实阶段最多3期。','blue'),('高级状态倍投','1→2→1三局格式，只跑一个循环；不与新状态功能混装。','green')]): base.card(s,Inches(.72+i*4.05),Inches(1.82),Inches(3.82),Inches(3.95),t,b,c,18,17)
 base.fixed.add_text(s,Inches(.9),Inches(6.02),Inches(11.5),Inches(.38),'TEST_ONLY｜默认关闭｜三者彼此隔离',18,base.COLORS['red'],True,PP_ALIGN.CENTER); base.fixed.set_notes(s,'这些功能只有E1或E2证据，不把它们当正式成熟功能。')
 x=hist['总计']; s=base.body_slide(prs,'资金边界与判定方法','风险控制'); base.card(s,Inches(.78),Inches(1.8),Inches(3.55),Inches(3.92),'建议本金','主方案72元\n随机对照72元\n合计144元','gold',18,22); base.card(s,Inches(4.58),Inches(1.8),Inches(3.55),Inches(3.92),'停止规则','止盈：不设置\n止损：不设置\n每阶段24期硬停止\n正式实验全程平倍','blue',18,18); base.card(s,Inches(8.38),Inches(1.8),Inches(3.55),Inches(3.92),'历史只作审计',f"滚动命中 {x['命中次数']}/{x['预测次数']}\n约{x['命中比例']*100:.2f}%\n随机基准30%\n不提前下结论",'green',18,18); base.fixed.set_notes(s,'历史接近随机基准，正式结论等待新记录。')
 base.fixed.add_end(prs,end); base.fixed.save(prs,PPT)

def validate(g):
 errs=[]
 with ZipFile(SCHEME) as z:
  names=z.namelist(); formal=[n for n in names if n.endswith('.txt') and '01_正式主方案' in n]; controls=[n for n in names if n.endswith('.txt') and '02_随机对照' in n]; probes=[n for n in names if n.endswith('.txt') and any(x in n for x in ('90_隔离探针','91_隔离探针','92_隔离探针')) and 'GJBTScheme' not in n]
  if len(formal)!=3 or len(controls)!=3 or len(probes)!=3: errs.append('TXT数量错误')
  for n in formal+controls+probes:
   raw=z.read(n); text=raw.decode('gbk')
   if b'\r\n' not in raw or 'SchemeCreator=\r\n' not in text: errs.append('TXT格式错误:'+n)
   if n in formal and not text.startswith('True\r\n'): errs.append('正式方案未启用:'+n)
   if n in controls+probes and not text.startswith('False\r\n'): errs.append('对照或探针未关闭:'+n)
  cfg='92_隔离探针_高级状态倍投/GJBTScheme/高级倍投主配置.txt'
  if cfg not in names or not z.read(cfg).startswith(b'\xef\xbb\xbf') or b'\r\n' not in z.read(cfg): errs.append('高级倍投配置错误')
 prs=Presentation(PPT); visible='\n'.join(sh.text for s in prs.slides for sh in s.shapes if hasattr(sh,'text') and sh.text)
 if len(prs.slides)!=10: errs.append('PPT页数错误')
 for i,s in enumerate(prs.slides,1):
  if not s.notes_slide.notes_text_frame.text.strip(): errs.append(f'第{i}页无备注')
 for bad in [ID,'SET_001','保证盈利','稳定盈利','回本']:
  if bad in visible: errs.append('PPT禁词:'+bad)
 if re.search(r'\d+(?:\.\d+)?U\b',visible): errs.append('金额单位错误')
 for n in ['百位','十位','个位']:
  if ' '.join(map(str,g[n]['冻结号码'])) not in visible: errs.append('缺少号码:'+n)
 if errs: raise ValueError(';'.join(errs))
 return {'TXT':'9_FILES_GBK_CRLF','ADVANCED_CONFIG':'UTF8_BOM_CRLF','PPT页数':10,'PPT隐藏页':0,'演讲者备注':'ALL_SLIDES','正式与探针物理分层':'PASS','号码一致性':'PASS'}

def main():
 if OUT.exists(): shutil.rmtree(OUT)
 OUT.mkdir(parents=True); rows=base.parse_draws(INPUT)
 if len(rows)!=200: raise ValueError('本批要求200期')
 g=freeze(rows); hist=audit(rows); build_package(g,rows[-1][0]); build_ppt(g,rows[-1][0],hist)
 evidence={'批次ID':BATCH,'方案内部ID':ID,'自然名称':PROJECT,'阶段':'PRE_RUN_SETUP','数据来源':{'文件':str(INPUT.relative_to(ROOT)).replace('\\','/'),'期号范围':f'{rows[0][0]}—{rows[-1][0]}','总期数':len(rows),'数据复用状态':'REUSED_DATA_NOT_INDEPENDENT_HOLDOUT'},'观察对象':'百位、十位、个位分别建模','分析角度':'固定分区频次冠军','计算过程':'0—2、3—6、7—9三区固定；区内频次降序，同频按最近出现与数字升序；每区取1码。','冻结结果':g,'历史滚动审计':hist,'正式执行':{'顶部方案轮投':'人工勾选','主方案期数':PERIODS,'随机对照期数':PERIODS,'每期成本':3,'建议本金':PERIODS*6,'止盈':'不设置','止损':'不设置','替代停止条件':f'每阶段满{PERIODS}期硬停止','资金路径':'平倍'},'隔离探针':[{'功能':'MONITORING','证据等级':'E1','最大期数':12,'成本上限':9},{'功能':'SIMULATION_REAL_SWITCH','证据等级':'E1','最大期数':12,'成本上限':9},{'功能':'FUNDING_ADVANCED_STATE','证据等级':'E2','最大期数':3,'成本上限':12}],'结论边界':'滚动审计未证明优于随机；最终结论只使用新的实际挂机记录。'}
 EVIDENCE.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); check=validate(g)
 with ZipFile(OUTER,'w',ZIP_DEFLATED) as z: z.write(SCHEME,arcname=SCHEME.name); z.write(PPT,arcname=PPT.name)
 files=[SCHEME,PPT,EVIDENCE,OUTER]; MANIFEST.write_text(json.dumps({'project':PROJECT,'stage':'PRE_RUN_SETUP','validation':check,'files':{p.name:base.sha256(p) for p in files}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('B397_DELIVERY_OK',','.join(f"{n}:{g[n]['冻结号码']}" for n in ['百位','十位','个位']),f"walk_forward={hist['总计']['命中次数']}/{hist['总计']['预测次数']}",OUTER.name)
if __name__=='__main__': main()

#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import hashlib, json, sys
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'assets'/'ppt'/'fixed_pages'; M=A/'PPT固定页资源清单.json'; errors=[]
def fail(x): errors.append(x)
def sha256(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()
def slide_count(p):
 with ZipFile(p) as z: return sum(1 for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml') and '/_rels/' not in n)
def xml(p,n):
 with ZipFile(p) as z: return z.read(f'ppt/slides/slide{n}.xml').decode('utf-8')
def rels(p,n):
 with ZipFile(p) as z:
  q=f'ppt/slides/_rels/slide{n}.xml.rels'; return z.read(q).decode('utf-8') if q in z.namelist() else ''
try: manifest=json.loads(M.read_text(encoding='utf-8'))
except Exception as e: fail(f'固定页资源清单读取失败: {e}'); manifest={}
if manifest.get('fixed_second_page') is not False: fail('资源清单未明确关闭固定第二页')
for rel,expected in manifest.get('files',{}).items():
 p=ROOT/rel
 if not p.exists(): fail(f'固定页资源缺失: {rel}')
 elif sha256(p)!=expected: fail(f'固定页资源哈希不一致: {rel}')
cover=A/'固定首页模板.pptx'; end=A/'固定最后一页_标准版.pptx'; preview=A/'PPT固定首页末页模板_V3.9.4.pptx'; protocol=ROOT/'05B_固定首页与末页协议.md'
for p in [A/'首页背景图谱.png',cover,end,preview,protocol]:
 if not p.exists(): fail(f'必要文件缺失: {p.relative_to(ROOT)}')
for p in [cover,end,preview]:
 if p.exists():
  try:
   with ZipFile(p) as z:
    if z.testzip() is not None: fail(f'PPTX压缩包损坏: {p.name}')
  except BadZipFile: fail(f'PPTX无法打开: {p.name}')
if cover.exists():
 x=xml(cover,1)
 if '<p:bg>' not in x or '<a:blipFill' not in x: fail('固定首页模板未使用图片背景层')
 if '<p:pic>' in x: fail('固定首页模板仍包含普通全页图片')
if end.exists():
 if slide_count(end)!=1: fail('固定最后一页必须且只能有一页')
 r=rels(end,1)
 for link in ['http://www.laocaimi.org','https://t.me/laocaimi1314']:
  if link not in r: fail(f'固定最后一页缺少超链接: {link}')
if preview.exists():
 if slide_count(preview)!=2: fail('固定预览模板必须严格为首页和末页两页')
 x=xml(preview,1)
 if '<p:bg>' not in x or '<p:pic>' in x: fail('预览模板首页没有使用不可选中的背景层')
 r=rels(preview,2)
 if 'http://www.laocaimi.org' not in r or 'https://t.me/laocaimi1314' not in r: fail('预览模板末页链接不完整')
for obsolete in [A/'固定第二页_平台与联系.pptx',A/'PPT固定首页第二页末页模板_V3.9.3.pptx']:
 if obsolete.exists(): fail(f'发现已取消的固定第二页残留: {obsolete.name}')
if protocol.exists():
 c=protocol.read_text(encoding='utf-8')
 for phrase in ['双击页面不得选中背景图','正文从第二页开始','固定第二页已经取消','固定最后一页_标准版.pptx']:
  if phrase not in c: fail(f'05B协议缺少关键规则: {phrase}')
if errors:
 print('PPT_FIXED_PAGES_FAILED'); [print('-',x) for x in errors]; sys.exit(1)
print('PPT_FIXED_PAGES_OK cover=BACKGROUND second=DISABLED end=FIXED_LAST links=VALID')

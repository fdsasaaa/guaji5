# RL_ADV_20260806 导入失败回归修复

## 用户现场异常

```text
System.NullReferenceException
IntelligentPlanning.ConfigurationStatus.Scheme.get_Value()
IntelligentPlanning.ConfigurationStatus.Scheme.GetFileValue()
IntelligentPlanning.AutoBetsWindow.exportScheme()
IntelligentPlanning.AutoBetsWindow.Ckb_ImportScheme_Click()
```

异常发生在软件导入方案并读取方案值时。该错误不是通过开启JIT调试解决的问题；JIT只改变未处理异常的显示与转交方式。

## 首版不合格项

### 主方案

- 第2行写成`定位胆`，把玩法类型误当成一级策略；
- 使用未验证字段`投注内容=3 7`；
- 缺少完整通用字段；
- `倍投方案`写成倍率序列，没有引用配置名。

### 高级倍投配置

- 使用`资金路径类型/状态数量/倍率`等说明型自定义字段；
- 没有逐局九字段；
- 软件无法建立完整Scheme对象。

## 修正版结构

```text
A001_回利二码_个位-定码轮换.txt
GJBTScheme/
  高级倍投主配置.txt
说明资料/
  ...
```

主方案关键字段：

```text
True
定码轮换
玩法类型=定位胆
玩法名称=个位
倍投类型=1
倍投方案=高级倍投主配置
定码轮换内容=3 7
```

高级倍投每局固定结构：

```text
软件名称=CXGGJ;ID=x;倍数=x;中后ID=x;挂后ID=x;中后监控=False;中后跳转=False-高级倍投主配置;挂后监控=False;挂后跳转=False-高级倍投主配置
```

## 审计器底层修复

`05_工具/audit_scheme_semantics.py`新增阻断规则：

1. 主方案必须为GBK无BOM、全CRLF、末尾双CRLF；
2. 第2行不得使用玩法类型代替一级策略；
3. 必需通用字段不得缺失；
4. 阻断未验证通用字段`投注内容`；
5. `定码轮换`必须有`定码轮换内容`和`定码轮换单组`；
6. `倍投计划`必须是正整数序列；
7. 高级倍投的`倍投方案`必须是配置名，不能是倍率序列；
8. ZIP必须存在被引用的`GJBTScheme/<配置名>.txt`；
9. 高级倍投配置必须为UTF-8 BOM、全CRLF；
10. 每局必须严格九字段、ID连续、倍数大于0、跳转目标存在；
11. 未验证的监控=True或跨配置跳转不得进入正式方案。

## 回归结果

修正版：

```text
strategy=定码轮换
main_encoding=gbk
advanced_rows=29
errors=0
warnings=0
```

首版同结构重放可被审计器阻断，主要错误包括：

- 第2行误用`定位胆`；
- 缺少通用字段；
- 检测到伪`投注内容`；
- `倍投方案`错误使用倍率序列。

## 尚未关闭的验证边界

当前执行环境不能运行用户Windows挂机软件，故只完成静态导入闸门。用户本机重新导入成功并核对跳转前，本任务不得标记为运行验证通过。

# FUNCTION-ORCHESTRATION-V1 升级记录

日期：2026-08-04  
状态：Draft PR #19 已通过全量CI，等待独立审查与合并  
基线：`main` @ `3c8757d89b8963be1f166d8cbbc0dd2f91907dc8`  
升级域：SYSTEM + PROGRAM

## 根因

此前协议虽然写明八层能力、资金四路和更多设置审议，但没有机器可执行的证据格式与失败门槛。导演可以用“风险较大”“污染对照”“不启用”几句话跳过监控、跳转、模拟切换、高级倍投和压力释放路径，最终仍反复交付静态号码、顶部轮投和 `1,1,1...`。

## 本次升级

1. 新增 `controller/function_orchestration.json`，固定四类画像、八层能力、资金四路、更多设置、重复限制与覆盖债务门槛。
2. 新增 `controller/templates/function_orchestration.template.json`，作为每个标准方案任务的完整证据模板；新增统一评分模板。
3. 新增中央证据注册表 `controller/feature_evidence_registry.json`，限制各功能可声称的最高证据等级，阻止把字段存在或E2导入证据自行升级为E3运行证据。
4. 新增中央覆盖账本 `controller/function_coverage_ledger.json`，持久记录到期功能、连续未形成实质候选次数和下一批探索优先级。
5. 新增 `tools/validate_function_orchestration.py`，校验：
   - 四类画像齐全；
   - 至少三种实质签名；
   - 每个画像完整填写A—H；
   - 平倍、有限普通、压力释放、高级状态四路均有具体设计和暴露；
   - 至少两类更多设置形成具体候选参数；
   - E3以下功能不得正式入选；
   - 连续纯平倍与重复画像限制；
   - 覆盖债务必须由候选、探针或证据化阻塞关闭；
   - 新状态功能首次使用不得与高级状态资金路径同时正式启用。
6. 新增 `tools/validate_orchestration_scoring.py`，强制画像和资金路径完成10维透明评分，默认选择最高分且正式合格项；低分覆盖必须保存证据引用。
7. 新增 `tools/validate_scheme_orchestration_gate.py`，对每个PR差异执行闸门：只新增构建器、批次记录或YouTube配置而缺少编排证据与中央账本更新时直接失败。
8. 新增 `tools/test_orchestration_gates.py`，对证据膨胀、覆盖债务清空、陈旧账本、历史证据误解释、缺少评分和低分无证据入选进行对抗测试。
9. 强化第11号协议、14号总控协议、AGENTS、系统清单、扩展注册表与总控流水线：全部编排闸门通过前不得冻结设计合同。
10. 下一次标准方案到期优先项固定为：投注监控、高级状态倍投、模拟/真实切换。证据不足时必须形成隔离、单变量、有限成本探针，不能继续笼统关闭。

## 设计边界

- 不强迫每套方案使用复杂功能；
- 允许平倍最终入选，但必须完成四路具体比较；
- 证据不足功能优先生成隔离、单变量、有限期数和有限成本的行为探针；
- 不允许为了覆盖率把多个未知状态首次混装；
- 不修改现有彩票号码规则或伪造软件字段；
- 历史运行证据保持不可变，不使用未来覆盖账本重新解释旧批次。

## 验收

必须通过：

```bash
python tools/validate_repository.py
python tools/validate_controller_architecture.py
python tools/lottery_controller.py validate
python tools/validate_function_orchestration.py --self-test --scan-runs
python tools/validate_orchestration_scoring.py --scan-runs
python tools/test_orchestration_gates.py
python tools/validate_scheme_orchestration_gate.py
```

负面夹具必须被拒绝：

- 只有一套平倍画像；
- 四个画像只是复制同一结构；
- 缺少压力释放或高级状态路径；
- 更多设置全部只写关闭；
- E2高级状态路径被正式选择；
- 监控从E1自行膨胀为E3；
- 清空中央到期功能；
- 中央覆盖账本不递增；
- 缺少评分卡；
- 选择较低分项目却没有证据化覆盖理由；
- 连续纯平倍达到上限仍无实验或探针。

## PR与校验

- Draft PR：#19
- 分支：`agent/enforce-full-function-orchestration`
- 已验证Head：`4c8ae350c2391b2060247fc743171aad9d34c9c2`
- GitHub Actions：`Validate system repository`
- Run ID：`30881063902`
- Run number：360
- 结论：success
- 自动合并：未启用
- `main`：尚未修改

## 回滚

若独立审查失败，不修改 `main`，保留分支、提交、PR和CI证据。若合并后异常，创建恢复分支，通过revert或按文件恢复到合并前最后一个已验证 `main`；禁止强推和删除失败证据。

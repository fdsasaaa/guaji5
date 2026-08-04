# FUNCTION-ORCHESTRATION-V1 升级记录

日期：2026-08-04  
状态：任务分支候选，必须经CI、独立审查和合并后生效  
基线：`main` @ `3c8757d89b8963be1f166d8cbbc0dd2f91907dc8`  
升级域：SYSTEM + PROGRAM

## 根因

此前协议虽然写明八层能力、资金四路和更多设置审议，但没有机器可执行的证据格式与失败门槛。导演可以用“风险较大”“污染对照”“不启用”几句话跳过监控、跳转、模拟切换、高级倍投和压力释放路径，最终仍反复交付静态号码、顶部轮投和 `1,1,1...`。

## 本次升级

1. 新增 `controller/function_orchestration.json`，固定四类画像、八层能力、资金四路、更多设置、重复限制与覆盖债务门槛。
2. 新增 `controller/templates/function_orchestration.template.json`，作为每个标准方案任务的证据模板。
3. 新增 `tools/validate_function_orchestration.py`，校验：
   - 四类画像齐全；
   - 至少三种实质签名；
   - 每个画像完整填写A—H；
   - 平倍、有限普通、压力释放、高级状态四路均有具体设计和暴露；
   - 至少两类更多设置形成具体候选参数；
   - E3以下功能不得正式入选；
   - 连续纯平倍与重复画像限制；
   - 覆盖债务必须由候选、探针或证据化阻塞关闭；
   - 新状态功能首次使用不得与高级状态资金路径同时正式启用。
4. 强化第11号协议、AGENTS与总控流水线：`function_orchestration.json` 未通过前不得冻结设计合同。
5. GitHub Actions新增自测与运行证据扫描。自测明确证明纯平倍空审议、E2高级倍投正式入选和伪多画像会被拒绝。

## 设计边界

- 不强迫每套方案使用复杂功能；
- 允许平倍最终入选，但必须完成四路具体比较；
- 证据不足功能优先生成隔离、单变量、有限期数和有限成本的行为探针；
- 不允许为了覆盖率把多个未知状态首次混装；
- 不修改现有彩票号码规则或伪造软件字段。

## 验收

必须通过：

```bash
python tools/validate_repository.py
python tools/validate_controller_architecture.py
python tools/lottery_controller.py validate
python tools/validate_function_orchestration.py --self-test --scan-runs
```

并验证以下负面夹具被拒绝：

- 只有一套平倍画像；
- 四个画像只是复制同一结构；
- 缺少压力释放或高级状态路径；
- 更多设置全部只写关闭；
- E2高级状态路径被正式选择；
- 连续纯平倍达到上限仍无实验或探针。

## 回滚

若校验失败，不修改 `main`，保留分支、提交、PR和CI证据。若合并后异常，创建恢复分支，通过revert或按文件恢复到合并前最后一个已验证 `main`；禁止强推和删除失败证据。

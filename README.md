# AI挂机方案生成系统

GitHub仓库是系统唯一正式源。以后通常只需要发送一句任务或方案灵感，不需要重复上传完整工作包。

## 一句话入口

标准口令：

```text
启动彩票总控：读取 fdsasaaa/guaji5 的 main，按本次要求直接生成并交付合格方案套。
```

没有额外要求时，推荐使用仓库内 `15_默认方案任务口述.md` 的完整口述。简化入口仍可使用：

```text
启动彩票总控：读取 fdsasaaa/guaji5 的 main，自主生成并交付一套合格方案。
```

前端口令虽然简单，后端仍必须完成：导演候选设计、冻结合同、执行、验证、审计、有限返工、交付和受控学习。

## 接管入口

依次读取：

1. `AGENTS.md`
2. `SYSTEM_MANIFEST.json`
3. `SYSTEM_STATE.json`
4. `00_启动入口与系统状态.md`
5. `10_静默方案总控与外部参考吸收协议.md`
6. `11_智能功能调度与资金路径编排协议.md`
7. `11B_长生存资金管理与数据成熟度协议.md`
8. `13_GitHub持续工作区与参考灵感自由重构协议.md`
9. `14_导演执行审计学习总控与模块化变更协议.md`
10. `15_默认方案任务口述.md`
11. `controller/pipeline.json`
12. `controller/extensions.json`
13. `controller/bankroll_stress.json`

## 总控工具

```bash
python tools/lottery_controller.py validate
python tools/lottery_controller.py start --request "本次任务要求" --domain SCHEME --domain PPT
```

`tools/lottery_controller.py`负责建立任务证据包、检查状态转移、登记返工、生成回滚计划和清理计划。它不会替代导演的内容判断，但会阻止阶段跳跃、无证据交付和破坏性清理。

## 质量闸门

```bash
python tools/validate_repository.py
python tools/validate_controller_architecture.py
python tools/lottery_controller.py validate
python tools/validate_function_orchestration.py --self-test --scan-runs
python tools/validate_bankroll_stress.py --self-test --scan-runs
python tools/test_bankroll_stress_gates.py
```

只有所有相关校验通过的任务分支才允许进入评审。默认创建Draft PR，不自动合并。

## 长生存资金管理

标准方案不再把倍投当作最后追加的一张倍数表。导演必须按具体玩法联合设计并比较：

- 平投；
- 有限直线倍投；
- 压力释放路径；
- 高级状态资金路径。

用户未指定时默认按5000元本金、最低有效投注0.1元设计，并检查连续挂10、20、30、40、50期的累计投入、剩余本金、下一期投入和命中回收。每次还必须完成理论概率、至少10000条随机路径压力模拟和历史验证。

当前约200期历史数据只属于快速实验层。系统可以据此完成流程、号码来源、方案执行和初步回测验证，但不得据此声称长期安全或稳定收益。数据达到1000、5000、10000和30000期时，触发更高等级的分区、滚动验证、封存样本外和重新校准。

## 可扩展变更域

系统把变更隔离为五类：

- `PPT`：PPT协议、模板、页面、备注、渲染和验收；
- `SCHEME`：方案逻辑、TXT、监控、正反投、枪弹结构和资金路径；
- `PROGRAM`：工具、构建器、校验器、CI和接口；
- `SYSTEM`：总控、状态、版本、协议、学习和回滚；
- `CLEANUP`：多余文件识别、隔离、删除和恢复。

跨域变更必须给出影响报告并运行各域专项校验。清理默认只生成计划，先隔离后删除。

## 重要原则

- 参考方案只是灵感，可大幅改写。
- 无法原样编码时优先重构为可执行TXT。
- 高级功能必须有真实语义，禁止用常量映射伪装。
- 倍投必须经过多路径比较，不能机械默认直线平倍。
- 能追几十期不等于安全；必须量化回撤、回收和资金断裂概率。
- ZIP和PPT是构建产物，源文件才是长期记忆。
- `main`只保存已验证稳定版本；升级失败保留完整证据并通过新提交回滚，禁止强推覆盖历史。

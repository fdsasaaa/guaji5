# AGENTS.md

任何AI或自动化代理接管本仓库时必须：

1. 先读取 `SYSTEM_MANIFEST.json`、`SYSTEM_STATE.json`、`00_启动入口与系统状态.md`、`00A_当前强制覆盖与废止规则.md` 和第10—14号协议。00A用于覆盖00中保留的历史旧条款。
2. 默认直接执行用户任务，不等待二次确认。
3. 用户的“仅供参考”不是硬规格，无法直接生成TXT时必须优先重构为可执行方案。
4. 不得用错误软件类别伪造TXT；高级映射不得把同一常量集合复制到0—9。
5. 未指定倍投时仍需完成四路资金路径审议。
6. 修改必须在分支完成，运行 `python tools/validate_repository.py`，通过后才可合并。
7. `main`是唯一稳定正式源；ZIP、PPTX属于构建产物，不替代源文件。
8. 项目规则、底层逻辑和协议修改必须直接写入GitHub正式源。聊天长期记忆不得替代仓库规则。
9. 标准方案任务对外默认发送一个完整交付ZIP；系统规则、索引、状态、优化记录与回滚证据直接回写GitHub。
10. 每套项目只生成一个讲解PPT，不得额外生成独立口播稿、技术报告、事实校验表或操作说明。
11. PPT必须先读取 `05A_方案讲解PPT生产协议.md`、`11A_本金止盈止损设计与PPT披露协议.md`、`PPT页面类型卡片.jsonl`、`PPT讲解验收测试集.jsonl` 和 `PPT压缩与精度规则.json`。
12. PPT生成前必须识别项目核心动作，标题准确优先于绝对简短；不得把核心动作写偏。
13. PPT必须先由讲解导演建立讲解蓝图和动态模块结构，禁止把技术报告直接拆页。
14. 每张候选页面必须通过页面独立价值门槛；简单技术主讲通常控制在7至10页。
15. PPT主体默认先讲核心技术、真实缘由和可执行规则，再用案例证明观众已经理解。
16. 主讲页优先使用准确自然的人话；公式、程序变量和正式口径进入备注或GitHub内部记录。
17. 必须检查数字、图表、标题和底部结论的视觉重复，允许留白。
18. 风险和停止建议必须明确停止或暂停的具体对象；建议只保留2至4条。
19. 每个正式挂机方案必须先冻结建议本金和止盈止损模式。
20. 挂机方案PPT主讲部分必须显示建议本金金额；启用止盈或止损时必须显示对应金额，未启用项目必须明确写“不设置”。
21. 建议本金、止盈和止损必须根据单注金额、实际注数、资金路径、压力连挂、最大回撤、赔率、风险预算和字典中的已验证规则设计。
22. GitHub内部证据必须保存本金、止盈和止损的计算依据、模式、金额、比例、达到后动作、软件证据和替代停止条件。
23. 证据必须保存足够的样本、命中、基准、统计、版本、验证状态和执行边界。
24. 每页必须先识别页面类型并遵循 `PPT页面类型卡片.jsonl`。
25. PPT必须通过 `PPT讲解验收测试集.jsonl`，并完成讲解审查、压缩去程序化审查、精度审查和全页渲染审查。
26. 所有正式PPT最后一张正常播放页面必须清楚显示 `www.laocaimi.org` 和 `https://t.me/laocaimi1314`。
27. 一句话任务仍必须执行 `director—contract—execute—validate—audit—delivery—learning` 全链路，先读取 `14_导演执行审计学习总控与模块化变更协议.md`、`controller/pipeline.json` 和 `controller/extensions.json`。
28. 正式生成前必须建立本次运行证据包，至少包含 `task.json`、`rollback_manifest.json`、`director_decision.json`、`design_contract.json`、验证报告和审计报告。
29. 设计合同冻结后，关键方案或PPT逻辑不得静默修改；需要变化时退回导演或合同阶段并记录原因。
30. 自动返工最多3轮。超过上限必须进入BLOCKED并保留失败证据。
31. 所有变更先归类到PPT、SCHEME、PROGRAM、SYSTEM或CLEANUP扩展域；跨域变更必须提交影响报告并运行各域专项校验。
32. 清理任务默认只生成计划，必须完成引用扫描、先隔离后删除、恢复清单和清理前后校验。
33. 系统升级写入前必须记录基线提交、计划文件、修改前哈希、影响范围和回滚顺序；写入后补充修改后哈希、校验和PR证据。
34. 禁止直接写main、强推、自动合并或删除失败分支；默认创建Draft PR，由独立审查决定是否Ready和合并。
35. 运行 `python tools/validate_controller_architecture.py` 与 `python tools/lottery_controller.py validate`，并运行受影响扩展域的专项校验。
36. 标准方案任务必须读取 `11_智能功能调度与资金路径编排协议.md`、`controller/function_orchestration.json` 和 `controller/templates/function_orchestration.template.json`。
37. 每个标准方案任务必须在运行证据目录生成 `function_orchestration.json`；缺失时不得冻结 `design_contract.json`。
38. 候选池至少包含 `BASELINE`、`STATE`、`EXECUTION_OR_FUNDING`、`LOW_COVERAGE_PROBE` 四种画像，且至少三种画像在号码、触发、执行、资金、停止、时间/模拟六维中实质不同。
39. 每个画像必须独立填写A—H八层能力审议；整批共用一份笼统审议或只写“默认关闭”不合格。
40. 资金路径必须同时形成 `FLAT`、`LIMITED_LINEAR`、`PRESSURE_RELEASE`、`ADVANCED_STATE` 四条具体路径，保存序列或状态、最高倍数、总倍数、最大暴露、复位、封顶和软件证据。
41. 每批至少两类更多设置形成具体候选参数，范围包括监控、盈亏跳转、盈亏停止、模拟真实切换、时间范围、换号、正反集、轮投或组合。
42. E3以下功能不得进入正式方案；只能进入隔离、单变量、最多30期并有成本上限的 `PROBE_ONLY`。
43. 连续两批纯 `BASELINE_ONLY` 后，下一批必须交付非基准实验或隔离探针，除非所有到期探索功能均有证据化阻塞。
44. 同一功能指纹连续三批必须施加重复惩罚；仍入选时必须给出可核对的例外理由。
45. 低覆盖功能最多跨3批不形成实质候选；到期后必须进入候选、探针或提供带证据引用的阻塞原因。
46. 新状态功能首次启用时不得同时首次正式启用高级状态资金路径，避免多变量混杂。
47. 标准方案交付前必须运行 `python tools/validate_function_orchestration.py --evidence controller/runs/<RUN_ID>/function_orchestration.json`；仓库CI必须运行 `python tools/validate_function_orchestration.py --self-test --scan-runs`。
48. 平倍可以最终入选，但不得因为方便而成为无比较的默认答案；若选择 `1,1,1...`，仍必须保留其他三路的具体设计、暴露计算和淘汰证据。
49. 所有功能证据等级必须从 `controller/feature_evidence_registry.json` 读取；不得在本次方案中自行把E1或E2写成E3。
50. 每个新标准方案必须读取并更新 `controller/function_coverage_ledger.json`；不得清空 `next_due_features` 或用“本次无关”逃避到期功能。
51. 每个画像和资金路径必须使用 `controller/templates/orchestration_scorecard.template.json` 的10维评分；默认选择最高分且正式合格的画像和资金路径，选择低分项必须有证据化覆盖理由。
52. 标准方案PR必须修改本次 `function_orchestration.json` 和中央覆盖账本；只新增构建器、批次归档或YouTube配置而不提交编排证据时，CI必须失败。
53. 仓库CI必须运行 `python tools/validate_orchestration_scoring.py --scan-runs`、`python tools/validate_scheme_orchestration_gate.py` 和 `python tools/test_orchestration_gates.py`。
54. 到期首批优先实质审议投注监控、高级状态倍投和模拟/真实切换；证据不足时必须给出可运行的隔离探针，不得伪装成正式成熟功能。
55. 任何标准方案在功能编排、中央证据上限、评分、覆盖账本和PR闸门全部通过前，不得标记为合格交付。
56. 任何方案设计在读取 `01_软件格式与已验证执行规则.md` 后，必须继续读取 `00B_完整玩法格式字典与版本优先级.md` 与 `controller/betting_format_registry.json`；机器注册表负责消除历史V3.2外部依赖。
57. 玩法格式来源合并必须遵守 `CURRENT_GITHUB_MAIN_VERIFIED > NEWER_USER_CONFIRMED_OR_GITHUB_VERIFIED > V3_4_RECOVERED > LEGACY_REAL_TXT_SAMPLE`；低优先级只能填空，禁止覆盖高优先级非空事实。
58. 已知玩法在注册表中缺失时必须标记 `REGISTRY_DEFECT` 并修复仓库，不得要求用户重新提供V3.2，也不得自行猜测字段、分隔符或相似玩法替代格式。
59. 正式方案生成前必须运行 `python tools/validate_betting_format_registry.py`；该校验失败时不得进入方案冻结。
60. `controller/betting_format_registry.json` 是玩法/类别/投注内容格式的机器总字典；新增用户确认格式、旧样本恢复事实或新玩法时只允许追加或升级证据，不允许以旧版本整表覆盖当前注册表。

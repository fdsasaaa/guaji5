# AGENTS.md

任何AI或自动化代理接管本仓库时必须：

1. 先读取 `SYSTEM_MANIFEST.json`、`SYSTEM_STATE.json`、`00_启动入口与系统状态.md`、`00A_当前强制覆盖与废止规则.md`、`00D_方案与PPT彻底解耦强制覆盖规则.md` 和第10—14号协议。00A/00D用于覆盖历史旧条款。
2. 默认直接执行用户任务，不等待二次确认。
3. 用户的“仅供参考”不是硬规格，无法直接生成TXT时必须优先重构为可执行方案。
4. 不得用错误软件类别伪造TXT；高级映射不得把同一常量集合复制到0—9。
5. 未指定倍投时仍需完成四路资金路径审议。
6. 修改必须在分支完成，运行 `python tools/validate_repository.py`，通过后才可合并。
7. `main`是唯一稳定正式源；ZIP、PPTX属于构建产物，不替代源文件。
8. 项目规则、底层逻辑和协议修改必须直接写入GitHub正式源。聊天长期记忆不得替代仓库规则。
9. 标准方案任务对外默认发送一个完整交付ZIP；系统规则、索引、状态、优化记录与回滚证据直接回写GitHub。
10. **标准方案任务禁止自动生成PPT、PPTX、PPT蓝图、PPT页面脚本或PPT渲染图。** 方案任务与PPT任务必须彻底解耦。
11. 每个标准方案任务必须在完整交付ZIP中生成 `玩家教学素材卡.md`，作为未来独立PPT任务的事实桥梁；素材卡不得包含GitHub、字段、编码、生成器等工程制作信息。
12. `STANDARD_SCHEME_TASK` 不得读取05A/05E/11A等历史PPT协议作为必需依赖，也不得为了未来PPT改变玩法、号码、倍投、资金或验证逻辑。
13. 只有用户**明确二次请求**创建PPT，或粘贴《玩家教学PPT独立创建总控口述》时，才允许进入 `PLAYER_TEACHING_PPT_TASK`。
14. `PLAYER_TEACHING_PPT_TASK` 必须读取 `05F_玩家教学PPT独立二次任务协议.md` 和 `玩家教学PPT独立创建总控口述_V1.0.md`；它只能表达已冻结方案事实，禁止反向修改方案。
15. 独立PPT任务优先读取 `玩家教学素材卡.md`；只有核对事实需要时才读取TXT/工程记录，且工程信息不得进入观众页面。
16. 独立PPT任务必须从真人玩家分享人工投注思路的角度重写故事线，优先自然大白话、第一人称、真实筛选过程，禁止工程报告式拆页。
17. 独立PPT任务必须讲清“为什么选、为什么不选、怎么搭配、连续不中怎么办、什么时候停”；倍投只能解释为资金管理，不得说成提高中奖概率。
18. PPT专项美工、备注、渲染、页面类型、品牌页和PPT验收只在 `PLAYER_TEACHING_PPT_TASK` 中执行，不得成为标准方案CI或交付门槛。
19. 每个正式挂机方案必须先冻结建议本金和止盈止损模式。
20. 标准方案的 `玩家教学素材卡.md` 必须记录建议本金、止盈、止损或“不设置”，并用普通玩家能理解的语言说明资金与降压思路。
21. 建议本金、止盈和止损必须根据单注金额、实际注数、资金路径、压力连挂、最大回撤、赔率、风险预算和字典中的已验证规则设计。
22. GitHub内部证据必须保存本金、止盈和止损的计算依据、模式、金额、比例、达到后动作、软件证据和替代停止条件。
23. 证据必须保存足够的样本、命中、基准、统计、版本、验证状态和执行边界。
24. 独立PPT任务每页必须先识别页面类型并遵循当前PPT专项协议；该要求不进入标准方案任务。
25. 独立PPT任务交付前必须完成讲解审查、去工程化审查、精度审查、全页渲染和文字溢出检查；该要求不进入标准方案任务。
26. 只有用户或当前PPT协议仍要求品牌结束页时，独立PPT最后一张正常播放页面才显示 `www.laocaimi.org` 和 `https://t.me/laocaimi1314`。
27. 一句话标准方案任务仍必须执行 `director—contract—execute—validate—audit—delivery—learning` 全链路，先读取 `14_导演执行审计学习总控与模块化变更协议.md`、`controller/pipeline.json` 和 `controller/extensions.json`。
28. 正式生成前必须建立本次运行证据包，至少包含 `task.json`、`rollback_manifest.json`、`director_decision.json`、`design_contract.json`、验证报告和审计报告。
29. 设计合同冻结后，关键方案逻辑不得静默修改；独立PPT任务若发现事实不足，只能要求补证据或修正素材卡，不得擅自改方案。
30. 自动返工最多3轮。超过上限必须进入BLOCKED并保留失败证据。
31. 所有变更先归类到PPT、SCHEME、PROGRAM、SYSTEM或CLEANUP扩展域；跨域变更必须提交影响报告并运行各域专项校验。标准方案任务不得自动跨入PPT域。
32. 清理任务默认只生成计划，必须完成引用扫描、先隔离后删除、恢复清单和清理前后校验。PPT解耦优先解除引用和降级历史协议，不为清理而误删未来独立PPT仍可复用的资产。
33. 系统升级写入前必须记录基线提交、计划文件、修改前哈希、影响范围和回滚顺序；写入后补充修改后哈希、校验和PR证据。
34. 禁止直接写main、强推、自动合并或删除失败分支；核心协议升级应使用独立PR。
35. 运行 `python tools/validate_controller_architecture.py`、`python tools/lottery_controller.py validate` 和受影响扩展域专项校验；方案/PPT解耦升级必须运行 `python tools/validate_scheme_ppt_decoupling.py`。
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
55. 任何标准方案在功能编排、中央证据上限、评分、覆盖账本、PPT解耦门禁和PR闸门全部通过前，不得标记为合格交付。
56. 任何方案设计在读取 `01_软件格式与已验证执行规则.md` 后，必须继续读取 `00B_完整玩法格式字典与版本优先级.md`、`00C_高级倍投GUI导出强制覆盖规则.md`、`controller/betting_format_registry.json`、`controller/advanced_betting_gui_export_override.json` 和 `controller/legacy_play_grammar_catalog.json`；00C/高级倍投覆盖合同仅在高级倍投冲突处覆盖旧注册表条款。
57. 玩法格式来源合并必须遵守 `CURRENT_GITHUB_MAIN_VERIFIED > NEWER_USER_CONFIRMED_OR_GITHUB_VERIFIED > V3_4_RECOVERED > LEGACY_GENERATOR_DOCS > LEGACY_REAL_TXT_SAMPLE`；低优先级只能填空，禁止覆盖高优先级非空事实、禁令、证据等级或已修复语义。
58. 已知玩法在当前注册表缺失时，先查历史语法目录确定其已知设计语法与当前处置；两层都缺失才标记 `REGISTRY_DEFECT`。不得要求用户重新提供V3.2，也不得自行猜测字段、分隔符或用相似玩法替代。
59. 正式方案生成前必须运行 `python tools/validate_betting_format_registry.py`；该校验失败时不得进入方案冻结。
60. `controller/betting_format_registry.json` 是基础当前可执行状态总表，`controller/advanced_betting_gui_export_override.json` 是高级倍投的更新用户实测覆盖层，`controller/legacy_play_grammar_catalog.json` 是历史完整玩法语法补充表；高级倍投冲突必须优先使用覆盖层。
61. `投注监控`关闭时只允许精确写成 `投注监控=False-`；开启时只允许 `投注监控=True-<非空01序列>`，不得把金额、期数或其他数字串塞进该字段。该规则是主方案“投注监控”字段规则，不等同于高级倍投单局的 `中后监控/挂后监控=True|False`。
62. 投注监控序列语义固定为 `0=挂、1=中`，序列字符集只能是 `0` 和 `1`；`2-9` 均无监控状态含义，因此 `False-50000`、`True-50000`、`True-0121` 等写法一律判定为非法。
63. 历史TXT若出现非法投注监控值，只能作为“旧样本错误证据”保存；不得复制进当前模板、注册表默认值或正式方案。`tools/validate_betting_format_registry.py` 必须持续校验这一硬规则。
64. 用户未明确要求加密或锁定时，所有正式交付的**主方案TXT**必须精确保留空值 `SchemeCreator=`；不得填入方案编号、批次ID、日期、AI名称、作者名或任何非空追踪标识。
65. 打包前必须区分主方案TXT与高级倍投配置TXT。主方案发现 `SchemeCreator=` 非空且未显式要求加密时必须失败；软件原生导出的高级倍投配置允许保留其非空 `SchemeCreator`，不得把主方案空值规则机械套用到 `GJBTScheme` 文件。
66. 标准方案的公开内容桥梁只有 `玩家教学素材卡.md`；不得同时生成“公开视频教学包”或PPT。未来PPT任务通过素材卡重新组织，不直接继承工程叙事。
67. 玩家教学素材卡必须讲清玩法、数据窗口、每个数字为什么被选、为什么不选接近候选、多组如何搭配、人工投注怎么理解、资金如何降压、连续不中如何处理以及风险边界。
68. 素材卡与未来独立PPT均不得把历史命中率包装成未来保证，不得声称倍投提高中奖率。
69. 当前用户实测高级倍投原生导出为16字段：`软件名称,ID,倍数,中后ID,挂后ID,中后监控,中后跳转,挂后监控,挂后跳转,是否盈利跳转,是否亏损跳转,盈利金额,亏损金额,盈利跳转局数,亏损跳转局数,SchemeCreator`；不得再生成旧9字段版冒充当前格式。
70. 高级倍投单局 `中后监控/挂后监控` 允许 `True` 与 `False`；`True`是用户GUI勾选“重新监控”后软件原生导出的已确认序列化值。
71. 高级倍投 `中后跳转/挂后跳转` 使用 `True-主方案名` 或 `False-主方案名`；`True`表示GUI启用跳转，`False`表示未启用，即使False后仍带方案名也不能误判为已跳转。
72. `中后ID/挂后ID` 是高级倍投内部局号流转；`中后跳转/挂后跳转` 是切换主方案；`中后监控/挂后监控` 是重新监控。三层控制必须分别设计与验证。
73. 当前用户软件原生导出的高级倍投文件实测为GBK、无BOM、CRLF；这条更新用户实测证据覆盖旧版“高级倍投一定UTF-8 BOM”的假设。跨主方案后的状态继承/重置、重新监控精确时点、盈亏跳转金额口径仍保持运行待验证。

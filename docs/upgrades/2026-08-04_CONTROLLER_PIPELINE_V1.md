# CONTROLLER-PIPELINE-V1 升级记录

日期：2026-08-04  
状态：已合并并在 `main` 正式启用  
原升级分支：`agent/controller-pipeline-rollback-extensibility`  
基线：`main` @ `6df377889c82ec20f7f8de7c5d7797d898b22454`  
合并提交：`2dc89ebe01f4d2f1804735140ce55c42ee447a5b`  
升级类型：SYSTEM + PROGRAM；不生成彩票方案，不修改既有方案含义，不启用自动合并。

## 一、升级目标

1. 让用户只需一句口令，后端仍完整执行导演、冻结合同、执行、验证、审计、返工、交付和学习。
2. 所有系统升级在写入前具备回滚基线、影响范围和恢复顺序。
3. 把PPT、方案、程序、系统和文件清理隔离成可独立扩展的变更域。
4. 防止小范围修改引发全局规则漂移。
5. 防止“清理多余文件”演变为不可恢复的批量删除。

## 二、新增文件

- `14_导演执行审计学习总控与模块化变更协议.md`
- `controller/pipeline.json`
- `controller/extensions.json`
- `tools/lottery_controller.py`
- `tools/validate_controller_architecture.py`
- `docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.md`
- `docs/upgrades/2026-08-04_CONTROLLER_PIPELINE_V1.rollback.json`

## 三、修改文件

- `AGENTS.md`：把14号协议、状态机、冻结合同、扩展域、回滚和清理纪律加入AI接管入口。
- `README.md`：增加一句话口令、总控工具和五类扩展域说明。
- `SYSTEM_MANIFEST.json`：正式登记14号协议、总控配置、工具、扩展域和回滚策略。
- `13_GitHub持续工作区与参考灵感自由重构协议.md`：增加写入前回滚清单、模块隔离、非破坏性清理和任务证据要求。
- `.github/workflows/validate.yml`：增加总控架构校验、配置校验和任务证据包冒烟测试。
- `.gitignore`：忽略本地 `.runtime/` 运行证据目录，避免临时状态污染正式源。

## 四、核心设计

### 1. 状态机

固定阶段：

```text
INTAKE
→ PREFLIGHT
→ DIRECTOR
→ CONTRACT_FROZEN
→ EXECUTION
→ VALIDATION
→ AUDIT
→ DELIVERY
→ LEARNING
→ COMPLETED
```

失败按类型进入 `REWORK`，最多3轮；超过上限进入 `BLOCKED`。

### 2. 冻结合同

`design_contract.json`保存本次研究问题、数据、候选画像、方案逻辑、监控与切换、资金路径、风险、本金、TXT和PPT合同。关键逻辑变更必须退回导演或合同阶段。

### 3. 扩展域

- PPT
- SCHEME
- PROGRAM
- SYSTEM
- CLEANUP

每个域登记负责路径、保护依赖、专项校验、兼容合同和回滚单元。跨域修改必须给出影响报告。

### 4. 回滚

每次任务建立 `rollback_manifest.json`，记录基线提交、计划文件、修改前后哈希、校验证据和回滚目标。禁止强推，失败分支和失败证据保留。

### 5. 清理

清理默认 `PLAN_ONLY`。先引用扫描，再隔离和恢复清单，最后使用独立PR删除。功能升级PR不得顺手批量清理。

## 五、兼容性

- 不改变现有TXT编码、方案语义或PPT品牌规则。
- 不替换现有 `tools/validate_repository.py`，而是新增独立总控架构校验。
- 不要求立即迁移历史批次。
- 新总控运行目录默认是 `.runtime/lottery-controller`，不提交到GitHub。
- 现有AI仍可按仓库协议执行；总控工具增加证据和状态约束，不负责凭空创造方案逻辑。

## 六、验证命令

CI执行：

```bash
python tools/validate_repository.py
python tools/validate_controller_architecture.py
python tools/lottery_controller.py validate
python tools/lottery_controller.py start --request "CI controller smoke test" --domain SYSTEM --run-id CI-SMOKE --run-root "$RUNNER_TEMP/lottery-controller"
python tools/lottery_controller.py status --run-id CI-SMOKE --run-root "$RUNNER_TEMP/lottery-controller"
```

并继续执行原有PPT专项校验和固定页物化校验。

## 七、回滚计划

若合并后出现问题：

1. 以合并前最后一个已验证 `main` 提交为目标；
2. 新建恢复分支；
3. 使用revert提交或按文件恢复，不强推；
4. 运行仓库总校验、总控校验和受影响域专项校验；
5. 通过独立恢复PR合并；
6. 保留本次失败版本和根因记录。

## 八、已知边界

- 当前总控负责治理、证据、状态和回滚，不替代未来的具体方案生成器和PPT构建器。
- 一句话全自动交付仍依赖接管AI或后续注册的执行处理器完成各阶段产物。
- 本次没有启用自动合并、自动规则晋级或破坏性文件清理。

## 九、PR、合并与校验结果

- PR：#16
- PR标题：`系统：建立一句话总控、回滚与模块化扩展框架`
- 最终Head：`f953a1aaf9ed79cbe2f129128c495c29e826152c`
- 合并提交：`2dc89ebe01f4d2f1804735140ce55c42ee447a5b`
- 合并时间：2026-08-04 12:02（Asia/Singapore）
- GitHub Actions工作流：`Validate system repository`
- 最终合并前Run ID：`30875759115`
- Run number：`257`
- 结果：`success`
- 自动合并：未启用
- `main`：已包含总控协议、状态机、扩展注册表、工具和CI校验

`controller/pipeline.json` 的正式状态为 `ACTIVE`，并记录PR #16及其合并提交；架构校验器阻止其回退为候选状态。

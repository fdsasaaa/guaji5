# AI挂机方案生成系统

私有GitHub仓库是系统唯一正式源。以后通常只需要发送方案灵感，不需要重复上传完整工作包。

## 接管入口

依次读取：

1. `AGENTS.md`
2. `SYSTEM_MANIFEST.json`
3. `SYSTEM_STATE.json`
4. `00_启动入口与系统状态.md`
5. `00A_当前强制覆盖与废止规则.md`
6. `00B_统一交付文件夹规则.md`
7. `10_静默方案总控与外部参考吸收协议.md`
8. `11_智能功能调度与资金路径编排协议.md`
9. `13_GitHub持续工作区与参考灵感自由重构协议.md`

## 质量闸门

```bash
python tools/validate_repository.py
python tools/validate_delivery_folder_policy.py
```

只有校验通过的任务分支才允许合并到`main`。

## 重要原则

- 参考方案只是灵感，可大幅改写。
- 无法原样编码时优先重构为可执行TXT。
- 高级功能必须有真实语义，禁止用常量映射伪装。
- 倍投必须经过多路径比较，不能机械默认直线平倍。
- ZIP和PPT是构建产物，源文件才是长期记忆。
- 标准方案仍生成原方案套ZIP与原PPTX，但对外只发送一个统一交付文件夹ZIP，解压后仅包含这两个文件。

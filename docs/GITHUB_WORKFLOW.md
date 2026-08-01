# GitHub工作流

1. 从`main`创建任务分支：`scheme/<方案ID>`或`upgrade/<版本>`。
2. 读取系统状态和总导演协议。
3. 创建方案源文件、TXT、验证记录和PPT源材料。
4. 更新索引、状态、CHANGELOG和版本号。
5. 运行`python tools/validate_repository.py`。
6. 创建PR；自动检查通过后合并。
7. 需要发布时再生成ZIP/PPTX，构建产物不替代源码。

## 阻断条件

只有仓库不可访问、核心源损坏、关键软件语义无证据且任何安全重构都无法完成时，才向用户报告阻断。

# 固定PPT页内置源数据

本目录保存固定首页与固定末页画面的Base64分片。分片只用于解决GitHub文本接口下的二进制持久化问题，不是人工编辑文件。

使用方式：

```bash
python tools/materialize_ppt_fixed_pages.py
python tools/validate_ppt_fixed_pages.py
```

物化器会生成不可选中的首页背景模板、重新排版的固定第二页、固定最后一页和三页预览模板。禁止手工修改分片。

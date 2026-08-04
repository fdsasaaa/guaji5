# 固定PPT页内置源数据

本目录只保存固定首页与固定末页画面的Base64分片。固定第二页已经取消，不再生成平台联系页。

```bash
python tools/materialize_ppt_fixed_pages.py
python tools/validate_ppt_fixed_pages.py
```

物化器生成不可选中的首页背景模板、固定最后一页和双页预览模板。禁止手工修改分片。

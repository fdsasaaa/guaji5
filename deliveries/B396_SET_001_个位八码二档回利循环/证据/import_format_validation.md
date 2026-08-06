# B396 导入格式验证记录

- 结果：**PASS**
- 主方案：GBK、无BOM、CRLF、30个通用字段+5个策略字段。
- 高级倍投：UTF-8 BOM、CRLF、2局、9字段、倍数1/4。
- 文件引用：`倍投方案=高级倍投主配置` ↔ `GJBTScheme/高级倍投主配置.txt`。

## 自动检查

- PASS：`main_no_utf8_bom`
- PASS：`main_gbk_decode`
- PASS：`main_crlf_only`
- PASS：`main_first_line_false`
- PASS：`main_second_line_strategy`
- PASS：`main_field_order`
- PASS：`main_ends_two_blank_lines`
- PASS：`main_gjbt_enabled`
- PASS：`positive_group_count_10`
- PASS：`positive_each_8_unique_digits`
- PASS：`negative_group_count_10`
- PASS：`negative_each_2_unique_digits`
- PASS：`cfg_utf8_bom`
- PASS：`cfg_crlf_only`
- PASS：`cfg_row_count_2`
- PASS：`cfg_field_order`
- PASS：`cfg_no_zero_multiplier`
- PASS：`cfg_ids`
- PASS：`cfg_multipliers_1_4`
- PASS：`cfg_d_mode_jumps`
- PASS：`cfg_filename_matches_main`

## 尚需人工验证

- 导入后8码正投集合是否完整显示。
- 第1局未中是否进入第2局，第2局命中是否回第1局。
- 第二局未中后人工停止，不继续第三期。

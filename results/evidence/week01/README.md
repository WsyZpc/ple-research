# 第一周小批量实验的评分证据

六题各保留 delivery-v1 最近一次正常结束的测量，另保留 LES 题 minimal 对照和火灾题 custom-openai 原版对照。同题的两行可直接比较。每个 results.json 来自所属批次，多题批次包含该批次的全部任务；按任务 ID 查分。为便于分享，将两个本机目录字段改为相对路径。评分 JSON、所列交付件与未捕获记录均按原文件复制。PDF 为评分器从交付件转换的版本。

| 任务 | 基线 | 原始批次 ID | 实测得分 | 运行与评分 | 交付或缺失证据 |
| --- | --- | --- | ---: | --- | --- |
| data-center-site-model | delivery-v1 | `qwen-custom-delivery-v1-six-r01-data-center-site-model-20261120-074143-124238` | 0.0 | [结果](data-center-site-model/delivery-v1/results.json) · [评分](data-center-site-model/delivery-v1/metrics.json) | — |
| engineers-estimate-check | delivery-v1 | `qwen-custom-delivery-v1-six-r01-engineers-estimate-check-20261120-082335-359999` | 0.065217 | [结果](engineers-estimate-check/delivery-v1/results.json) · [评分](engineers-estimate-check/delivery-v1/grade.json) | — |
| fill-compaction-acceptance | delivery-v1 | `qwen-custom-delivery-v1-six-r01-fill-compaction-acceptance-20261120-081433-612188` | 0.138889 | [结果](fill-compaction-acceptance/delivery-v1/results.json) · [评分](fill-compaction-acceptance/delivery-v1/grade.json) | — |
| fire-test-validation-memo | custom-openai | `qwen-custom-openai-fire-validation-20261120-001318` | 0.0 | [结果](fire-test-validation-memo/custom-openai/results.json) · [评分](fire-test-validation-memo/custom-openai/grade.json) | [no_output.txt](fire-test-validation-memo/custom-openai/no_output.txt) |
| fire-test-validation-memo | delivery-v1 | `qwen-custom-openai-delivery-v1-fire-20261120-004629` | 0.25 | [结果](fire-test-validation-memo/delivery-v1/results.json) · [评分](fire-test-validation-memo/delivery-v1/grade.json) | [Bianca_email_paragraph.docx](fire-test-validation-memo/delivery-v1/Bianca_email_paragraph.docx) · [E119_validation_memo.docx](fire-test-validation-memo/delivery-v1/E119_validation_memo.docx) |
| landscape-sheet-revision | delivery-v1 | `qwen-custom-delivery-v1-six-r01-landscape-sheet-revision-20261120-013437-820274` | 0.155844 | [结果](landscape-sheet-revision/delivery-v1/results.json) · [评分](landscape-sheet-revision/delivery-v1/grade.json) | — |
| les-mesh-resolution | delivery-v1 | `qwen-custom-delivery-v1-six-r01-les-mesh-resolution-20261120-012734-999608` | 0.02439 | [结果](les-mesh-resolution/delivery-v1/results.json) · [评分](les-mesh-resolution/delivery-v1/grade.json) | [CFDME-2025-041_resolution_note_revA.pdf](les-mesh-resolution/delivery-v1/CFDME-2025-041_resolution_note_revA.pdf) |
| les-mesh-resolution | minimal | `qwen-minimal-four-tasks-r01` | 0.02439 | [结果](les-mesh-resolution/minimal/results.json) · [评分](les-mesh-resolution/minimal/grade.json) | [CFDME-2025-041_resolution_note_revA.pdf](les-mesh-resolution/minimal/CFDME-2025-041_resolution_note_revA.pdf) |

[六题复盘](../../../docs/week01-baseline-analysis.md) · [复跑说明](../../../baselines/README.md)

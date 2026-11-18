# Kaggle PLE 公开开发集全量精准统计（共 29 个任务）

## 1. 四大学科任务数量分布
| 工程学科 (Discipline) | 任务数 (#) | 占比 (%) |
| :--- | :---: | :---: |
| Electrical (电气) | 9 | 31.0% |
| Mechanical (机械) | 8 | 27.6% |
| Civil (土木) | 8 | 27.6% |
| Structural (结构) | 4 | 13.8% |

## 2. 数据构建与测评机制分布（核心架构发现）
| 测评机制类型 | 任务数 (#) | 占比 (%) |
| :--- | :---: | :---: |
| Script-Verify (脚本验证) | 15 | 51.7% |
| Criteria+Verify (混合准则) | 14 | 48.3% |

## 3. 29 个任务全量明细扫描表
| 任务文件夹名 (Task ID) | 所属学科 | 挂载目录 | 附件数 | CAD | 表格 | PDF | WebApp | 测评机制 | 评分细度 | 指令词数 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
| `backfeed-energization-reply` | Electrical (电气) | `files` | 95 | No | Yes | Yes | Yes | Criteria+Verify (混合准则) | 17 条准则 | 260 |
| `cooling-water-flush-plan` | Mechanical (机械) | `filesystem` | 51 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 6 个验证脚本 | 2040 |
| `data-center-site-model` | Civil (土木) | `filesystem` | 6 | No | No | No | No | Script-Verify (脚本验证) | 14 个验证脚本 | 550 |
| `data-hall-device-takeoff` | Electrical (电气) | `filesystem` | 38 | No | No | Yes | No | Script-Verify (脚本验证) | 20 个验证脚本 | 914 |
| `data-hall-mep-routing` | Mechanical (机械) | `filesystem` | 8 | No | No | No | No | Script-Verify (脚本验证) | 16 个验证脚本 | 831 |
| `data-hall-mep-routing-offset` | Mechanical (机械) | `filesystem` | 8 | No | No | No | No | Script-Verify (脚本验证) | 16 个验证脚本 | 1072 |
| `division-26-specifications` | Electrical (电气) | `filesystem` | 121 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 13 个验证脚本 | 1000 |
| `emergency-spillway-check` | Civil (土木) | `files` | 56 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 15 条准则 | 174 |
| `engineers-estimate-check` | Civil (土木) | `files` | 56 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 10 条准则 | 195 |
| `eor-review-corrections` | Structural (结构) | `filesystem` | 94 | No | Yes | Yes | No | Script-Verify (脚本验证) | 11 个验证脚本 | 2048 |
| `fill-compaction-acceptance` | Civil (土木) | `files` | 55 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 28 条准则 | 150 |
| `fire-solve-convergence` | Mechanical (机械) | `files` | 50 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 43 条准则 | 299 |
| `fire-test-validation-memo` | Mechanical (机械) | `filesystem` | 50 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 48 条准则 | 462 |
| `footing-settlement-verification` | Civil (土木) | `files` | 55 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 17 条准则 | 123 |
| `foundation-strategy` | Civil (土木) | `filesystem` | 50 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 13 个验证脚本 | 1943 |
| `frame-extension-method` | Mechanical (机械) | `filesystem` | 35 | No | Yes | No | No | Script-Verify (脚本验证) | 9 个验证脚本 | 1997 |
| `heat-rejection-life-cycle-cost` | Mechanical (机械) | `filesystem` | 50 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 8 个验证脚本 | 3272 |
| `landscape-sheet-revision` | Civil (土木) | `filesystem` | 112 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 18 条准则 | 122 |
| `les-mesh-resolution` | Mechanical (机械) | `files` | 50 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 14 条准则 | 172 |
| `lv-cable-sizing` | Electrical (电气) | `filesystem` | 32 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 16 个验证脚本 | 2178 |
| `mv-conveyance-study` | Electrical (电气) | `filesystem` | 66 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 10 个验证脚本 | 1341 |
| `permission-to-operate-memo` | Electrical (电气) | `files` | 95 | No | Yes | Yes | Yes | Criteria+Verify (混合准则) | 13 条准则 | 276 |
| `pre-application-capacity-response` | Electrical (电气) | `files` | 95 | No | Yes | Yes | Yes | Criteria+Verify (混合准则) | 14 条准则 | 139 |
| `roof-deck-design` | Structural (结构) | `filesystem` | 31 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 14 个验证脚本 | 1636 |
| `seismic-diaphragm-shear` | Structural (结构) | `filesystem` | 39 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 11 个验证脚本 | 954 |
| `shoring-design-verification` | Civil (土木) | `files` | 55 | No | Yes | Yes | No | Criteria+Verify (混合准则) | 30 条准则 | 228 |
| `solar-supplemental-review` | Electrical (电气) | `files` | 53 | No | Yes | Yes | Yes | Criteria+Verify (混合准则) | 22 条准则 | 88 |
| `solar-witness-test-package` | Electrical (电气) | `files` | 53 | No | Yes | Yes | Yes | Criteria+Verify (混合准则) | 34 条准则 | 236 |
| `wind-diaphragm-shear` | Structural (结构) | `filesystem` | 74 | Yes | Yes | Yes | No | Script-Verify (脚本验证) | 13 个验证脚本 | 1242 |
# 第 1 周 · PLE 开发集调研与基线

## 数据范围与构建

Physical-Engineering’s Last Exam（PLE）用真实工程工作形式测量模型和代理的表现。完整基准有 85 题，本次研究使用 Hugging Face 的 29 题开发集。当前本地数据版本为 `b3857a3fea39a695e18f845d4a88f29442e96e75`。开发集的学科分布为电气 9 题、机械 7 题、土木 9 题、结构 4 题。

作者采用两种构建路线。专家编写路线由执业工程师完成任务及其专业评审标准。协同路线由工程师确定真实任务，代理协助搭建并完善环境与评测，随后由工程专家验证。每题包含自然语言指令、独立任务环境和评分器。环境可包含图纸、表格、规范、计算工具和模拟应用。研究组可从官方分发入口申请访问对应资料。

来源：[PLE 论文](https://arxiv.org/abs/2610.30537) · [官方数据集](https://huggingface.co/datasets/google/physical-engineerings-last-exam)

## 问题分类

下表是本次调研的主类标注。每题归入一个主类，代表题用官方 ID 标识。六类共计 29 题。

| 主类 | 数量 | 判定依据 | 代表任务 |
| --- | ---: | --- | --- |
| 规范流程与技术决策 | 8 | 从适用规程和记录推导是否放行、下一动作与责任方。 | `backfeed-energization-reply` |
| 空间规划与建模 | 3 | 把图纸、坐标和空间约束转成可检查的几何或线路网络。 | `data-center-site-model` |
| 跨文档审计与修订 | 5 | 核对多份资料的冲突和版本，使更正传递到各交付物。 | `data-hall-device-takeoff` |
| 工程计算与校核 | 5 | 按适用工况和参数复算，核对量纲、边界条件与验收限值。 | `emergency-spillway-check` |
| 仿真验证与诊断 | 3 | 定位已有仿真异常，核对试验、网格、求解设置或不确定度。 | `fire-solve-convergence` |
| 多约束设计与选型 | 5 | 在工程约束下比较可行方案与成本等目标。 | `foundation-strategy` |

## 评测机制

开发集有 12 道程序检查（`checks`）、14 道按专家评分细则由模型评判（`rubric`），以及 3 道结合两者（`checks-judge`）。代理在隔离任务环境里读取工程资料并产出交付物，评分器单独检查。实验表记录任务的归一化分数、运行状态、耗时和 Token 数。具体题目的通过条件和容差以对应题面及官方评测为准。

来源：[PLE 本地评测文档](https://github.com/google-research/ple/blob/main/eval/README.md)

## 基线实验

本周用官方 `minimal` harness 跑 Qwen。首题选择 `data-center-site-model`，交付物为 IFC 模型，采用程序检查。先验证 WSL 内 Docker 和模型连通性，再运行该任务。待确认的模型 ID、服务商、推理设置、数据版本和 harness 提交号在实验表中登记。计划行状态为 `planned`，得到实际评测结果后补记录。[基线实验表](../results/baseline.csv)

## 29 题目录

| 编号 | 任务 ID | 学科 | 主类 | 评分 | 原工作表核实状态 |
| ---: | --- | --- | --- | --- | --- |
| 01 | `backfeed-energization-reply` | 电气 | 规范流程与技术决策 | `rubric` | 目录拟分 |
| 02 | `cooling-water-flush-plan` | 机械 | 规范流程与技术决策 | `checks` | 目录拟分 |
| 03 | `data-center-site-model` | 土木 | 空间规划与建模 | `checks` | 目录拟分 |
| 04 | `data-hall-device-takeoff` | 电气 | 跨文档审计与修订 | `checks` | 目录拟分 |
| 05 | `data-hall-mep-routing` | 机械 | 空间规划与建模 | `checks` | 题面已核对 |
| 06 | `data-hall-mep-routing-offset` | 机械 | 空间规划与建模 | `checks` | 题面已核对 |
| 07 | `division-26-specifications` | 电气 | 规范流程与技术决策 | `checks` | 题面已核对 |
| 08 | `emergency-spillway-check` | 土木 | 工程计算与校核 | `rubric` | 题面已核对 |
| 09 | `engineers-estimate-check` | 土木 | 跨文档审计与修订 | `rubric` | 题面已核对 |
| 10 | `eor-review-corrections` | 结构 | 跨文档审计与修订 | `checks-judge` | 题面已核对 |
| 11 | `fill-compaction-acceptance` | 土木 | 跨文档审计与修订 | `rubric` | 题面已核对 |
| 12 | `fire-solve-convergence` | 机械 | 仿真验证与诊断 | `rubric` | 题面已核对 |
| 13 | `fire-test-validation-memo` | 机械 | 仿真验证与诊断 | `rubric` | 题面已核对 |
| 14 | `footing-settlement-verification` | 土木 | 工程计算与校核 | `rubric` | 题面已核对 |
| 15 | `foundation-strategy` | 土木 | 多约束设计与选型 | `checks-judge` | 题面已核对 |
| 16 | `frame-extension-method` | 土木 | 规范流程与技术决策 | `checks` | 题面已核对 |
| 17 | `heat-rejection-life-cycle-cost` | 机械 | 多约束设计与选型 | `checks` | 题面已核对 |
| 18 | `landscape-sheet-revision` | 土木 | 跨文档审计与修订 | `rubric` | 题面已核对 |
| 19 | `les-mesh-resolution` | 机械 | 仿真验证与诊断 | `rubric` | 题面已核对 |
| 20 | `lv-cable-sizing` | 电气 | 多约束设计与选型 | `checks-judge` | 题面已核对 |
| 21 | `mv-conveyance-study` | 电气 | 多约束设计与选型 | `checks` | 题面已核对 |
| 22 | `permission-to-operate-memo` | 电气 | 规范流程与技术决策 | `rubric` | 题面已核对 |
| 23 | `pre-application-capacity-response` | 电气 | 规范流程与技术决策 | `rubric` | 题面已核对 |
| 24 | `roof-deck-design` | 结构 | 多约束设计与选型 | `checks` | 题面已核对 |
| 25 | `seismic-diaphragm-shear` | 结构 | 工程计算与校核 | `checks` | 题面已核对 |
| 26 | `shoring-design-verification` | 土木 | 工程计算与校核 | `rubric` | 题面已核对 |
| 27 | `solar-supplemental-review` | 电气 | 规范流程与技术决策 | `rubric` | 题面已核对 |
| 28 | `solar-witness-test-package` | 电气 | 规范流程与技术决策 | `rubric` | 题面已核对 |
| 29 | `wind-diaphragm-shear` | 结构 | 工程计算与校核 | `checks` | 题面与资料已核对 |

<!-- ple-week01-progress -->
# PLE 研究进度

## 第二周｜RSI 人工编排

对 LES 网格分辨率、填土压实验收和景观 L-4 修订进行了编排尝试，涉及十条问题中的 P01–P05、P08。P08 已按批准函和交付物人工核验，填土 P04–P05 有原题材料的固定回复对照证据，LES 已留下真题运行与复算诊断。

[本周 README 与证据索引](results/evidence/week02/README.md) · [十条问题 CSV](results/evidence/week02/周任务_10条修复对照.csv) · [十条问题 Excel](results/evidence/week02/周任务_10条修复对照.xlsx) · [RSI 项目源码](experiments/rsi/)

## 第一周｜数据集调研与六题基线

**第一周已完成 29 道公开开发集任务的调研，并用 `qwen3.5-plus` 完成六题小批量基线复盘。** 交付修正版 `delivery-v1` 在六题上均取得正常结束的测量。按每题最近一次正常结束的结果等权计算，平均得分为 **0.1057**（满分 1），其中 5 题获得部分分，1 题为零分。[六题结果与逐题失分分析](docs/week01-baseline-analysis.md)

| 检查项 | 本周进度 | 查看材料 |
| --- | --- | --- |
| 数据集与任务分类 | 梳理了数据构建方式和评分机制，按工程目标将 29 题归为 6 类，每类列出判定依据和代表题。 | [分类与代表题](docs/week01.md#问题分类) · [29 题逐题调研](data/work/PLE_research.md) |
| 基线代码 | 保存了 minimal、custom-openai 原版和 delivery-v1 三份代码快照，附 WSL 单题复跑说明。 | [基线代码与复跑说明](baselines/README.md) |
| 实验表 | 六题历次实验共 17 个批次、21 条实际运行记录，含同题复跑。其中 13 条取得评分，8 条未取得测量。 | [实验总表](results/baseline.csv) · [minimal 明细](results/minimal_batch_tasks.csv) · [custom-openai 系列明细](results/custom_openai_batch_tasks.csv) |
| 评分证据 | 可按题目核对评分或验证器输出，并查阅火灾验证题的 Word 和 LES 网格题的 PDF。 | [六题评分证据与交付件](results/evidence/week01/README.md) |

**下一步**是将同一基线配置扩展到 29 题，按唯一题目统计覆盖率、得分分布和各类失分问题的出现比例，另行记录环境或接口故障。
<!-- /ple-week01-progress -->

# PLE 第二周｜RSI 人工编排与工程复核

本周在 RSI 中尝试了三道 PLE 开发题，覆盖十条问题清单中的 P01–P05、P08。保留了任务输入对应的证据引用、执行状态、Word 交付以及可重放的节点结果。

## 结果与复核材料

| 任务 | 编排与核验结果 | 证据 |
| --- | --- | --- |
| LES 网格分辨率（P01–P03） | 参数提取 → 物理复算 → 实体和来源审计 → 覆盖审计 → 门禁 → 有限局部修订或待核交付。真题两轮重试后保持 `EVIDENCE_HOLD`，Word 回读通过。C3 仍为 7.52，回放定位到参数实体或适用范围不匹配。P01、P02 待修复，P03 已保留审查项开放，仍缺 SGS 闭合记录位置。 | [真题黑板](les/run-joro928i/blackboard.json) · [Word](les/run-joro928i/CFDME-2025-041_resolution_note_revA.docx) · [后端单节点回放](les/single-node-live/replay-result.json) · [离线诊断](les/offline-diagnosis.json) · [历史回放评分](les/scoring/grade-les-tsYYxeD9/) |
| 填土压实验收（P04–P05） | 基线 **15/108**，首轮固定回复回放 **24/108**。覆盖门禁版用同一初稿验证，四个检测点和其他必查项进入局部修订，覆盖清单从 **0/10** 到 **10/10**。新 Word 回读通过，Item 054 保持开放。 | [首轮评分](fill/scoring/grade-fill-compaction-acceptance-1rM5Jqmx/grade.json) · [新版回放和交付物](fill/coverage-gate/) |
| 景观 L-4 修订（P08） | 核对批准函 Condition 14、HOA 公共区域、图纸数量和听证日历 → 经证据门禁导出备忘录 → 回读。原评分器本地复测 **70/77（90.9%）**，基线 **12/77**。P08 部分修复，**0/20 → 13/20**。图纸 58 株、复算 208 株。书面重大变更判定待取得，暂不承诺 11 月 30 日重提，状态为 `EVIDENCE_HOLD`。 | [评分明细](landscape/scoring/grade-landscape-sheet-revision-3ukqY0iP/grade.json) · [运行结果](landscape/scoring/grade-landscape-sheet-revision-3ukqY0iP/results.json) · [黑板](landscape/blackboard.json) · [备忘录](landscape/Memo_to_Callaway_L4_Revision.docx) · [版面预览](landscape/render/memo.pdf) |

景观题逐项评分中，Condition 14 引用（#1）得 **5/5**，对本次修订的适用性判断（#2）得 **8/8**。唯一扣分项（#0，**0/7**）是备忘录缺一句直接表明 Condition 14 决定本次 L-4 行道树修订能否进入工作人员层级处置（staff-level action）。[逐项评分](landscape/scoring/grade-landscape-sheet-revision-3ukqY0iP/grade.json)

填土编排在覆盖审计阶段增加了由原始材料定位的必查项。门禁可以把有来源的缺口送回求解节点局部修订。导出后，Word 回读核对 FD-14 至 FD-17 和 RFI 079 的五条已通过覆盖检查的原句。删掉 FD-14 的处置句后，回读测试会报错。两轮均使用固定回复，因此分数用于观察相关能力和交付链路。 [同初稿对照](fill/coverage-gate/comparison.json)

LES 的历史基线为 2/82，审计意见重建的历史回放为 7/82。两次用到的交付材料不同。LES 仍待新版评分。P06、P07、P09、P10 等待本轮复测。

## 表格与其他证据

- [10 条问题对照 CSV（含景观和填土复测记录）](周任务_10条修复对照.csv) · [10 条问题对照 Excel（评分前快照）](周任务_10条修复对照.xlsx)
- [六题基线评分及验证器输出](baseline/)
- [LES 历史评测目录](les/scoring/) · [填土执行日志](fill/runtime.log) · [填土离线联调样例](fill/fixture/)
- [节点回放与通信故障证据](节点回放与通信故障证据.csv) · [故障注入、恢复和 Word 回放快照](recovery/)
- [后端联调截图](setup/work1.png) · [画布初始化截图](setup/work2.png)。两张图记录环境联调。三道真题逐次从画布发起的运行截图待补。

表格证据路径相对于本目录。原始黑板和运行快照内的本机路径保留为运行元数据。可直接从本目录打开相应的交付物和证据。

## 原子能力与代码

共注册九个通用原子能力：工作区侦察、工程提取与求解、实体与来源隔离审计、集合覆盖与归因审校、证据完备性门禁、产物回读、物理派生量复算、定向补证、修订保留性检查。题目专用节点负责 LES Word 导出、填土模板填写和景观资料核对及备忘录生成。

- [前端 rsi-flow-platform](../../../experiments/rsi/rsi-flow-platform/)
- [画布组件 rsi-flow-visual](../../../experiments/rsi/rsi-flow-visual/)
- [后端 rsi-flow-spring-boot](../../../experiments/rsi/rsi-flow-spring-boot/) · [流程定义](../../../experiments/rsi/rsi-flow-spring-boot/core-flow/src/main/resources/flow/Orchestration/) · [原子能力注册](../../../experiments/rsi/rsi-flow-spring-boot/core-flow/src/main/resources/flow/Skills/)

## 复跑

将三个项目保持在 `experiments/rsi` 下的同级目录。前端使用本地画布包，设置 `RSI_BACKEND_ORIGIN` 为本机后端地址。后端需要本地 RSI 依赖及任务材料，在 IDEA 中重新构建并启动本机配置，脚本默认使用 18080 端口。将 `PLE_TASK_ROOT` 指向原题目录的父目录，并按需在本机配置模型访问。后端的 `test`、`remote` 数据源从 `RSI_DB_URL`、`RSI_DB_USERNAME`、`RSI_DB_PASSWORD` 获取配置。

从仓库根目录在 PowerShell 执行一条对应任务的命令。

```powershell
& .\experiments\rsi\run_les_review.ps1 -TaskId les-mesh-resolution -TaskRoot '<原题目录的父目录>'
& .\experiments\rsi\run_les_review.ps1 -TaskId fill-compaction-acceptance -TaskRoot '<原题目录的父目录>'
& .\experiments\rsi\run_les_review.ps1 -TaskId landscape-sheet-revision -TaskRoot '<原题目录的父目录>'
```

已有黑板可以通过 [replay_review.py](../../../experiments/rsi/replay_review.py) 复算或重新导出。出现 `TRANSPORT_PAUSED` 时，从该次运行的 `final.json` 执行 `resume`。通信重试与工程重试独立记录。景观真题已在 RSI 引擎跑完，最新一次 HTTP 入口重跑返回 700，具体原因待结合后端日志定位。

# PLE 第一周基线代码与单题复跑

三个目录保存历史运行打包清单里的源文件。逐个文件按各批次 export.json 的 Git blob 哈希核对。minimal 有未提交的实验修改，复跑请使用此处快照。delivery-v1 加入交付检查。各目录沿用原项目的版权声明。

| 目录 | 实验入口名称 | 原本地 commit | 运行源文件树摘要 |
| --- | --- | --- | --- |
| minimal | ple-minimal-baseline | `5197d6dd9a9b47d5a3b0cc72e01332fc40f6c553` | `20900dab39df3f8265e267501348acace15133570dbba200ce58513b3e6799c0` |
| custom-openai | ple-custom-openai-baseline | `b8aca70a25538b65078d0119513360687a4e6a70` | `acd9d40d2cae210968b2c22587c91b00b43720f9647b9528903310da1bdc86da` |
| delivery-v1 | ple-custom-openai-baseline-delivery-v1 | `8ad0bf83fcabeb93ce265232a94db4bcf93127fe` | `dbaefc9e0490d2366b2169efb5bcb54e896b9ce1fe6feae0ea9b92af66487835` |

## 在 Ubuntu / WSL 中复跑 LES 网格题

准备 Docker Desktop 的 WSL 集成、uv、官方 PLE 评测器和公开开发集，将下方路径改为本机绝对路径。实验机使用的评测器 checkout 为 `8320f0402fdca9f42476607f72bcfd5271cd50c9`。任务目录应包含 `les-mesh-resolution/task.toml`。本实验通过配置的兼容服务调用 qwen3.5-plus，使用本地评测模式。

```bash
RESEARCH="$HOME/ple_harness"
KIT="$RESEARCH/ple"
TASKS="$RESEARCH/data/tasks"
cd "$KIT"
read -rsp 'Model API key: ' MODEL_API_KEY
echo
export MODEL_API_KEY
export JUDGE_BASE_URL="https://uniapi.thingo.com.cn/v1"
export JUDGE_MODEL="qwen3.5-plus"
export JUDGE_API_KEY="$MODEL_API_KEY"
uv run python eval/run.py "$RESEARCH/baselines/delivery-v1" \
  --tasks-dir "$TASKS" --tasks les-mesh-resolution \
  --trials 1 --attempts 1 --no-export \
  --out "runs/repro-delivery-les-$(date +%Y%m%d-%H%M%S)"
```

切换基线时，把入口换成 `$RESEARCH/baselines/minimal` 或 `$RESEARCH/baselines/custom-openai`，使用新的输出目录。评测会调用模型和裁判；复跑分数可能不同。历史成绩见[六题复盘](../docs/week01-baseline-analysis.md)和[逐题证据](../results/evidence/week01/README.md)。

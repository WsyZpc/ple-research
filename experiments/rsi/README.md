# RSI 前后端联调实验

2026-11-24 的本地实验快照。三个目录保持同级，前端通过 `file:../rsi-flow-visual` 加载画布组件。

| 目录 | 上游仓库、分支和起点 | 本周调整 |
| --- | --- | --- |
| rsi-flow-spring-boot | [ymxiong/rsi-flow-spring-boot](https://github.com/ymxiong/rsi-flow-spring-boot)，master，254574c | Windows IDEA、Java 8，AppTestStarter Windows 启动配置使用 18080。FlowCodeRun 将收到的 structure 注册为 result，用于核对接口往返。 |
| rsi-flow-platform | [ymxiong/rsi-flow-platform](https://github.com/ymxiong/rsi-flow-platform)，dev_main，a82a93a | WSL、nvm Node 24、pnpm 10。开发代理指向 127.0.0.1:18080，包含 rc-trigger、rc-align 的 React 19 补丁。 |
| rsi-flow-visual | [ymxiong/rsi-flow-visual](https://github.com/ymxiong/rsi-flow-visual)，dev_main，43b8f53 | 包含联调所用的 dist 构建产物。 |

在原实验环境中，在前端目录执行 `pnpm install --frozen-lockfile` 和 `pnpm dev`，访问 http://localhost:3000 。后端使用实验环境的 Maven 仓库访问设置。test 和 remote 配置通过 `RSI_DB_PASSWORD` 读取数据库密码。

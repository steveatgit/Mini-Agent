# OSS Maintainer Agent 3 分钟 Demo 脚本

目标：在 3 分钟内讲清楚这个项目不是聊天机器人，而是一个能处理真实 issue-to-patch 闭环的本地维护 Agent。

## 1. 项目目标

开场直接说：

“这个项目是一个本地运行的开源仓库维护 Agent。用户给我一个 issue 和测试命令，它会先理解问题，再定位文件，生成补丁，跑验证，最后输出 patch、PR 描述和完整运行报告。”

## 2. Workflow 图

展示 `docs/OSS_MAINTAINER_AGENT_DEV_CN.md` 里的 workflow 或用一句话说明：

`repo_scan -> issue_triage -> context_select -> plan_patch -> implement_patch -> run_verification -> reflect_failure -> package_artifacts`

补一句：

“默认走 LangGraph，环境里没有 LangGraph 时自动回退到同样顺序的本地流程。”

## 3. 一次成功修复

演示一个 `maintain-eval` fixture：

```bash
uv run python -m mini_agent.cli maintain-eval \
  --fixture-root evals/fixtures \
  --tasks-dir evals/tasks \
  --no-langgraph
```

讲点：

- 它会把 fixture repo 复制到临时目录再运行。
- `run_summary.md` 会写出节点耗时、测试耗时和模型调用次数。
- `eval_report.md` 会汇总通过率、token 用量和失败分类。

## 4. 一次失败反思

选 `failure-001`：

- 说明 verification 命令故意失败。
- 强调报告里会保留 `failure_category` 和 `failure_summary`。
- 如果启用了 implementer 和 verifier，可以展示失败后进入 reflection，再决定是否重试。

## 5. 结尾

收束成一句：

“这个项目的重点不是生成一段代码，而是把 issue、补丁、验证、失败反思和交付物串成一个可审计的工程闭环。”

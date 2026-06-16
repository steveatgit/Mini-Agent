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
  --output-dir workspace/maintainer-fixture-eval \
  --llm-plan \
  --llm-implement \
  --llm-reflect \
  --llm-pr
```

讲点：

- 它会把 fixture repo 复制到临时目录再运行。
- 评测器会先读 `issue.md`、`test_command.txt`、`repo_ref.txt` 等任务文件，再把对应 fixture 仓库作为起点。
- `issue_triage`、`context_select`、`plan_patch`、`implement_patch`、`reflect_failure`、`package_artifacts` 会按顺序执行，默认走 LangGraph，环境里没有 LangGraph 时自动回退到同样顺序的本地流程。
- `run_summary.md` 会写出节点耗时、测试耗时、模型调用次数和 token 用量。
- `eval_report.md` 会汇总通过率、token 用量、平均耗时、失败分类和每个任务的 `repo_source` / `failure_summary`。
- 如果本地没有配置 maintainer models，这条命令会回退到规则版实现，所以要想看到真正的修复结果，需要先配置 `tools.maintainer_models`。

预期执行过程：

1. 读取 `evals/tasks/<task-id>/issue.md` 和 `repo_ref.txt`。
2. 复制 `evals/fixtures/<repo_ref>/repo/` 到临时目录并初始化成 git 仓库。
3. 扫描仓库，生成 repo map 和上下文选择。
4. 由 planner 生成结构化计划。
5. 由 implementer 生成并应用 unified diff。
6. 运行 `test_command.txt` 指定的验证命令。
7. 如果失败，verifier 反思是否值得重试。
8. 产出 `final.diff`、`final.patch`、`pr_description.md`、`run_summary.md`、`state.json`、`tool_trace.jsonl`，并在评测目录写出 `eval_results.json` 和 `eval_report.md`。

预期结果：

- `python-cli-001`、`python-cli-002`、`docs-001` 这 3 个任务应当通过。
- `failure-001` 应当失败，并在报告里保留 `failure_category` 和 `failure_summary`。
- `eval_report.md` 会显示整体通过率，以及每个任务的来源和失败原因。
- `evals/tasks/<task-id>/issue.md` 写这个任务要修什么问题。
- `evals/tasks/<task-id>/test_command.txt` 写验证命令，告诉评测器怎么判断修复是否成功。
- `evals/tasks/<task-id>/repo_ref.txt` 指向对应的 fixture 仓库名，例如 `python-cli-001`。
- `evals/tasks/<task-id>/expected_files.txt` 和 `expected_behavior.md` 用来描述预期修改文件和预期行为。
- 评测器会去 `evals/fixtures/<repo_ref>/repo/` 复制初始仓库，再按这些任务文件运行。

当前这套 demo 里有 4 个真实任务：

- `python-cli-001`
  - 问题：`--name` 传空字符串时，CLI 只返回不清晰的问候语。
  - 期望：空名字要报验证错误，合法名字保持原行为。
- `python-cli-002`
  - 问题：`normalize_slug("Hello  World!")` 仍然保留重复分隔符。
  - 期望：折叠重复分隔符，并去掉首尾分隔符。
- `docs-001`
  - 问题：README 没有写 maintainer 工作流的运行命令。
  - 期望：补一个 `mini-agent maintain` 示例，并说明产物写到哪里。
- `failure-001`
  - 问题：这是一个故意失败的任务，用来展示评测报告如何解释失败。
  - 期望：验证命令退出码为 1，报告里能看到失败摘要和失败分类。

## 4. 一次失败反思

选 `failure-001`：

- 说明 verification 命令故意失败。
- 强调报告里会保留 `failure_category` 和 `failure_summary`。
- 如果启用了 implementer 和 verifier，可以展示失败后进入 reflection，再决定是否重试。

## 5. 结尾

收束成一句：

“这个项目的重点不是生成一段代码，而是把 issue、补丁、验证、失败反思和交付物串成一个可审计的工程闭环。”

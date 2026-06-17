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

## 5. 最近一次失败复盘

最新一轮 LLM eval 曾出现 4 个 case 只有 1 个通过。复盘后发现，失败并不都是模型“不会修”，而是暴露了 maintainer workflow 当前的几个系统性薄弱点。

### 失败原因简记

- `docs-001`
  - 现象：README 修复任务第一次失败。
  - 原因：模型生成的 unified diff 使用了裸 `@@` hunk header，没有 `@@ -old,count +new,count @@` 行号，patch 被本地校验拒绝。
  - 修复：在 `apply_unified_diff` 前增加裸 hunk 规范化。能根据当前文件内容定位旧行时，自动补齐合法 hunk header。

- `python-cli-001`
  - 现象：模型已经生成了正确的 `ValueError` 校验逻辑，但测试仍失败。
  - 原因：模型 patch 混入了 `*** End of File ***` 这类非 unified diff 标记，导致 hunk 定位失败，补丁没有应用。
  - 修复：提取模型 diff 时清理非 diff sentinel；同时补测试覆盖这类模型输出。

- `python-cli-002`
  - 现象：slug 修复多次失败，第一次失败是 patch apply 问题，后续失败是模型只处理空白字符，没有处理 `!` 等标点。
  - 原因一：模型返回过缺少 `---/+++` 文件头的 `diff --git + @@` 片段，`git apply` 会报 patch fragment without header。
  - 原因二：`context_select` 在 LLM 输出解析失败后回退到规则选择，但只选中了 `tests/test_slug.py`，覆盖掉 triage 已经识别出的 `src/slug.py`。
  - 原因三：只把实现文件放进上下文时，模型没有稳定看到测试断言 `normalize_slug("Hello  World!") == "hello-world"`，容易把 separator 理解成 whitespace。
  - 修复：缺失文件头时根据 `diff --git a/x b/x` 补 `---/+++`；context 选择改为合并 triage 文件、context 文件和测试文件，避免丢掉实现文件或断言。

- `failure-001`
  - 现象：报告中仍显示 fail。
  - 原因：这是故意失败 fixture，验证命令固定为 `python -c 'import sys; sys.exit(1)'`，目标是展示失败分类和摘要，不应按“修复成功”任务理解。
  - 后续：eval report 可以增加 expected-failure / xfail 语义，把“预期失败路径验证成功”和“修复任务失败”区分开。

### 归纳出的当前问题

- 模型输出格式不稳定：即使 prompt 要求 unified diff，仍可能出现裸 `@@`、缺文件头、`*** End of File ***` 或额外文本。
- 上下文选择过脆弱：单个 planner/context 节点失败时，fallback 可能只选测试或只选实现，导致 implementer 缺关键信息。
- LLM 调用链路过长：triage、context、plan、implement、reflect、PR writer 多次串行调用，耗时主要花在模型路由和重试，而不是测试。
- eval 指标语义还不够细：故意失败 case 被计入普通 fail，会拉低 resolved rate，也容易误导 demo 解读。
- 失败重试仍偏被动：patch apply 失败和测试失败都进入同一 retry 链路，但对“格式错误可自动修复”和“实现逻辑错误需补上下文”的区分还不够明确。

### 进一步优化方向

- 增加 `expected_failure` / `xfail` 任务类型，让 `failure-001` 这类任务独立计入 failure-path coverage。
- 对模型 diff 做更完整的 normalize：清理非 diff 标记、补 hunk header、补文件头，并把每次 normalize 写入 trace。
- context selection 使用保守合并策略：triage suspected files、LLM selected files、规则 selected files、相关 test files 取并集，按上限裁剪。
- 对简单 fixture 增加 fast path：明确 `expected_files` 时直接把这些文件和对应测试放进上下文，减少 planner 失败面。
- eval 默认关闭 LLM PR writer，或不把 PR writer 计入 resolved latency；PR 文案可在通过后异步生成。
- 在 report 中拆分 LLM 耗时、测试耗时、patch normalize 耗时、API retry 次数，便于判断瓶颈是模型、网络还是本地工具。

## 6. 结尾

收束成一句：

“这个项目的重点不是生成一段代码，而是把 issue、补丁、验证、失败反思和交付物串成一个可审计的工程闭环。”

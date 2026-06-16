# OSS Maintainer Agent 开发文档

本文档定义一个适合面试展示的真实 Agent 项目：基于当前 Mini-Agent 改造成面向开源仓库维护的 `Issue-to-Patch` / `Issue-to-PR` Agent。目标不是做一个泛泛的聊天机器人，而是完成真实软件工程闭环：理解 issue、定位代码、修改、运行验证、生成 patch 和 PR 说明，并保留完整执行轨迹。

<style>
  .maintainer-sidebar {
    position: fixed;
    top: 24px;
    left: 24px;
    width: 260px;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
    padding: 14px 16px;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    background: #ffffff;
    box-shadow: 0 8px 24px rgba(140, 149, 159, 0.2);
    font-size: 13px;
    line-height: 1.45;
    z-index: 20;
  }

  .maintainer-sidebar strong {
    display: block;
    margin-bottom: 8px;
    color: #24292f;
    font-size: 14px;
  }

  .maintainer-sidebar a {
    display: block;
    color: #0969da;
    text-decoration: none;
    padding: 3px 0;
  }

  .maintainer-sidebar a:hover {
    text-decoration: underline;
  }

  .maintainer-sidebar .sub {
    padding-left: 14px;
    color: #57606a;
  }

  .maintainer-sidebar .sub2 {
    padding-left: 28px;
    color: #6e7781;
    font-size: 12px;
  }

  @media (min-width: 1100px) {
    body {
      padding-left: 310px;
    }
  }

  @media (max-width: 1099px) {
    .maintainer-sidebar {
      position: static;
      width: auto;
      max-height: none;
      margin: 16px 0 24px;
    }
  }
</style>

<nav class="maintainer-sidebar">
  <strong>导航目录</strong>
  <a href="#1-项目定位">1. 项目定位</a>
  <a href="#2-当前代码是否适合作为底座">2. 当前代码是否适合作为底座</a>
  <a href="#3-技术选型">3. 技术选型</a>
  <a class="sub" href="#31-agent-底座">3.1 Agent 底座</a>
  <a class="sub" href="#32-编排">3.2 编排</a>
  <a class="sub" href="#33-模型接口">3.3 模型接口</a>
  <a class="sub" href="#34-执行环境">3.4 执行环境</a>
  <a href="#4-核心用户流程">4. 核心用户流程</a>
  <a href="#5-langgraph-工作流设计">5. LangGraph 工作流设计</a>
  <a class="sub" href="#51-state-结构">5.1 State 结构</a>
  <a class="sub" href="#52-节点划分">5.2 节点划分</a>
  <a class="sub" href="#53-路由">5.3 路由</a>
  <a href="#6-模块规划">6. 模块规划</a>
  <a href="#7-工具规划">7. 工具规划</a>
  <a class="sub" href="#71-复用现有工具">7.1 复用现有工具</a>
  <a class="sub" href="#72-新增-git-工具">7.2 新增 Git 工具</a>
  <a class="sub" href="#73-新增-repo-工具">7.3 新增 Repo 工具</a>
  <a href="#8-openrouter-配置">8. OpenRouter 配置</a>
  <a href="#9-sandbox-策略">9. Sandbox 策略</a>
  <a href="#10-artifacts-设计">10. Artifacts 设计</a>
  <a href="#11-评测集设计">11. 评测集设计</a>
  <a href="#12-mvp-里程碑">12. MVP 里程碑</a>
  <a class="sub" href="#m0确认底座">M0 确认底座</a>
  <a class="sub" href="#m1本地-repo-maintainer-runner">M1 本地 runner</a>
  <a class="sub" href="#m2实现补丁闭环">M2 补丁闭环</a>
  <a class="sub" href="#m3失败反思和重试">M3 失败重试</a>
  <a class="sub" href="#m4评测和面试展示">M4 评测展示</a>
  <a href="#13-面试叙事">13. 面试叙事</a>
  <a href="#14-风险和取舍">14. 风险和取舍</a>
  <a href="#15-首批开发任务清单">15. 首批开发任务清单</a>
  <a href="#16-参考资料">16. 参考资料</a>
</nav>

## 1. 项目定位

项目名称建议：`RepoPilot`、`PatchPilot` 或 `OSS Maintainer Agent`。

一句话介绍：

> 一个本地运行的开源仓库维护 Agent。用户输入 GitHub issue、任务描述或 failing test，Agent 在本地 sandbox 中分析仓库、生成修复计划、修改代码、运行测试，并输出 patch、验证报告和 PR 描述。

适合面试讲述的重点：

- 真实工程任务，而不是问答 demo。
- 有工具调用闭环：read/search/edit/bash/git/test。
- 有 LangGraph 编排：规划、检索、实现、验证、反思、报告。
- 有本地 sandbox：不依赖企业数据，不触碰生产环境。
- 有可观测性：保留每一步决策、工具调用、测试结果和最终 diff。

## 2. 当前代码是否适合作为底座

结论：当前 Mini-Agent 可以作为底座，并且已经具备几个关键条件。

已有能力：

- `mini_agent/agent.py`：完整单 Agent 执行循环，支持多轮工具调用、上下文压缩、取消清理。
- `mini_agent/llm/openai_client.py`：OpenAI-compatible 客户端，可接 OpenRouter。
- `mini_agent/tools/file_tools.py`：`read_file`、`write_file`、`edit_file`。
- `mini_agent/tools/bash_tool.py`：本地 shell 执行和后台进程管理。
- `mini_agent/event_trace.py`：已有 LangGraph 风格 workflow，证明项目已经引入图式编排依赖和节点设计经验。
- `mini_agent/event_trace_runner.py`：已有 workflow runner 和状态落盘思路。
- `mini_agent/config.py`：配置支持 `.env`、环境变量展开、OpenRouter role-specific models、AnySearch 等。
- `INTERVIEW_PREP_CN.md`：已有面试叙事基础。

需要新增的能力：

- 仓库任务的结构化输入：repo 路径、issue 文本、测试命令、约束。
- Git 工具封装：status、diff、apply patch、生成 patch、回滚本次改动。
- Repo 索引：快速获取文件树、语言、测试框架、关键文件。
- LangGraph 编排：把单 agent loop 包进可控节点，而不是让模型自由长跑。
- 验证闭环：测试失败时分类、摘要日志、决定是否重试。
- 评测集：10 到 30 个小型真实任务，能统计成功率和失败原因。

## 3. 技术选型

### 3.1 Agent 底座

继续使用当前 Mini-Agent：

- 保留 `Agent` 作为低层执行器。
- 保留现有 tool 抽象。
- 新增面向仓库维护的 tools 和 graph runner。

不要一开始重写整个 runtime。现阶段最有价值的是做一个清晰的 coding-agent workflow，而不是造第二套通用 agent 框架。

### 3.2 编排

使用 LangGraph。

LangGraph 适合把长任务拆成显式状态机：节点负责局部动作，边负责下一步路由。当前项目已经有 `EventTraceAgent._build_langgraph()`，可以参考它的写法。官方文档已迁移到 `docs.langchain.com`，旧入口会跳转到新站点。

### 3.3 模型接口

使用 OpenRouter 的 OpenAI-compatible API。

配置建议：

```yaml
api_key: "${OPENROUTER_API_KEY}"
api_base: "https://openrouter.ai/api/v1"
provider: "openai"
model: "openai/gpt-oss-20b:free"
```

OpenRouter 官方 Quickstart 说明它提供统一 API，可通过标准 `/api/v1/chat/completions` 访问多模型，并可用 OpenAI SDK 指向 OpenRouter base URL。

### 3.4 执行环境

MVP 使用本地 sandbox：

- 工作目录限制在 `workspace_dir`。
- 所有 shell 命令默认在 repo workspace 内执行。
- 第一阶段不自动 push、不自动创建真实 PR。
- 输出 patch 和 PR 文案，由用户手动确认。

后续可选增强：

- 用 `git worktree` 为每个任务创建隔离目录。
- 用 Docker 或 `uv` 临时环境运行测试。
- 对危险命令做确认或 denylist。

## 4. 核心用户流程

```text
用户输入：
  repo_path: /path/to/repo
  issue: "xxx 功能失败，期望行为是 ..."
  test_command: "pytest tests/test_x.py"

Agent 输出：
  artifacts/runs/<run_id>/
    plan.md
    repo_map.md
    tool_trace.jsonl
    test_results.md
    final.patch
    pr_description.md
    run_summary.md
```

MVP 命令建议：

```bash
mini-agent maintain \
  --repo /path/to/project \
  --issue-file examples/issues/demo_issue.md \
  --test "pytest tests/test_demo.py"
```

也保留普通交互入口：

```bash
mini-agent --workspace /path/to/project
```

## 5. LangGraph 工作流设计

### 5.1 State 结构

新增文件建议：`mini_agent/maintainer/state.py`

```python
class MaintainerState(TypedDict, total=False):
    run_id: str
    repo_path: str
    issue_text: str
    constraints: list[str]
    test_command: str | None

    repo_map: dict
    suspected_files: list[str]
    plan: str
    implementation_notes: list[str]

    changed_files: list[str]
    diff: str
    test_results: list[dict]
    verification_status: str
    failure_summary: str
    retry_count: int

    pr_description: str
    artifacts_dir: str
    final_report: str
```

### 5.2 节点划分

推荐节点：

1. `bootstrap_run`
   - 创建 `run_id` 和 artifacts 目录。
   - 检查 repo 是否存在、是否是 git repo、工作区是否干净。

2. `repo_scan`
   - 运行 `git status --short`、`find`、`rg --files`。
   - 识别语言、包管理器、测试框架、README、配置文件。
   - 输出 `repo_map.md`。

3. `issue_triage`
   - 从 issue 中提取 bug 类型、期望行为、可能模块、验收标准。
   - 输出结构化 triage。

4. `context_select`
   - 用 `rg`、文件树和模型判断选择相关文件。
   - 限制上下文规模，避免把整个仓库塞给模型。

5. `plan_patch`
   - 生成修改计划。
   - 计划必须包含：文件、改动点、测试策略、风险。

6. `implement_patch`
   - 调用 Mini-Agent 低层执行器或直接用 tools 修改文件。
   - 只允许改计划中列出的文件，除非模型给出追加理由。

7. `run_verification`
   - 运行用户指定测试命令。
   - 如果未指定，则根据 repo_map 选择最小测试命令。
   - 记录 stdout、stderr、exit code、耗时。

8. `reflect_failure`
   - 测试失败时分析日志。
   - 使用 `verifier_model` 结合失败摘要、当前 diff 和计划，判断失败原因。
   - 判断是否继续重试、缩小问题、或终止。
   - 输出下一轮修复建议，供 `implement_patch` 使用。

9. `package_artifacts`
   - 生成 `git diff`、`final.patch`、`pr_description.md`、`run_summary.md`。

### 5.3 路由

```text
bootstrap_run -> repo_scan -> issue_triage -> context_select -> plan_patch
plan_patch -> implement_patch -> run_verification
run_verification -- pass --> package_artifacts
run_verification -- fail and retry_count < max_retry --> reflect_failure -> implement_patch
run_verification -- fail and retry exhausted --> package_artifacts
```

## 6. 模块规划

建议新增目录：

```text
mini_agent/
  maintainer/
    __init__.py
    state.py
    graph.py
    runner.py
    prompts.py
    artifacts.py
    repo_inspector.py
    verifier.py
    patch_packager.py
    evals.py
```

模块职责：

- `state.py`：TypedDict 和 pydantic payload。
- `graph.py`：LangGraph 节点和路由。
- `runner.py`：命令行入口调用的同步/异步 runner。
- `prompts.py`：planner、triage、reflector、PR writer 的 prompt。
- `artifacts.py`：统一写入 artifacts，避免各节点随意写文件。
- `repo_inspector.py`：文件树、语言识别、测试命令推断。
- `verifier.py`：测试执行、日志截断、失败分类。
- `patch_packager.py`：`git diff`、patch、PR 文案。
- `evals.py`：评测任务加载和批量运行。

## 7. 工具规划

### 7.1 复用现有工具

- `ReadTool`
- `WriteTool`
- `EditTool`
- `BashTool`
- `WebSearchTool` 可选
- `SessionNoteTool` 可选
- Skills 可选，用于加载特定语言或框架规则

### 7.2 新增 Git 工具

新增文件建议：`mini_agent/tools/git_tools.py`

工具列表：

- `git_status`
- `git_diff`
- `git_apply_patch`
- `git_create_patch`
- `git_restore_run_changes`

MVP 可以先不暴露给模型，而是在 LangGraph 节点里直接调用 Python subprocess。这样更可控。

### 7.3 新增 Repo 工具

新增文件建议：`mini_agent/tools/repo_tools.py`

工具列表：

- `repo_tree`
- `repo_grep`
- `repo_file_summary`
- `repo_detect_test_command`

这些工具的价值是减少模型自由执行 shell 的比例，让 workflow 更稳定。

## 8. OpenRouter 配置

推荐开发配置：

```yaml
api_key: "${OPENROUTER_API_KEY}"
api_base: "https://openrouter.ai/api/v1"
provider: "openai"
model: "openai/gpt-oss-20b:free"  # 可按任务替换为其它 OpenRouter 可用模型。
max_steps: 80
workspace_dir: "./workspace"
```

`model` 不是固定值。OpenRouter 上可用模型会变化，开发时可以根据上下文长度、工具调用稳定性、代码能力和限速情况切换。当前可选模型示例：

```text
nex-agi/nex-n2-pro:free
nvidia/nemotron-3-ultra-550b-a55b:free
openrouter/owl-alpha
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
poolside/laguna-xs.2:free
poolside/laguna-m.1:free
google/gemma-4-26b-a4b-it:free
google/gemma-4-31b-it:free
nvidia/nemotron-3-super-120b-a12b:free
openrouter/free
nvidia/nemotron-3-nano-30b-a3b:free
nvidia/nemotron-nano-12b-v2-vl:free
qwen/qwen3-next-80b-a3b-instruct:free
nvidia/nemotron-nano-9b-v2:free
openai/gpt-oss-120b:free
openai/gpt-oss-20b:free
qwen/qwen3-coder:free
meta-llama/llama-3.3-70b-instruct:free
```

实践建议：

- 代码修改节点优先试 `qwen/qwen3-coder:free`、`openai/gpt-oss-120b:free` 或 `openai/gpt-oss-20b:free`。
- 规划、总结、PR 文案节点可以用更便宜或更快的通用模型。
- 如果某个免费模型工具调用格式不稳定，优先换模型，而不是在 prompt 里堆太多格式约束。

如果要给不同节点配置不同模型，可以复用当前 `event_trace_models` 的设计，新增：

```yaml
tools:
  maintainer_models:
    api_key: "${OPENROUTER_API_KEY}"
    api_base: "https://openrouter.ai/api/v1"
    provider: "openai"
    planner_model: "openai/gpt-oss-20b:free"
    implementer_model: "qwen/qwen3-coder:free"
    verifier_model: "openai/gpt-oss-20b:free"
    pr_writer_model: "openai/gpt-oss-20b:free"
```

模型分工建议：

- `planner_model`：负责 issue triage、上下文选择和修复计划。
- `implementer_model`：负责实际代码修改，优先选择代码能力更强的模型。
- `verifier_model`：负责理解测试输出、生成失败摘要和失败反思；输入 `test_results`、`diff`、`retry_count`，输出下一轮修复方向或终止原因，不负责运行测试。
- `pr_writer_model`：负责生成 PR 描述和最终报告。

注意事项：

- 免费模型可能限速、上下文较小或工具调用不稳定。
- 需要把测试日志和文件内容做截断。
- 对关键输出使用 pydantic 校验，避免模型返回散文导致节点失败。

## 9. Sandbox 策略

MVP 安全边界：

- `repo_path` 必须存在，且所有操作限制在该目录下。
- 拒绝执行包含明显危险模式的命令：
  - `rm -rf /`
  - `sudo`
  - `chmod -R 777`
  - `curl ... | sh`
  - 向远端 push
- 默认不执行网络安装命令，除非用户显式允许。
- 修改前记录 `git status --short`。
- 结束时输出本轮改动文件列表。

推荐实现：

- 在 `BashTool` 外层增加 `SandboxCommandRunner`。
- 命令执行前做 cwd 校验和 denylist。
- 所有命令写入 `tool_trace.jsonl`。
- 对长输出做 token/字符截断，完整日志落盘。

## 10. Artifacts 设计

每次运行创建：

```text
artifacts/runs/20260615-113000-demo/
  input.json            # 本次运行的原始输入，包括 repo、issue、测试命令、约束等。
  plan.md               # 修复计划：目标文件、改动点、测试策略和主要风险。
  repo_map.md           # 仓库扫描结果：语言、包管理器、测试框架、关键目录和配置文件。
  selected_context.md   # 被选入模型上下文的文件片段、搜索结果和选择理由。
  tool_trace.jsonl      # 工具调用轨迹；每行一条 JSON，记录命令/工具名、参数、结果、耗时和错误。
  test_results.md       # 验证结果摘要：执行的测试命令、退出码、失败日志摘要和失败分类。
  final.diff            # 最终 `git diff` 输出，便于直接查看本次改动。
  final.patch           # 可应用的补丁文件，用于复现改动或提交 PR。
  pr_description.md     # PR 描述草稿，包括问题背景、修复说明、验证方式和风险。
  run_summary.md        # 本次运行总报告：最终状态、改动文件、重试次数、测试结论和后续建议。
  state.json            # 结构化状态快照，保存 LangGraph 各节点的关键字段，便于调试和评测。
```

`run_summary.md` 模板：

```md
# Run Summary

## Task
...

## Result
- status: pass | fail | partial
- changed_files:
...

## Verification
...

## Risk
...

## Next Steps
...
```

## 11. 评测集设计

不要一开始跑 SWE-bench。先做本地小评测集。

目录建议：

```text
evals/
  tasks/
    python-cli-001/
      repo_ref.txt
      issue.md
      test_command.txt
      expected_files.txt
    js-utils-001/
      issue.md
      test_command.txt
```

每个任务记录：

- 任务描述
- 初始 repo 或 fixture
- 期望测试命令
- 是否允许新增依赖
- 成功标准

指标：

- `resolved_rate`：测试通过且 diff 合理。
- `test_pass_rate`：测试命令 exit code 为 0。
- `avg_iterations`：平均修复轮数。
- `avg_tokens`：平均 token 使用。
- `failure_categories`：定位失败、修改错误、测试环境失败、模型格式错误、超限。

面试展示时不要只说成功案例。至少准备 1 个失败案例，说明你如何分类和改进。

## 12. MVP 里程碑

### M0：确认底座

- `uv sync` 成功。
- `mini-agent` 能用 OpenRouter 跑一次普通问答。
- 文件工具和 bash 工具能在 workspace 内执行。

验收：

```bash
uv run python -m mini_agent.cli --task "读取 README.md 并总结项目"
```

### M1：本地 repo maintainer runner

- 新增 `maintain` 子命令。
- 支持 `--repo`、`--issue-file`、`--test`。
- 能生成 repo map、plan、最终 summary。

验收：

```bash
mini-agent maintain --repo /tmp/demo-repo --issue-file issue.md --test "pytest"
```

### M2：实现补丁闭环

- Agent 能改文件。
- 运行测试。
- 生成 `final.patch` 和 `pr_description.md`。

验收：

- 至少 3 个 demo 任务跑通。
- 每个任务都有 artifacts。

### M3：失败反思和重试

- 测试失败后进入 `reflect_failure`。
- 最多重试 2 次。
- 失败也生成可解释报告。

验收：

- 能展示一次第一次失败、第二次修复成功的轨迹。

### M4：评测和面试展示

- 准备 10 个小任务。
- 输出 `eval_report.md`。
- 准备 3 分钟 demo 脚本。

验收：

- README 中有架构图、demo gif 或录屏链接、评测表。

## 13. 面试叙事

推荐表述：

> 我基于 Mini-Agent 做了一个开源仓库维护 Agent。底层复用了 Mini-Agent 的工具调用 runtime 和 OpenAI-compatible 模型适配，模型走 OpenRouter；上层没有让模型自由长跑，而是用 LangGraph 把任务拆成 repo scan、issue triage、context select、patch plan、implementation、verification、reflection、artifact packaging 这些节点。每次运行都会生成 patch、测试报告、PR 描述和完整轨迹，因此可以评测和复盘。

可以重点展开：

- 为什么不用企业数据：选择开源 repo 和本地 fixture，任务真实且可复现。
- 为什么用 LangGraph：把长任务变成可控状态机，便于失败重试和评测。
- 为什么保留 Mini-Agent：底层 agent loop、tools、OpenRouter 适配已经够轻，适合快速改造。
- 为什么本地 sandbox：面试项目不需要云端复杂度，但必须有安全边界。
- 如何评测：小任务集、测试通过率、失败分类、轨迹分析。

不要这样说：

- “我做了一个通用自主 Agent。”
- “它可以自动修任何 bug。”
- “免费模型效果和商业最强模型一样。”

更稳妥的说法：

- “我把目标收敛在开源仓库维护任务。”
- “MVP 重点验证工具闭环和测试反馈闭环。”
- “模型能力不足时，我用结构化节点、上下文选择和验证重试降低失败率。”

## 14. 风险和取舍

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| 免费模型工具调用不稳定 | 修复质量波动 | 节点输出用 pydantic 校验，失败重试 |
| 测试命令耗时或缺依赖 | demo 卡住 | MVP 使用小 repo 和预装依赖 |
| 上下文过大 | 模型漏读关键文件 | repo_scan + context_select 限制文件 |
| shell 命令危险 | 误删文件 | sandbox runner + denylist + git diff |
| 自动修改过多文件 | PR 风险高 | plan_patch 限制改动范围 |

## 15. 首批开发任务清单

优先级从上到下：

- [x] 新增 `mini_agent/maintainer/` 包。
- [x] 定义 `MaintainerState`。
- [x] 新增 artifacts 写入工具。
- [x] 新增 repo scan 节点。
- [x] 新增 issue triage prompt 和 pydantic 输出。
- [x] 新增 context select 节点。
- [x] 新增 maintain CLI 子命令。
- [x] 接入 OpenRouter 默认配置示例。
- [x] 新增 verification 节点和测试日志摘要。
- [x] 生成 `final.patch`、`pr_description.md`、`run_summary.md`。
- [x] 加 3 个最小 fixture 任务。
- [ ] 写面试 demo 脚本。

当前 MVP 已经能完成 deterministic runner、LangGraph/fallback workflow、artifacts、`maintain` CLI、`maintain-eval` CLI 和基础 eval report。下一阶段重点不再是补目录结构，而是把“规则版节点”升级成“模型驱动但可控的补丁闭环”。

## 16. 第二批开发任务清单：模型补丁闭环

目标：让 Agent 从“生成计划和报告”升级为“能自动修改代码、运行测试、失败后反思并重试”。

### P0：LLM 节点接入

- [x] 新增 `mini_agent/maintainer/llm_roles.py`，复用 `tools.maintainer_models` 创建 planner、implementer、verifier、pr_writer client。
- [x] 在 `issue_triage` 中增加 LLM 模式，输出 `IssueTriagePayload`，失败时回退规则版 triage。
- [x] 在 `context_select` 中增加 LLM 模式，输出 `ContextSelectionPayload`，并校验文件必须存在于 repo。
- [x] 在 `plan_patch` 中增加 LLM 模式，输出 `PatchPlanPayload`，并写入结构化 `plan.json`。
- [partial] 增加 CLI 开关：
  - [x] `--llm-plan`
  - [x] `--llm-implement`
  - [x] `--llm-reflect`
  - [x] `--llm-pr`
  - [ ] `--model-profile openrouter-free|local|custom`

### P0：实现 `implement_patch`

- [x] 新增 `mini_agent/maintainer/implementer.py`。
- [x] 给 implementer 输入：issue、triage、selected_context、plan、当前 diff、失败反思。
- [x] implementer 第一版只允许返回 unified diff，不直接写文件。
- [x] 使用 `git apply --check` 校验 patch。
- [x] 使用 `git apply` 应用 patch。
- [x] patch 失败时把错误写入 `tool_trace.jsonl` 和 `implementation_notes`。
- [x] 限制 patch 修改文件必须属于计划文件。
- [ ] 支持模型为计划外文件提供新增理由并通过校验。
- [ ] 对新增文件、删除文件、二进制文件分别做策略限制。

### P0：失败反思和重试

- [x] 在 `reflect_failure` 中接入 verifier_model。
- [x] 输出 `FailureReflectionPayload`。
- [x] 将失败分类为：
  - `test_failed`
  - `test_timeout`
  - `dependency_missing`
  - `patch_apply_failed`
  - `context_missing`
  - `model_format_error`
- [x] 根据分类决定是否重试。
- [x] 重试时把失败摘要和当前 diff 注入 implementer。
- [x] 默认 `max_retries=2`，CLI 可覆盖。

### P1：PR 文案和最终报告升级

- [x] 在 `package_artifacts` 中接入 pr_writer_model。
- [x] 生成 `pr_description.md` 时包含：
  - 问题背景
  - 关键改动
  - 验证方式
  - 风险和回滚建议
- [x] 生成 `run_summary.md` 时包含节点耗时、测试耗时、模型调用次数。
- [x] 输出 `state.json` 时过滤过长日志，只保留摘要和 artifact 路径。

### P1：可观测性和 token 统计

- [ ] 在 `tool_trace.jsonl` 中记录每个节点：
  - node name
  - started_at / ended_at
  - duration_ms
  - input summary
  - output summary
  - error
- [x] 记录 LLM request/response 的 token usage。
- [x] 在 eval report 中增加：
  - `avg_tokens`
  - `avg_duration_seconds`
  - `patch_apply_success_rate`
  - `retry_success_rate`

## 17. 第三批开发任务清单：安全、评测和展示

目标：让项目适合面试展示和持续迭代，不只是单次 demo。

### P0：Sandbox 和 Git 安全边界

- [ ] 新增 `mini_agent/maintainer/sandbox.py`。
- [ ] 所有命令必须在 repo 根目录内运行。
- [ ] 拒绝危险命令：
  - `rm -rf /`
  - `sudo`
  - `chmod -R 777`
  - `curl ... | sh`
  - `wget ... | sh`
  - `git push`
  - 修改 `.git/` 内部文件
- [ ] verification command 默认禁止网络安装命令。
- [ ] 支持 `--allow-network-install` 显式打开安装类命令。
- [ ] 每次运行开始记录 baseline `git status --short`。
- [ ] 每次运行结束输出本次新增/修改/删除文件。
- [ ] 新增 `--restore-on-failure`，失败后自动回滚本轮改动。

### P0：真实 eval fixture

- [x] 新增 `evals/fixtures/`，放 3 个小型可复制 repo。
- [x] 每个 fixture 都要有：
  - 初始代码
  - failing test
  - issue.md
  - test_command.txt
  - expected_files.txt
  - expected_behavior.md
- [x] 将当前 `evals/tasks/*` 从“任务描述”升级为可实际运行的 fixture 或 repo_ref。
- [x] 新增 `maintain-eval --fixture-root`，自动复制 fixture 到临时目录再运行。
- [x] eval 结束后保留每个任务的 run artifacts。
- [x] 准备至少 1 个失败案例，报告中能解释失败原因。

### P1：Demo 和文档

- [x] 新增 `docs/OSS_MAINTAINER_DEMO_CN.md`。
- [x] 写 3 分钟面试 demo 脚本：
  - 项目目标
  - workflow 图
  - 一次成功修复
  - 一次失败反思
  - eval report
- [x] README 增加 `maintain` 和 `maintain-eval` 使用示例。
- [x] README 增加 artifacts 示例目录。
- [ ] 增加一张架构图或 Mermaid 图。
- [ ] 录制 demo gif 或 asciinema。

### P1：工程质量

- [partial] 给 maintainer workflow 增加单元测试：
  - [x] repo scan
  - [x] triage payload fallback
  - [x] context selection
  - [x] patch apply success/failure
  - [x] verification timeout
  - [x] reflect retry route
- [x] 给 CLI 增加解析测试。
- [x] 给 eval report 增加 snapshot 测试。
- [x] 为 `maintain` / `maintain-eval` 增加终端进度日志：
  - 当前 task_id / repo_ref
  - 当前 workflow 节点
  - verification 命令开始/结束
  - 失败时的摘要
- [x] 增加简洁的大模型决策摘要：
  - triage / context / plan / implement / reflect / pr
- [ ] CI 中跳过需要真实 API key 的 LLM 集成测试。
- [ ] 将需要真实模型的测试标记为 `@pytest.mark.integration`。

## 18. 参考资料

- Mini-Agent 当前仓库：本项目 README 和 `INTERVIEW_PREP_CN.md`。
- OpenRouter Quickstart：https://openrouter.ai/docs/quickstart
- LangGraph 文档入口：https://docs.langchain.com/langgraph/
- OpenHands：https://github.com/OpenHands/OpenHands
- SWE-bench：https://www.swebench.com/

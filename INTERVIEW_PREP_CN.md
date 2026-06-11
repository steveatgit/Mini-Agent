# Mini Agent 面试准备笔记

<style>
  .interview-sidebar {
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

  .interview-sidebar strong {
    display: block;
    margin-bottom: 8px;
    color: #24292f;
    font-size: 14px;
  }

  .interview-sidebar a {
    display: block;
    color: #0969da;
    text-decoration: none;
    padding: 3px 0;
  }

  .interview-sidebar a:hover {
    text-decoration: underline;
  }

  .interview-sidebar .sub {
    padding-left: 14px;
    color: #57606a;
  }

  .interview-sidebar .sub2 {
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
    .interview-sidebar {
      position: static;
      width: auto;
      max-height: none;
      margin: 16px 0 24px;
    }
  }
</style>

<nav class="interview-sidebar">
  <strong>导航目录</strong>
  <a href="#1-项目定位">1. 项目定位</a>
  <a href="#2-整体架构">2. 整体架构</a>
  <a href="#3-核心执行链路">3. 核心执行链路</a>
  <a href="#31-runtime-和-harness-的理解">3.1 Runtime 和 Harness</a>
  <a href="#4-项目亮点">4. 项目亮点</a>
  <a class="sub" href="#41-统一-llm-协议适配">4.1 LLM 协议适配</a>
  <a class="sub" href="#42-支持-thinkingreasoning-的多轮保留">4.2 Thinking 保留</a>
  <a class="sub" href="#43-工具系统可扩展">4.3 工具系统</a>
  <a class="sub" href="#44-真实工程任务支持">4.4 工程任务支持</a>
  <a class="sub" href="#45-长上下文压缩">4.5 长上下文压缩</a>
  <a class="sub" href="#46-mcp-扩展">4.6 MCP 扩展</a>
  <a class="sub" href="#47-claude-skills-渐进式加载">4.7 Skills 加载</a>
  <a class="sub" href="#48-可观测性和稳定性">4.8 可观测性</a>
  <a href="#5-面试-demo-建议">5. 面试 Demo</a>
  <a class="sub" href="#demo-1基础工具调用">Demo 1 基础工具调用</a>
  <a class="sub" href="#demo-2长任务执行">Demo 2 长任务执行</a>
  <a class="sub" href="#demo-3mcp-或-skill">Demo 3 MCP / Skill</a>
  <a href="#6-如何真正变成自己的项目">6. 变成自己的项目</a>
  <a class="sub" href="#61-加一个自己的工具">6.1 自定义工具</a>
  <a class="sub2" href="#611-自定义工具开发通用步骤">6.1.1 工具开发步骤</a>
  <a class="sub2" href="#612-方案一实现-web_search-工具">6.1.2 web_search 工具</a>
  <a class="sub2" href="#613-方案二实现-jira_reader-工具">6.1.3 jira_reader 工具</a>
  <a class="sub2" href="#614-两个工具的组合-demo">6.1.4 组合 Demo</a>
  <a class="sub" href="#62-改进记忆系统">6.2 记忆系统</a>
  <a class="sub2" href="#621-当前记忆系统的边界">6.2.1 当前边界</a>
  <a class="sub2" href="#622-方案一按-workspace-隔离记忆">6.2.2 Workspace 隔离</a>
  <a class="sub2" href="#623-方案二接向量库做语义检索">6.2.3 语义检索</a>
  <a class="sub2" href="#624-组合改造后的记忆架构">6.2.4 记忆架构</a>
  <a class="sub" href="#63-增强安全边界">6.3 安全边界</a>
  <a class="sub2" href="#631-危险命令确认的实现思路">6.3.1 危险命令确认</a>
  <a class="sub" href="#64-增加真实业务场景">6.4 业务场景</a>
  <a class="sub2" href="#641-事件脉络-agent-的核心链路">6.4.1 事件脉络 Agent</a>
  <a class="sub2" href="#642-为什么用-langgraph">6.4.2 LangGraph</a>
  <a class="sub2" href="#643-langgraph-节点设计">6.4.3 节点设计</a>
  <a class="sub2" href="#644-负责任务规划器设计">6.4.4 任务规划器</a>
  <a class="sub2" href="#645-工具层设计">6.4.5 工具层</a>
  <a class="sub2" href="#646-memory-系统设计">6.4.6 Memory 系统</a>
  <a class="sub2" href="#647-能力分层和当前缺口">6.4.7 能力分层</a>
  <a class="sub2" href="#648-评测系统设计">6.4.8 评测系统</a>
  <a href="#7-可能被追问的问题">7. 可能被追问</a>
  <a href="#8-推荐面试叙事">8. 推荐面试叙事</a>
  <a href="#9-简历写法">9. 简历写法</a>
  <a href="#10-面试时不要这样说">10. 不要这样说</a>
</nav>

## 1. 项目定位

这个项目可以定位为：一个面向复杂任务执行的轻量级 Agent Runtime，而不是简单聊天机器人。

更稳妥的面试表述：

> 我复现并改造了一个 Mini Agent 框架，重点实现了工具调用闭环、长上下文管理、多 Provider 适配、Skills/MCP 扩展和 CLI/ACP 交互能力。

一句话介绍：

> 我做的是一个轻量级 Agent Runtime，支持 Anthropic/OpenAI 协议兼容模型，通过统一的工具抽象完成文件、Shell、记忆、MCP、Skills 等能力接入，并加入了长上下文压缩、执行日志、重试和 CLI/ACP 集成，目标是让 Agent 能稳定处理真实工程任务。

## 2. 整体架构

```text
CLI / ACP Client
      |
      v
Agent Runtime
  - 多轮执行循环
  - 消息历史管理
  - token 估算与摘要
  - 取消与清理
      |
      +--> LLM Adapter
      |      - Anthropic 协议
      |      - OpenAI 协议
      |      - thinking/reasoning/tool_calls 统一解析
      |
      +--> Tool System
             - file tools: read/write/edit
             - bash tools: 前台/后台执行
             - note tools: 跨会话记忆
             - skill tools: 按需加载 Skills
             - MCP tools: 外部 MCP server 工具接入
```

架构图里 Agent Runtime 的几项能力，在代码里不是独立模块，而是集中落在 `mini_agent/agent.py` 的 `Agent` 状态机里：

- **多轮执行循环**：`run()` 里用 `while step < self.max_steps` 控制执行轮次。每一轮先把当前 `messages` 和工具列表传给 LLM；如果 LLM 返回 `tool_calls`，Runtime 按 tool name 找到本地工具并执行，再把工具结果写回历史；如果没有 `tool_calls`，就把本轮 assistant 文本作为最终结果返回。`max_steps` 是兜底保护，避免模型反复调用工具导致无限循环。
- **消息历史管理**：`Agent` 初始化时把 system prompt 放进 `self.messages`，用户输入通过 `add_user_message()` 追加。每次 LLM 响应都会追加一条 `assistant` message，里面保留普通文本、`thinking` 和 `tool_calls`；每个工具执行结果会追加成 `tool` message，并带上 `tool_call_id` 和工具名。这样下一轮模型能看到完整的“用户目标 -> 模型决策 -> 工具结果”链路。
- **token 估算与摘要**：每轮调用 LLM 前会执行 `_summarize_messages()`。它同时参考本地 `_estimate_tokens()` 的估算值和 Provider 返回的 `response.usage.total_tokens`。本地估算优先用 `tiktoken` 的 `cl100k_base` 编码统计消息正文、thinking、tool calls 和每条消息的额外开销；如果超过 `token_limit`，就按用户轮次保留 system 和 user message，把中间 assistant/tool 执行过程压缩成 `[Assistant Execution Summary]`，从而保留关键结果并降低上下文长度。
- **取消与清理**：CLI 里监听 Esc，把 `asyncio.Event` 设置到 `agent.cancel_event`。`run()` 会在每轮开始、工具执行前、每个工具执行后检查 `_check_cancelled()`。一旦取消，`_cleanup_incomplete_messages()` 会删除最后一条 assistant message 以及它后面的部分 tool result，只保留已经完成的历史，避免下一轮看到半截 tool call / tool result，最后返回 `Task cancelled by user.`。

源码对应关系：

- Agent 主循环：`mini_agent/agent.py`
- LLM 抽象层：`mini_agent/llm/base.py`
- Provider 包装：`mini_agent/llm/llm_wrapper.py`
- Anthropic/OpenAI 适配：`mini_agent/llm/anthropic_client.py`、`mini_agent/llm/openai_client.py`
- 工具基类：`mini_agent/tools/base.py`
- MCP 接入：`mini_agent/tools/mcp_loader.py`
- Skill 按需加载：`mini_agent/tools/skill_loader.py`
- CLI 入口：`mini_agent/cli.py`
- ACP 集成：`mini_agent/acp/__init__.py`

## 3. 核心执行链路

Agent 的主流程是一个多轮工具调用闭环：

1. 用户通过 CLI 输入任务。
2. `Agent` 把 system prompt、历史消息、工具 schema 发给 LLM。
3. LLM 返回普通文本、thinking/reasoning，或者一个或多个 tool call。
4. Agent 根据 tool name 找到本地工具并执行。
5. 工具结果作为 `tool` message 追加进历史。
6. 下一轮继续让 LLM 基于工具结果推理。
7. 如果 LLM 不再调用工具，就认为任务完成。

这个逻辑主要在 `mini_agent/agent.py` 的 `run()` 方法里。

## 3.1 Runtime 和 Harness 的理解

### Runtime 是什么

在这个项目里，Runtime 可以理解为“让 Agent 真正跑起来的执行环境和控制系统”。

它不是模型本身，也不是某个工具，而是负责把这些东西串起来：

```text
用户任务
  -> 调用 LLM
  -> 解析 LLM 返回的 tool call
  -> 执行工具
  -> 把工具结果回填给 LLM
  -> 继续下一轮
  -> 判断任务结束
```

更工程化地说：

> Agent Runtime 是一个状态机。它维护消息历史和执行状态，每一轮根据 LLM 输出决定进入“执行工具”还是“结束任务”的状态。它还负责错误处理、上下文压缩、日志记录和最大步数限制。

在 Mini-Agent 里，Runtime 主要对应 `mini_agent/agent.py` 的 `Agent` 主循环，再加上工具系统、LLM 适配层、日志、重试和上下文管理这些配套能力。

Runtime 主要负责：

- 维护 `messages` 历史。
- 把工具列表转成 schema 传给 LLM。
- 调用 LLM Provider。
- 解析 `content`、`thinking`、`tool_calls`。
- 根据 tool name 找到对应工具。
- 执行工具并拿到 `ToolResult`。
- 把工具结果追加成 `tool` message。
- 多轮循环直到没有 tool call。
- 超过 token limit 时做摘要。
- 超过 `max_steps` 时停止。
- 用户取消时清理未完成消息。
- 写执行日志。

面试说法：

> Runtime 是 Agent 的执行内核。LLM 负责推理和决策，工具负责具体动作，而 Runtime 负责调度：什么时候调用模型、怎么把工具 schema 给模型、怎么执行模型返回的工具调用、怎么把工具结果放回上下文、什么时候继续下一轮、什么时候停止。

一句话总结：

> 模型决定“要做什么”，工具负责“怎么动手”，Runtime 负责“把这个过程可靠地跑完”。

### LLM 和 Runtime / Harness 的职责边界

在复杂 Agent 里，LLM 通常负责语义理解和决策建议，但不应该直接掌控执行环境。

LLM 负责：

- 理解任务。
- 拆解目标。
- 选择下一步。
- 生成计划。
- 判断是否继续。

Runtime / Harness 负责：

- 状态管理。
- 工具执行。
- 安全拦截。
- 上下文压缩。
- 权限确认。
- 回滚。
- 日志。
- 重试。

可以这样理解：

```text
LLM:
  负责“想”：理解用户意图、规划步骤、选择工具、解释结果。

Runtime:
  负责“管”：维护状态、执行工具、处理错误、控制循环、记录日志。

Harness:
  负责“测”：构造输入、隔离环境、收集输出、验证行为。
```

这也是为什么复杂 Agent 里即使用大模型做 planning，也需要 Runtime 在外层做约束。模型可以建议“运行测试”或“修改文件”，但真正能不能执行、在哪个目录执行、是否需要确认、失败后如何回滚，都应该由 Runtime 或 Harness 控制。

### Harness 是什么

Harness 更像“测试、评测或包裹执行的外壳”。

它通常负责：

- 准备输入。
- 控制运行环境。
- 构造 fake LLM 或 fake tool。
- 调用 Runtime。
- 收集输出。
- 判断结果是否符合预期。

例如测试里的 harness 可能会做：

```text
准备测试环境
  -> 构造 fake LLM / fake tool
  -> 调用 Agent.run()
  -> 断言工具是否被调用
  -> 断言最终输出是否正确
```

它关注的是：怎么驱动和验证这个系统。

### Runtime 和 Harness 的关系

两者关系可以这样理解：

```text
Harness 驱动 Runtime
Runtime 驱动 LLM 和 Tools
```

或者：

```text
Test / Eval Harness
   |
   v
Agent Runtime
   |
   +--> LLM
   +--> Tools
```

区别：

- Runtime 关注 Agent 在真实任务中怎么运行。
- Harness 关注怎么驱动、测试、评测 Runtime。

举例：

```text
Runtime:
  真实运行时，Agent 收到“创建 calculator.py 并运行测试”的任务，
  自动调用 write_file、bash、edit_file，直到完成。

Harness:
  测试时，构造一个假 LLM，让它固定返回 write_file tool call，
  然后检查 Agent 是否真的执行了 write_file，
  并把工具结果正确追加到 messages。
```

在 Mini-Agent 这个项目里：

- `mini_agent/agent.py` 更像 Runtime。
- `tests/test_agent.py`、`tests/test_integration.py` 里的测试逻辑更像 Harness。
- 如果以后做 benchmark/eval，比如给 Agent 一组任务并统计成功率，那套评测框架也可以叫 Harness。

面试说法：

> Runtime 是 Agent 的执行系统，负责真实任务中的多轮推理和工具调度；Harness 是包在 Runtime 外面的测试或评测驱动，用来构造输入、隔离环境、收集输出和验证行为。简单说，Runtime 负责跑任务，Harness 负责驱动和检查 Runtime。

## 4. 项目亮点

### 4.1 统一 LLM 协议适配

项目内部统一使用 `Message`、`ToolCall`、`LLMResponse`，外部支持 Anthropic 和 OpenAI 两种协议。

可以这样讲：

> 我没有把业务逻辑绑死在某个 SDK 上，而是做了协议适配层。Anthropic 的 `tool_use/tool_result` 和 OpenAI 的 `tool_calls/tool` 最终都会转成统一内部结构。

### 4.2 支持 thinking/reasoning 的多轮保留

Anthropic client 解析 `thinking` block，OpenAI client 解析 `reasoning_details`，并在下一轮请求里保留。

这个设计适合复杂任务，因为模型带工具执行时，不能丢掉中间推理状态。

### 4.3 工具系统可扩展

所有工具继承统一 `Tool`，只需要实现：

```python
name
description
parameters
execute()
```

同时工具可以转换为 Anthropic schema 和 OpenAI function schema。

面试说法：

> 我把工具做成协议无关的抽象，工具只关心参数和执行结果，协议转换由适配层处理。

#### 当前默认注册工具

在默认配置下，Agent 会注册以下本地工具：

```text
read_file
write_file
edit_file
bash
bash_output
bash_kill
record_note
recall_notes
get_skill
```

如果 MCP 配置可用，还会额外注册 MCP server 暴露出来的工具，具体数量和名称取决于 `mcp.json`。

各工具作用：

- `read_file`：读取文件，输出带行号，支持 `offset` 和 `limit`，适合读取大文件或源码片段。
- `write_file`：写入文件，会完整覆盖目标文件，适合创建新文件或生成报告。
- `edit_file`：对文件做精确字符串替换，要求 `old_str` 唯一匹配，适合小范围修改。
- `bash`：执行 shell 命令，支持前台执行和后台执行。
- `bash_output`：读取后台 shell 命令的新输出，适合监控长时间运行的服务或任务。
- `bash_kill`：终止后台 shell 进程，并清理相关资源。
- `record_note`：记录会话记忆，例如用户偏好、项目事实、阶段性决策。
- `recall_notes`：读取之前记录的会话记忆，可按 category 过滤。
- `get_skill`：按需加载某个 Skill 的完整内容，用于专业任务指导。

面试说法：

> 这些工具可以分成四类：文件工具、Shell 工具、记忆工具和 Skill 工具。文件和 Shell 是执行工程任务的基础能力；记忆工具提供轻量跨会话上下文；Skill 工具负责按需加载专业任务流程。如果配置了 MCP，还可以把外部服务暴露的工具统一接入到同一个 `Tool` 抽象下。

### 4.4 真实工程任务支持

文件工具支持读、写、精确替换；读文件带行号，长内容按 token 截断。

Bash 工具支持：

- 前台命令执行
- 后台进程启动
- 后台输出轮询
- 后台进程终止

这适合启动服务、跑测试、监控日志等真实工程场景。

### 4.5 长上下文压缩

`Agent` 会估算历史 token，同时参考 API 返回的 token usage。

超过阈值后，它会按用户轮次总结中间执行过程，保留用户意图和关键结果。

这比简单裁剪历史更好，因为它能保留任务阶段信息。

### 4.6 MCP 扩展

项目能读取 `mcp.json`，连接 stdio/SSE/HTTP MCP server，把远程 MCP tools 包装成本地 `Tool`。

面试说法：

> 普通工具是本地写死的 Python 类；MCP 是外部 server 暴露工具，Agent 通过协议动态发现和调用，扩展性更强。

### 4.7 Claude Skills 渐进式加载

项目不是一开始把所有 Skill 内容塞进 prompt，而是先把 Skill 名称和描述注入 system prompt。

真正需要时，Agent 再通过 `get_skill` 加载完整 Skill 内容。

这个点可以讲成上下文成本优化。

### 4.8 可观测性和稳定性

项目包含：

- 完整执行日志
- LLM 请求/响应记录
- 工具调用结果记录
- API 重试机制
- MCP timeout 配置
- 用户取消后的消息清理

这些细节让它更像一个可运行的 Agent Runtime，而不是一次性 demo。

## 5. 面试 Demo 建议

### Demo 1：基础工具调用

让 Agent 创建一个文件、读取、修改、运行测试。

展示重点：

- LLM 如何选择工具
- 工具结果如何回填
- 多轮执行如何结束

#### Demo 1 详细演示脚本

这个 Demo 的目标不是展示模型聊天能力，而是展示 Agent Runtime 的基础闭环：

```text
用户任务
  -> LLM 判断需要调用工具
  -> Agent 执行工具
  -> 工具结果回填给 LLM
  -> LLM 根据结果继续下一步
  -> 没有新的 tool call 后结束
```

推荐演示任务：

```text
请在当前 workspace 下创建一个 Python 文件 calculator.py，实现 add 和 divide 两个函数；
然后创建 test_calculator.py，写 pytest 测试；
运行测试；
如果测试失败，请修改代码直到测试通过；
最后总结你做了什么。
```

这个任务适合作为基础 Demo，因为它会自然触发多种工具：

- `write_file`：创建源文件和测试文件
- `read_file`：读取文件确认内容
- `edit_file`：如果测试失败，修改文件
- `bash`：运行 `pytest`

#### 演示前准备

进入项目目录：

```bash
cd /Users/wqu/Documents/github/Mini-Agent
```

启动 Agent：

```bash
uv run python -m mini_agent.cli --workspace ./workspace
```

如果已经安装成命令行工具，也可以运行：

```bash
mini-agent --workspace ./workspace
```

#### 演示输入

在 Agent 交互界面输入：

```text
请在当前 workspace 下创建一个 Python 文件 calculator.py，实现 add 和 divide 两个函数；
然后创建 test_calculator.py，写 pytest 测试，uv run pytest -q；
运行测试；
如果测试失败，请修改代码直到测试通过；
最后总结你做了什么。
```

#### 现场讲解重点 1：LLM 如何选择工具

当 Agent 收到任务后，主循环会把以下内容发给 LLM：

- system prompt
- 当前消息历史
- 可用工具列表
- 每个工具的 JSON schema

LLM 不是直接执行文件操作，而是返回类似这样的 tool call：

```text
tool_call: write_file
arguments:
  path: calculator.py
  content: ...
```

可以这样讲：

> 这里的关键点是，LLM 只负责规划下一步和生成工具参数，真正的文件写入由 Agent Runtime 根据工具名分发执行。工具 schema 告诉模型每个工具能做什么、需要哪些参数。

源码对应：

- 工具 schema 定义：`mini_agent/tools/base.py`
- 工具注册和初始化：`mini_agent/cli.py`
- LLM 调用和工具列表传入：`mini_agent/agent.py`

#### 现场讲解重点 2：工具结果如何回填

当 `write_file`、`read_file` 或 `bash` 执行完成后，Agent 会把结果包装成 `tool` message 加入历史。

例如：

```text
assistant:
  tool_calls:
    - write_file(path="calculator.py", content="...")

tool:
  name: write_file
  content: Successfully wrote to workspace/calculator.py
```

下一轮 LLM 会看到这个工具结果，再决定继续创建测试文件、读取文件，或者运行测试。

可以这样讲：

> 工具结果不是打印完就结束，而是作为新的上下文回填给模型。这样模型才能知道上一步是否成功，并基于真实执行结果继续决策。

源码对应：

- 工具执行结果结构：`mini_agent/tools/base.py` 的 `ToolResult`
- 工具结果追加历史：`mini_agent/agent.py` 的工具执行循环

#### 现场讲解重点 3：多轮执行如何结束

Agent 每一轮都会调用 LLM。

如果 LLM 返回 tool call，Agent 就继续执行工具。

如果 LLM 没有返回 tool call，只返回最终文本，Agent 就认为任务完成并退出当前 run。

可以这样讲：

> 这个 Agent 的停止条件很直接：当模型认为已经不需要更多工具时，就返回最终回答；Runtime 看到没有 tool calls，就结束本轮任务。为了避免无限循环，还有 `max_steps` 上限。

源码对应：

- 停止条件：`mini_agent/agent.py` 中 `if not response.tool_calls`
- 最大步数限制：`Agent(max_steps=...)`

#### 预期演示过程

理想情况下，你会看到类似过程：

```text
Step 1
  Tool Call: write_file
  Result: Successfully wrote calculator.py

Step 2
  Tool Call: write_file
  Result: Successfully wrote test_calculator.py

Step 3
  Tool Call: bash
  Arguments: pytest
  Result: tests passed

Step 4
  Assistant: 总结本次完成内容
```

如果测试失败，演示效果反而更好：

```text
Step 3
  Tool Call: bash
  Result: pytest failed

Step 4
  Tool Call: read_file
  Result: 读取 calculator.py 或 test_calculator.py

Step 5
  Tool Call: edit_file
  Result: 修改错误代码

Step 6
  Tool Call: bash
  Result: pytest passed

Step 7
  Assistant: 总结修复过程
```

这能更清楚地展示 Agent 是根据真实工具结果做闭环修复，而不是一次性生成答案。

#### 面试讲法

可以这样组织：

> 这个 Demo 展示的是 Agent 的最小可用闭环。我给它一个创建代码、写测试、运行测试并修复的任务。模型第一轮不会直接“假装完成”，而是根据工具 schema 选择 `write_file` 创建文件。Runtime 执行工具后，把结果作为 `tool` message 回填给模型。模型看到文件创建成功后继续写测试，再调用 `bash` 运行 pytest。如果测试失败，失败日志也会作为工具结果回填，模型再读取和编辑文件。最终当模型判断不需要继续调用工具时，它返回总结文本，Runtime 看到没有 tool call，就结束本轮执行。

#### 可以强调的工程价值

- Agent 的行为基于真实工具结果，而不是纯文本猜测。
- 文件写入、测试运行、失败修复都在同一个执行闭环内完成。
- 工具调用协议和工具执行逻辑解耦，后续可以继续扩展更多工具。
- `max_steps` 防止异常情况下无限循环。
- 日志可以回放每次 LLM 请求、响应和工具调用，便于调试。

### Demo 2：长任务执行

让 Agent 分析一个小项目，生成报告，并让它中途多次读取文件。

展示重点：

- 上下文管理
- 执行日志
- 长文件读取和 token 截断

#### Demo 2 详细演示脚本

这个 Demo 的目标是展示 Agent 不只是能执行单步工具，而是能处理一个需要多轮阅读、分析、归纳的长任务。

推荐演示任务：

```text
请分析当前 Mini-Agent 项目的核心架构，重点阅读 agent.py、llm 目录、tools 目录和 config.py；
请输出一份 Markdown 报告，包含：
1. 项目职责划分
2. Agent 执行流程
3. LLM Provider 适配方式
4. 工具系统设计
5. 你认为当前项目的 3 个不足和改进建议
请把报告写入 workspace/architecture_report.md。
```

这个任务适合作为长任务 Demo，因为它会自然触发：

- 多次 `read_file`
- 可能的目录查看或 shell 命令
- 长文件读取
- 多轮总结和归纳
- 最后 `write_file` 输出报告

#### 演示前准备

进入项目目录：

```bash
cd /Users/wqu/Documents/github/Mini-Agent
```

启动 Agent：

```bash
uv run python -m mini_agent.cli --workspace .
```

这里建议把 workspace 设置为项目根目录，这样 Agent 可以读取当前项目源码。

#### 演示输入

```text
请分析当前 Mini-Agent 项目的核心架构，重点阅读 agent.py、llm 目录、tools 目录和 config.py；
请输出一份 Markdown 报告，包含：
1. 项目职责划分
2. Agent 执行流程
3. LLM Provider 适配方式
4. 工具系统设计
5. 你认为当前项目的 3 个不足和改进建议
请把报告写入 workspace/architecture_report.md。
```

#### 现场讲解重点 1：长任务不是一次 prompt 解决

这个任务要求 Agent 读取多个源码文件，然后做跨文件归纳。

可以这样讲：

> 这里我故意不给它直接贴源码，而是让 Agent 自己通过工具读取项目。这样可以展示 Runtime 的多轮感知能力：模型先判断需要读哪些文件，再根据读到的内容继续决定下一步。

#### 现场讲解重点 2：上下文管理

Agent 会维护完整消息历史，包括：

- 用户任务
- LLM 每轮回复
- 每次工具调用
- 每次工具结果

当历史 token 超过阈值后，`Agent` 会触发摘要逻辑，把中间执行过程压缩成总结。

可以这样讲：

> 长任务最大的问题是工具结果会快速膨胀上下文。这个项目没有简单粗暴地丢弃历史，而是按用户轮次总结 Agent 的执行过程，保留完成了什么、调用了哪些工具、得到哪些关键结果。

源码对应：

- token 估算：`mini_agent/agent.py` 的 `_estimate_tokens()`
- 历史摘要：`mini_agent/agent.py` 的 `_summarize_messages()`
- 摘要生成：`mini_agent/agent.py` 的 `_create_summary()`

#### 现场讲解重点 3：长文件读取和 token 截断

`read_file` 会给每一行加行号，并支持 `offset` 和 `limit`。

如果读取内容过长，会按 token 截断，保留头部和尾部，中间加入截断提示。

可以这样讲：

> 这对 Agent 读源码很重要。模型需要引用具体行，也需要避免一次工具结果把上下文撑爆。所以 read_file 做了行号格式化、分页读取和 token 级截断。

源码对应：

- 文件读取工具：`mini_agent/tools/file_tools.py`
- 截断逻辑：`truncate_text_by_tokens()`

#### 现场讲解重点 4：执行日志

每次 Agent run 都会生成日志，记录：

- LLM request
- LLM response
- tool call
- tool result

可以这样讲：

> Agent 类系统很难调试，因为你要知道模型为什么做了某个决策。这个项目把每次请求、响应和工具结果都落日志，出问题时可以回放执行轨迹。

源码对应：

- 日志模块：`mini_agent/logger.py`
- CLI 日志命令：`/log`

#### 预期演示过程

理想情况下，你会看到类似过程：

```text
Step 1
  Tool Call: read_file
  Arguments: mini_agent/agent.py
  Result: 返回带行号源码

Step 2
  Tool Call: read_file
  Arguments: mini_agent/llm/llm_wrapper.py
  Result: 返回 LLM Provider 包装逻辑

Step 3
  Tool Call: read_file
  Arguments: mini_agent/tools/base.py
  Result: 返回工具抽象

Step 4
  Tool Call: read_file
  Arguments: mini_agent/config.py
  Result: 返回配置模型

Step 5
  Tool Call: write_file
  Arguments: workspace/architecture_report.md
  Result: 写入架构报告

Step 6
  Assistant: 总结报告已生成
```

如果文件较多，Agent 可能会多次读取目录或分段读取文件。

#### 面试讲法

可以这样组织：

> 这个 Demo 展示的是长任务处理能力。我让 Agent 分析整个项目架构，而不是只回答一个孤立问题。它会先根据任务选择关键源码文件，通过 `read_file` 多轮读取，再把不同模块的信息合并成架构报告。整个过程中，工具结果都会进入消息历史。如果上下文过长，Runtime 会触发摘要，把已经完成的分析过程压缩，避免后续请求超 token。最后它用 `write_file` 输出报告，并通过最终回答结束任务。

#### 可以强调的工程价值

- Agent 能主动探索代码，而不是依赖用户一次性提供全部上下文。
- 长文件读取有行号、分页和 token 截断，便于模型定位代码。
- 历史摘要机制降低长任务的上下文压力。
- 日志可用于调试 Agent 决策链路。
- 这个 Demo 更贴近真实工程助手场景，例如代码审查、架构分析、迁移评估。

### Demo 3：MCP 或 Skill

接一个简单 MCP server，或者用内置 Skill 完成文档、测试、设计类任务。

展示重点：

- 工具动态扩展
- Skills 按需加载
- Agent 能力从本地工具扩展到外部服务

#### Demo 3 详细演示脚本

这个 Demo 的目标是展示 Agent 的能力不是写死在本地工具里，而是可以通过 Skills 和 MCP 扩展。

建议优先演示 Skill，因为当前项目已经内置了多种 Skills，不需要额外搭 MCP server。

推荐演示任务：

```text
请查看当前可用的 Skills，选择适合“代码仓库自动巡检报告”的 Skill；
加载该 Skill 的完整内容；
然后基于当前 Mini-Agent 项目，生成一份适合面试展示的代码仓库巡检报告，
写入 workspace/repo_inspection_report.md。
```

这个任务适合作为 Skill Demo，因为它会自然触发：

- 系统 prompt 中的 Skill metadata
- `get_skill` 工具调用
- Skill 完整内容按需加载
- 基于 Skill 指导完成具体任务
- 最后输出文件

#### 演示前准备

确认配置里启用了 Skills：

```yaml
tools:
  enable_skills: true
```

启动 Agent：

```bash
cd /Users/wqu/Documents/github/Mini-Agent
uv run python -m mini_agent.cli --workspace .
```

#### 演示输入

```text
请查看当前可用的 Skills，选择适合“代码仓库自动巡检报告”的 Skill；
加载该 Skill 的完整内容；
然后基于当前 Mini-Agent 项目，生成一份适合面试展示的代码仓库巡检报告，
写入 workspace/repo_inspection_report.md。
```

#### 现场讲解重点 1：Skills 不是普通 prompt 模板

Skills 是一组可复用的专业能力说明，每个 Skill 有自己的 `SKILL.md`，里面包含：

- name
- description
- 使用指导
- 可能的脚本
- 可能的参考文件

可以这样讲：

> Skill 更像是给 Agent 的专业操作手册，而不是简单 prompt。它告诉模型遇到某类任务时应该按什么流程做、可以读哪些参考文件、可以调用哪些脚本。

源码对应：

- Skill 解析：`mini_agent/tools/skill_loader.py`
- Skill 工具：`mini_agent/tools/skill_tool.py`

#### 现场讲解重点 2：渐进式加载降低上下文成本

项目启动时不会把所有 Skill 全文塞进 system prompt。

流程是：

```text
启动时发现 Skills
  -> system prompt 只注入 name + description
  -> LLM 判断当前任务需要某个 Skill
  -> 调用 get_skill
  -> Runtime 返回该 Skill 完整内容
  -> LLM 按 Skill 指导执行任务
```

可以这样讲：

> 如果一次性加载所有 Skill，prompt 会非常长，成本高且干扰模型判断。这里采用渐进式加载，先让模型知道有哪些技能，真正需要时再加载完整内容。

#### 现场讲解重点 3：Agent 能力从本地工具扩展到专业流程

基础工具只能提供“能力原语”，比如读文件、写文件、跑命令。

Skill 提供的是“完成某类任务的方法论”。

可以这样讲：

> 工具解决的是能不能做，Skill 解决的是该怎么做。比如 `read_file` 只能读文件，但代码巡检类 Skill 可以指导 Agent 先看项目结构、再看核心模块、再总结风险和改进建议。

#### 预期演示过程

理想情况下，你会看到类似过程：

```text
启动阶段
  Discovered N Claude Skills

Step 1
  Tool Call: get_skill
  Arguments: skill_name=...
  Result: 返回完整 Skill 内容

Step 2
  Tool Call: read_file
  Arguments: README.md 或核心源码
  Result: 返回项目说明或源码

Step 3
  Tool Call: read_file
  Arguments: mini_agent/agent.py
  Result: 返回 Agent 主循环

Step 4
  Tool Call: write_file
  Arguments: workspace/repo_inspection_report.md
  Result: 写入巡检报告

Step 5
  Assistant: 总结报告已生成
```

#### MCP 备选演示

如果面试官特别关注 MCP，可以这样讲，不一定现场实操：

> MCP 的作用是让 Agent 不只使用本地 Python 工具，还可以连接外部 MCP server。项目会读取 `mcp.json`，连接 stdio、SSE 或 HTTP 类型的 server，调用 `list_tools()` 获取外部工具定义，再包装成统一的 `Tool`。这样 Agent 主循环不需要知道工具来自本地还是远程。

MCP 代码路径：

- MCP 连接管理：`mini_agent/tools/mcp_loader.py`
- MCPTool 包装：`MCPTool`
- MCP server 配置：`mini_agent/config/mcp-example.json`

MCP 讲解流程：

```text
mcp.json
  -> load_mcp_tools_async()
  -> MCPServerConnection.connect()
  -> session.list_tools()
  -> MCPTool(...)
  -> 加入 Agent tools
  -> LLM 像调用普通工具一样调用 MCP 工具
```

#### 面试讲法

可以这样组织：

> 这个 Demo 展示的是 Agent 的扩展机制。基础工具提供读写文件和命令执行这类原子能力，但面对专业任务，Agent 还需要流程性知识。项目通过 Skills 做渐进式加载：启动时只把 Skill 名称和描述放进 prompt，模型判断需要时再调用 `get_skill` 获取完整内容。这样既节省上下文，又能让 Agent 获得面向具体任务的操作手册。如果要接外部系统，则通过 MCP 动态发现远程工具，并包装成统一 `Tool`，让 Agent 主循环无感调用。

#### 可以强调的工程价值

- Skills 让 Agent 从“能调用工具”提升到“知道怎么完成专业任务”。
- 渐进式加载减少上下文浪费。
- MCP 让工具来源从本地扩展到外部服务。
- 本地工具、Skill 工具、MCP 工具最终都统一成 `Tool` 接口。
- 扩展能力不需要修改 Agent 主循环。

## 6. 如何真正变成自己的项目

只读懂项目不够，建议至少做 3 个明确改造。

### 6.1 加一个自己的工具

可选方向：

- `git_diff_analyzer`
- `pytest_runner`
- `code_search`
- `web_search`
- `jira_reader`

实现一个新的 `Tool`，并接入 CLI 初始化流程。

#### 6.1.1 自定义工具开发通用步骤

新增工具的核心路径是：

```text
定义 Tool 类
  -> 实现 name / description / parameters / execute()
  -> 在 CLI 初始化时注册工具
  -> 让 LLM 通过 tool schema 看到工具
  -> 在 Demo 中触发工具调用
```

在 Mini-Agent 里，所有工具都继承 `mini_agent/tools/base.py` 里的 `Tool`。

最小结构：

```python
from typing import Any

from .base import Tool, ToolResult


class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Describe what this tool does and when to use it."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Input query",
                }
            },
            "required": ["query"],
        }

    async def execute(self, query: str) -> ToolResult:
        try:
            result = f"received query: {query}"
            return ToolResult(success=True, content=result)
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
```

接入位置：

- 新工具文件建议放在 `mini_agent/tools/` 下。
- 工具注册一般放在 `mini_agent/cli.py` 的工具初始化流程中。
- 如果希望可配置开关，需要同步修改 `mini_agent/config.py` 和 `mini_agent/config/config-example.yaml`。

面试说法：

> 我扩展工具时没有改 Agent 主循环，而是复用了统一 `Tool` 抽象。新工具只需要声明工具名、描述、参数 schema 和执行逻辑，Runtime 会自动把 schema 传给模型，并在模型返回 tool call 时完成分发执行。

#### 6.1.2 方案一：实现 `web_search` 工具

##### 目标

给 Agent 增加联网搜索能力，让它可以在回答涉及实时信息、外部资料、文档查询时主动搜索。

适合展示：

- Agent 不只依赖本地文件。
- 工具能力可以扩展到外部 API。
- 模型先判断“需要搜索”，再调用 `web_search`。

##### 工具设计

工具名：

```text
web_search
```

参数设计：

```text
query: 搜索关键词
num_results: 返回结果数量，默认 5
```

返回内容建议包含：

- 标题
- URL
- 摘要
- 来源

示例返回：

```text
1. Title: OpenRouter Documentation
   URL: https://openrouter.ai/docs
   Snippet: OpenRouter provides an OpenAI-compatible API...
```

##### 实现步骤

第一步：新增工具文件。

建议创建：

```text
mini_agent/tools/web_search_tool.py
```

示例代码：

```python
"""Web search tool."""

from typing import Any

import httpx

from .base import Tool, ToolResult


class WebSearchTool(Tool):
    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key
        self.endpoint = endpoint or "https://api.tavily.com/search"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for up-to-date external information. "
            "Use this when the answer depends on current facts, external docs, news, prices, or recent changes."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, num_results: int = 5) -> ToolResult:
        if not self.api_key:
            return ToolResult(
                success=False,
                content="",
                error="web_search API key is not configured",
            )

        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max(1, min(num_results, 10)),
            }
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if not results:
                return ToolResult(success=True, content="No search results found.")

            lines = []
            for idx, item in enumerate(results, 1):
                title = item.get("title", "")
                url = item.get("url", "")
                snippet = item.get("content", "") or item.get("snippet", "")
                lines.append(f"{idx}. Title: {title}\n   URL: {url}\n   Snippet: {snippet}")

            return ToolResult(success=True, content="\n\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content="", error=f"web_search failed: {e}")
```

这里用 Tavily 作为示例，因为它是常见搜索 API。也可以替换为 SerpAPI、Bing Search API、Brave Search API 或公司内部搜索服务。

第二步：增加配置项。

在配置中预留：

```yaml
tools:
  enable_web_search: true
  web_search:
    api_key: "YOUR_SEARCH_API_KEY_HERE"
    endpoint: "https://api.tavily.com/search"
```

如果想更规范，需要在 `mini_agent/config.py` 中给 `ToolsConfig` 增加字段。

第三步：在 CLI 初始化流程中注册工具。

在 `mini_agent/cli.py` 中引入：

```python
from mini_agent.tools.web_search_tool import WebSearchTool
```

然后在工具初始化逻辑里追加：

```python
if getattr(config.tools, "enable_web_search", False):
    tools.append(
        WebSearchTool(
            api_key=config.tools.web_search.api_key,
            endpoint=config.tools.web_search.endpoint,
        )
    )
```

如果暂时不想改 Pydantic 配置模型，也可以先用环境变量：

```python
import os

search_api_key = os.getenv("WEB_SEARCH_API_KEY")
if search_api_key:
    tools.append(WebSearchTool(api_key=search_api_key))
```

第四步：演示触发。

可以输入：

```text
请搜索 OpenRouter 当前的免费模型限制，并总结哪些信息适合写进我的 Mini-Agent 面试 Demo。
```

预期链路：

```text
User asks current external information
  -> LLM 选择 web_search
  -> Runtime 执行 web_search
  -> 搜索结果回填给 LLM
  -> LLM 基于结果总结
```

##### 面试讲法

> 我新增了 `web_search` 工具，用来补齐 Agent 对实时外部信息的访问能力。实现上仍然复用统一 `Tool` 抽象，只是 execute 里调用搜索 API。模型通过工具 schema 知道何时该搜索，Runtime 负责执行搜索并把搜索结果作为 tool message 回填。这样 Agent 就可以在需要当前信息时主动检索，而不是只依赖训练语料。

##### 注意事项

- 搜索结果要限制数量，避免污染上下文。
- 返回内容要结构化，方便模型引用。
- 最好要求模型在最终回答里带来源 URL。
- 搜索 API key 不要写死进代码，放配置或环境变量。
- 面试时可以强调“工具只负责检索，最终判断仍由 LLM 完成”。

#### 6.1.3 方案二：实现 `jira_reader` 工具

##### 目标

给 Agent 增加读取 Jira issue 的能力，让它可以基于真实需求单、bug 单或任务单做分析。

适合展示：

- Agent 能接企业内部系统。
- Agent 可以读取结构化业务上下文。
- 可以把需求、代码、测试串成完整工程流程。

##### 工具设计

工具名：

```text
jira_reader
```

建议先做两个能力：

```text
get_issue: 根据 issue key 读取单个 Jira issue
search_issues: 根据 JQL 搜索多个 Jira issues
```

为了简单，也可以先只实现一个工具 `jira_reader`，通过参数区分模式。

参数设计：

```text
issue_key: 单个 issue 编号，例如 PROJ-123
jql: 可选，Jira Query Language
max_results: 可选，默认 10
```

返回内容建议包含：

- issue key
- summary
- status
- assignee
- reporter
- description
- priority
- labels
- comments 摘要

##### 实现步骤

第一步：新增工具文件。

建议创建：

```text
mini_agent/tools/jira_reader_tool.py
```

示例代码：

```python
"""Jira reader tool."""

from typing import Any

import httpx

from .base import Tool, ToolResult


class JiraReaderTool(Tool):
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token

    @property
    def name(self) -> str:
        return "jira_reader"

    @property
    def description(self) -> str:
        return (
            "Read Jira issues by issue key or JQL. "
            "Use this to understand product requirements, bugs, acceptance criteria, and task context."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "Jira issue key, for example PROJ-123",
                },
                "jql": {
                    "type": "string",
                    "description": "Optional Jira Query Language for searching issues",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of issues to return when using JQL",
                    "default": 10,
                },
            },
        }

    async def execute(
        self,
        issue_key: str | None = None,
        jql: str | None = None,
        max_results: int = 10,
    ) -> ToolResult:
        if not issue_key and not jql:
            return ToolResult(
                success=False,
                content="",
                error="Either issue_key or jql is required",
            )

        try:
            async with httpx.AsyncClient(timeout=30, auth=(self.email, self.api_token)) as client:
                if issue_key:
                    url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
                    response = await client.get(
                        url,
                        params={
                            "fields": "summary,status,assignee,reporter,description,priority,labels,comment"
                        },
                    )
                    response.raise_for_status()
                    return ToolResult(success=True, content=self._format_issue(response.json()))

                url = f"{self.base_url}/rest/api/3/search"
                response = await client.get(
                    url,
                    params={
                        "jql": jql,
                        "maxResults": max(1, min(max_results, 20)),
                        "fields": "summary,status,assignee,reporter,priority,labels",
                    },
                )
                response.raise_for_status()
                data = response.json()
                issues = data.get("issues", [])
                if not issues:
                    return ToolResult(success=True, content="No Jira issues found.")
                return ToolResult(
                    success=True,
                    content="\n\n".join(self._format_issue(issue, include_description=False) for issue in issues),
                )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"jira_reader failed: {e}")

    def _format_issue(self, issue: dict[str, Any], include_description: bool = True) -> str:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        status = (fields.get("status") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
        reporter = (fields.get("reporter") or {}).get("displayName", "")
        labels = ", ".join(fields.get("labels") or [])

        parts = [
            f"Key: {key}",
            f"Summary: {summary}",
            f"Status: {status}",
            f"Priority: {priority}",
            f"Assignee: {assignee}",
            f"Reporter: {reporter}",
            f"Labels: {labels}",
        ]

        if include_description:
            description = fields.get("description")
            parts.append(f"Description: {description}")

            comments = ((fields.get("comment") or {}).get("comments") or [])[-5:]
            if comments:
                parts.append("Recent Comments:")
                for comment in comments:
                    author = (comment.get("author") or {}).get("displayName", "")
                    body = comment.get("body", "")
                    parts.append(f"- {author}: {body}")

        return "\n".join(parts)
```

第二步：增加配置项。

建议配置：

```yaml
tools:
  enable_jira_reader: true
  jira:
    base_url: "https://your-company.atlassian.net"
    email: "YOUR_EMAIL_HERE"
    api_token: "YOUR_JIRA_API_TOKEN_HERE"
```

更安全的方式是用环境变量：

```bash
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-token"
```

第三步：在 CLI 初始化流程中注册工具。

在 `mini_agent/cli.py` 中引入：

```python
from mini_agent.tools.jira_reader_tool import JiraReaderTool
```

然后追加：

```python
import os

jira_base_url = os.getenv("JIRA_BASE_URL")
jira_email = os.getenv("JIRA_EMAIL")
jira_api_token = os.getenv("JIRA_API_TOKEN")

if jira_base_url and jira_email and jira_api_token:
    tools.append(
        JiraReaderTool(
            base_url=jira_base_url,
            email=jira_email,
            api_token=jira_api_token,
        )
    )
```

第四步：演示触发。

可以输入：

```text
请读取 Jira issue PROJ-123，总结需求背景、验收标准、潜在技术风险，并给出实现计划。
```

或者：

```text
请搜索当前项目中 status = "To Do" 且 priority = High 的 Jira issues，
按优先级生成本周开发计划。
```

预期链路：

```text
User asks about Jira issue
  -> LLM 选择 jira_reader
  -> Runtime 调用 Jira REST API
  -> issue 内容作为 tool result 回填
  -> LLM 总结需求、风险和计划
```

##### 面试讲法

> 我新增 `jira_reader` 是为了展示 Agent 接入企业工程系统的能力。Jira 里有真实需求、bug、验收标准和评论上下文。Agent 可以先读取 issue，再结合本地代码工具分析影响范围，最后生成实现计划或测试建议。这个工具仍然遵循统一 `Tool` 抽象，所以 Agent 主循环不用知道 Jira 的存在，只要按工具名分发执行即可。

##### 注意事项

- Jira token 不要写死进仓库，建议用环境变量。
- 返回评论时要限制数量，避免上下文过长。
- Jira 的 `description` 是 Atlassian Document Format，不是普通纯文本，生产级实现最好做格式转换。
- 企业 Jira 可能有权限限制，工具要把 401/403 明确返回给模型。
- 如果涉及敏感需求，日志里可能会记录 issue 内容，需要考虑脱敏或关闭详细日志。

#### 6.1.4 两个工具的组合 Demo

更完整的展示任务：

```text
请读取 Jira issue PROJ-123，理解需求背景；
然后搜索相关公开技术文档；
再阅读当前仓库中可能受影响的模块；
最后生成一份实现方案和风险评估，写入 workspace/implementation_plan.md。
```

这个 Demo 能展示完整工程链路：

```text
jira_reader
  -> 获取业务需求
web_search
  -> 获取外部资料
read_file
  -> 理解本地代码
write_file
  -> 生成实现方案
```

面试总结：

> 这两个工具体现了我的扩展思路：`web_search` 解决外部实时信息获取，`jira_reader` 解决企业内部需求上下文获取。它们都不是改 Agent 主循环，而是作为工具挂到 Runtime 上。这样 Agent 的核心调度逻辑保持稳定，能力通过工具生态持续扩展。

### 6.2 改进记忆系统

当前记忆只是 JSON notes，适合保存用户偏好、项目事实、阶段性决策。

可以升级为：

- 按 workspace 隔离记忆
- 支持 category 查询
- 支持全文搜索
- 接 SQLite
- 接向量库做语义检索

#### 6.2.1 当前记忆系统的边界

当前项目的记忆工具主要在：

```text
mini_agent/tools/note_tool.py
```

它包含两个工具：

```text
record_note
recall_notes
```

当前实现方式：

```text
Agent 调用 record_note
  -> 读取 JSON 文件
  -> 追加一条 note
  -> 写回 JSON 文件

Agent 调用 recall_notes
  -> 读取 JSON 文件
  -> 可按 category 过滤
  -> 返回所有匹配 notes
```

优点：

- 实现简单。
- 适合 Demo。
- 适合保存用户偏好、项目事实、阶段性决策。

不足：

- 默认记忆文件容易混在一起。
- 不按 workspace 隔离时，不同项目的上下文会互相污染。
- 只能按 category 过滤，不能按语义检索。
- notes 多了以后，全部返回会占用大量上下文。

面试说法：

> 当前记忆更像轻量 notes，不是完整长期记忆系统。它适合记录明确事实，但不适合从大量历史内容中找语义相关信息。所以我的改造方向是两步：先按 workspace 隔离，避免项目间污染；再接向量库，让 Agent 可以按当前任务语义召回相关记忆。

#### 6.2.2 方案一：按 workspace 隔离记忆

##### 目标

让每个 workspace 拥有独立记忆文件，避免不同项目之间的记忆混用。

例如：

```text
workspace/project-a/.mini_agent_memory.json
workspace/project-b/.mini_agent_memory.json
```

或者统一放在用户目录下，用 workspace hash 隔离：

```text
~/.mini-agent/memory/{workspace_hash}.json
```

##### 推荐方案

推荐使用用户目录 + workspace hash：

```text
~/.mini-agent/memory/{workspace_hash}.json
```

原因：

- 不污染项目仓库。
- 不容易误提交到 git。
- 同一个 workspace 每次启动都能找到同一份记忆。
- hash 后路径稳定，也能避免 workspace 路径里有特殊字符。

##### 实现步骤

第一步：新增一个生成 memory path 的工具函数。

可以放在 `mini_agent/tools/note_tool.py` 或新文件 `mini_agent/tools/memory_path.py`。

示例：

```python
import hashlib
from pathlib import Path


def get_workspace_memory_file(workspace_dir: str) -> Path:
    workspace_path = str(Path(workspace_dir).expanduser().resolve())
    workspace_hash = hashlib.sha256(workspace_path.encode("utf-8")).hexdigest()[:16]
    memory_dir = Path.home() / ".mini-agent" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir / f"{workspace_hash}.json"
```

第二步：修改 `SessionNoteTool` 和 `RecallNoteTool` 初始化方式。

当前是：

```python
SessionNoteTool(memory_file="./workspace/.agent_memory.json")
RecallNoteTool(memory_file="./workspace/.agent_memory.json")
```

改成根据 workspace 生成：

```python
memory_file = get_workspace_memory_file(workspace_dir)

tools.append(SessionNoteTool(memory_file=str(memory_file)))
tools.append(RecallNoteTool(memory_file=str(memory_file)))
```

第三步：在 CLI 工具初始化时传入 workspace。

工具注册时已经知道 workspace，就可以生成对应 memory file。

伪代码：

```python
if config.tools.enable_note:
    memory_file = get_workspace_memory_file(str(workspace_dir))
    tools.append(SessionNoteTool(memory_file=str(memory_file)))
    tools.append(RecallNoteTool(memory_file=str(memory_file)))
```

第四步：给记忆文件加 metadata。

建议 JSON 结构从简单 list 升级为：

```json
{
  "workspace": "/abs/path/to/workspace",
  "notes": [
    {
      "timestamp": "2026-06-10T10:00:00",
      "category": "project_info",
      "content": "This project uses OpenRouter with provider=openai."
    }
  ]
}
```

这样后续调试时能知道这份记忆属于哪个项目。

##### Demo 触发

演示任务：

```text
请记录一条项目记忆：这个项目的 Agent Runtime 主循环在 mini_agent/agent.py。
然后读取当前 workspace 的全部记忆。
```

预期链路：

```text
record_note
  -> 写入当前 workspace 对应 memory 文件
recall_notes
  -> 只读取当前 workspace 的记忆
```

##### 面试讲法

> 我把记忆从全局 JSON 改成按 workspace 隔离。这样 Agent 在不同项目里工作时，不会把 A 项目的技术栈、用户偏好或阶段性结论带到 B 项目。实现上我用 workspace 绝对路径计算 hash，把记忆存到 `~/.mini-agent/memory/{workspace_hash}.json`，这样既不污染代码仓库，也能保证同一个项目重复启动时复用同一份记忆。

#### 6.2.3 方案二：接向量库做语义检索

##### 目标

把记忆系统从“全部 recall”升级为“按当前任务语义召回相关记忆”。

当前 `recall_notes` 的问题是：

```text
notes 少时可用
notes 多时上下文浪费
只能按 category 过滤
不能找到语义相近内容
```

向量检索后的流程：

```text
record_note
  -> 生成 embedding
  -> 写入向量库

semantic_recall
  -> 对 query 生成 embedding
  -> top_k 相似度检索
  -> 返回最相关 notes
```

##### 技术选型

轻量本地 Demo 推荐：

```text
Chroma
```

原因：

- Python 接入简单。
- 支持本地持久化。
- 适合 Demo 和小规模项目记忆。

也可以选择：

- FAISS：更底层，适合本地高性能向量检索。
- Qdrant：适合服务化部署。
- Milvus：适合大规模向量检索。
- SQLite + sqlite-vec：适合轻量嵌入式方案。

##### 推荐架构

```text
MemoryTool
   |
   +--> JSON / SQLite metadata store
   |
   +--> Vector Store
          - note_id
          - embedding
          - workspace_id
          - category
          - timestamp
```

为什么还需要 metadata store：

> 向量库适合相似度检索，但业务字段、时间、category、workspace 过滤仍然需要结构化 metadata。生产实现里通常是 metadata + vector store 组合。

##### 工具设计

新增或改造三个工具：

```text
record_memory
semantic_recall
list_memory
```

也可以保留原来的：

```text
record_note
recall_notes
```

然后新增：

```text
semantic_recall_notes
```

参数设计：

```text
record_note:
  content: 记忆内容
  category: 分类

semantic_recall_notes:
  query: 当前要检索的问题
  top_k: 返回数量，默认 5
  category: 可选过滤条件
```

##### 实现步骤

第一步：增加依赖。

可以在 `pyproject.toml` 加：

```toml
dependencies = [
    ...
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",
]
```

如果不想引入本地 embedding 模型，也可以用 OpenAI-compatible embedding API。

本地 Demo 推荐先用 `sentence-transformers`，避免额外 API 成本。

第二步：设计 workspace collection。

每个 workspace 一个 collection：

```text
mini_agent_memory_{workspace_hash}
```

或者一个总 collection，通过 metadata 过滤：

```text
collection: mini_agent_memory
metadata:
  workspace_id: xxx
```

推荐第二种，因为后续可以跨 workspace 管理。

第三步：实现 embedding provider。

可以先抽象一个简单类：

```python
class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

本地实现：

```python
from sentence_transformers import SentenceTransformer


class LocalEmbeddingProvider:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()
```

第四步：实现向量记忆工具。

建议新增：

```text
mini_agent/tools/vector_memory_tool.py
```

核心逻辑：

```python
class SemanticRecallTool(Tool):
    @property
    def name(self) -> str:
        return "semantic_recall_notes"

    @property
    def description(self) -> str:
        return "Recall semantically relevant notes for the current task."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Number of notes to return", "default": 5},
                "category": {"type": "string", "description": "Optional category filter"},
            },
            "required": ["query"],
        }
```

写入时：

```text
note_id = uuid
embedding = embed(content)
collection.add(
  ids=[note_id],
  documents=[content],
  metadatas=[{
    "workspace_id": workspace_id,
    "category": category,
    "timestamp": timestamp
  }],
  embeddings=[embedding]
)
```

查询时：

```text
query_embedding = embed(query)
collection.query(
  query_embeddings=[query_embedding],
  n_results=top_k,
  where={"workspace_id": workspace_id}
)
```

第五步：注册工具。

在 CLI 初始化时：

```python
if config.tools.enable_vector_memory:
    tools.append(VectorRecordNoteTool(...))
    tools.append(SemanticRecallTool(...))
```

配置示例：

```yaml
tools:
  enable_vector_memory: true
  vector_memory:
    persist_dir: "~/.mini-agent/vector_memory"
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
    top_k: 5
```

第六步：更新 system prompt。

可以在 system prompt 中提醒 Agent：

```text
When the user asks about previous project context, preferences, decisions, or recurring issues,
use semantic_recall_notes before answering.
```

这样模型更容易主动调用语义检索工具。

##### Demo 触发

先记录几条记忆：

```text
请记录这些项目记忆：
1. 这个项目使用 OpenRouter 作为 OpenAI-compatible Provider。
2. Agent Runtime 主循环在 mini_agent/agent.py。
3. 工具系统统一继承 mini_agent/tools/base.py 里的 Tool。
```

再提问：

```text
我之前关于模型供应商配置记录了什么？请从记忆里找相关内容回答。
```

预期链路：

```text
semantic_recall_notes(query="模型供应商配置")
  -> 返回 OpenRouter 相关记忆
  -> LLM 基于召回内容回答
```

##### 面试讲法

> 我把记忆系统从简单 JSON notes 扩展成 workspace-aware 的语义记忆。写入记忆时，系统会把 note 内容向量化，并带上 workspace、category、timestamp 等 metadata 存入向量库。召回时，Agent 不再把所有历史 notes 都塞进上下文，而是根据当前问题做 top-k 语义检索，只返回最相关的记忆。这能减少上下文浪费，也能让长期记忆在 notes 较多时仍然可用。

##### 注意事项

- 向量检索要按 workspace_id 过滤，避免跨项目污染。
- top_k 不宜过大，通常 3 到 8 条即可。
- 记忆内容要短而具体，避免整段日志直接入库。
- 对敏感信息要脱敏或禁止写入向量库。
- embedding 模型要固定，否则历史向量可能和新向量空间不一致。
- 生产环境最好增加删除、更新、过期和导出能力。

#### 6.2.4 组合改造后的记忆架构

最终可以演进成：

```text
Agent Runtime
   |
   +--> record_note
   |      -> workspace_id
   |      -> JSON/SQLite metadata
   |      -> embedding
   |      -> vector store
   |
   +--> recall_notes
   |      -> category/time filter
   |
   +--> semantic_recall_notes
          -> query embedding
          -> workspace filter
          -> top-k relevant notes
```

面试总结：

> 我对记忆系统的改造分两层。第一层是 workspace 隔离，解决不同项目记忆互相污染的问题。第二层是语义检索，解决 notes 增多后无法高效召回的问题。这样 Agent 不只是“能记住”，而是能在合适的项目上下文里找回和当前任务最相关的历史信息。

### 6.3 增强安全边界

当前文件和 bash 工具比较自由。

可以加：

- workspace 路径限制
- bash 命令 allowlist/denylist
- 写文件前 diff 预览
- 危险命令确认

#### 6.3.1 危险命令确认的实现思路

这个点可以做成一个很适合面试展示的小改造：不是直接禁用 bash，而是在 Agent Runtime 执行工具前增加一层“风险识别 + 人工确认”。

当前 `BashTool.execute()` 会直接把模型给出的 `command` 交给 shell 执行：

```text
LLM tool call
  -> Agent.run()
  -> tool.execute(**arguments)
  -> BashTool.execute(command)
  -> create_subprocess_shell(command)
```

可以改成：

```text
LLM tool call
  -> Agent.run()
  -> SecurityPolicy.inspect(tool_name, arguments)
  -> 安全命令：直接执行
  -> 危险命令：展示命令、风险原因、影响范围，等待用户确认
  -> 用户确认后执行；用户拒绝则返回 ToolResult 失败
```

##### 第一步：在配置里增加安全策略

在 `mini_agent/config.py` 的 `ToolsConfig` 里加几项配置：

```python
class ToolsConfig(BaseModel):
    enable_bash: bool = True

    require_confirmation_for_dangerous_commands: bool = True
    dangerous_command_patterns: list[str] = [
        r"\brm\s+-rf\b",
        r"\bsudo\b",
        r"\bchmod\s+-R\b",
        r"\bchown\s+-R\b",
        r"\bdd\b",
        r">\s*/dev/",
        r"\bmkfs\b",
        r"\bgit\s+clean\s+-fd",
        r"\bgit\s+reset\s+--hard",
        r"\bcurl\b.*\|\s*(bash|sh)",
        r"\bwget\b.*\|\s*(bash|sh)",
    ]
```

这样面试时可以说：风险规则不是硬编码在工具里，而是放在配置层，方便不同环境调整。

##### 第二步：新增安全检查模块

新建 `mini_agent/security.py`，负责判断一个工具调用是否需要确认。

核心逻辑：

```python
import re
from dataclasses import dataclass


@dataclass
class SecurityDecision:
    requires_confirmation: bool
    reasons: list[str]


class SecurityPolicy:
    def __init__(self, dangerous_patterns: list[str]) -> None:
        self.dangerous_patterns = [re.compile(p) for p in dangerous_patterns]

    def inspect(self, tool_name: str, arguments: dict) -> SecurityDecision:
        if tool_name != "bash":
            return SecurityDecision(False, [])

        command = str(arguments.get("command", ""))
        reasons = []

        for pattern in self.dangerous_patterns:
            if pattern.search(command):
                reasons.append(f"matched pattern: {pattern.pattern}")

        return SecurityDecision(bool(reasons), reasons)
```

这一步要保持简单：先只处理 `bash` 工具，后面再扩展到 `write_file`、`edit_file`、MCP 工具等。

##### 第三步：在 Agent 执行工具前拦截

拦截点放在 `mini_agent/agent.py` 中真正执行工具之前，也就是：

```python
tool = self.tools[function_name]
result = await tool.execute(**arguments)
```

前面插入：

```python
decision = self.security_policy.inspect(function_name, arguments)
if decision.requires_confirmation:
    approved = self.confirm_tool_call(function_name, arguments, decision.reasons)
    if not approved:
        result = ToolResult(
            success=False,
            content="",
            error="User rejected dangerous command execution.",
        )
        continue
```

这样危险命令不会进入 `BashTool.execute()`，也不会被 shell 执行。

##### 第四步：实现 CLI 确认交互

在 `Agent` 或 CLI 交互层实现一个确认函数：

```python
def confirm_tool_call(self, tool_name: str, arguments: dict, reasons: list[str]) -> bool:
    print("\nDangerous tool call requires confirmation")
    print(f"Tool: {tool_name}")
    print(f"Arguments: {arguments}")
    print("Reasons:")
    for reason in reasons:
        print(f"- {reason}")

    answer = input("Execute this command? Type 'yes' to continue: ")
    return answer.strip() == "yes"
```

注意不要用 `y` 默认通过，最好要求用户输入完整的 `yes`。面试时可以强调：这个设计故意增加确认成本，因为它只出现在高风险操作上。

##### 第五步：给工具结果返回明确反馈

用户拒绝时，不应该静默失败，而是把失败结果回填给 LLM：

```text
ToolResult(
  success=False,
  error="User rejected dangerous command execution."
)
```

这样模型能继续选择更安全的替代方案，比如把 `rm -rf build` 改成列出目录、请求用户手动删除，或只删除 workspace 内的临时文件。

##### 第六步：补测试用例

可以增加几类单元测试：

- `echo hello` 不需要确认。
- `rm -rf /tmp/demo` 需要确认。
- `git reset --hard` 需要确认。
- `curl https://example.com/install.sh | bash` 需要确认。
- 用户拒绝后不会调用 `BashTool.execute()`。
- 用户确认后才调用 `BashTool.execute()`。

测试时不需要真的执行危险命令，可以 mock `BashTool.execute()` 和 `confirm_tool_call()`。

##### 面试讲法

> 我在工具执行前加了一层 SecurityPolicy。模型仍然可以提出 bash 调用，但 Runtime 不会盲目执行，而是先根据配置化规则判断风险。普通命令直接通过；匹配到 `rm -rf`、`sudo`、`git reset --hard`、`curl | bash` 这类模式时，CLI 会展示命令和风险原因，要求用户输入完整的 yes 才继续。用户拒绝时，Runtime 会把拒绝结果作为 ToolResult 回填给模型，让模型尝试更安全的替代方案。这样安全边界放在 Runtime 层，而不是依赖模型“自觉”。

##### 可以继续增强的点

- 把命令解析从正则升级为 `shlex` 或 shell AST，降低误判和漏判。
- 对 `rm`、`mv`、`cp` 这类命令额外检查路径是否在 workspace 内。
- 为工具增加 `readOnly`、`destructive`、`externalAccess` 等元数据。
- 区分 `ask`、`allow`、`deny` 三种决策，而不是只有是否确认。
- 在日志里记录危险命令、确认人、确认时间和最终执行结果，方便审计。

### 6.4 增加真实业务场景

可以做成一个“事件脉络 Agent”：

> 面向复杂公共事件、公司舆情、政策变化、行业事故等主题，自动检索候选来源、抓取页面、抽取结构化证据、归并事件簇、构建时间线、多源交叉验证，并生成带引用的事件报告。

这个场景比普通“搜索总结”更适合作为 Agent 项目亮点，因为它有明确的多阶段链路、状态管理、证据结构、引用约束和评测标准。

#### 6.4.1 事件脉络 Agent 的核心链路

主链路可以设计成：

```text
用户输入事件主题
  -> 负责任务规划
  -> 检索候选来源
  -> 抓取页面正文
  -> 抽取结构化证据
  -> 归并事件簇
  -> 构建时间线
  -> 多源交叉验证
  -> 生成带引用报告
```

具体例子：

```text
输入：
请梳理某公司最近一次重大产品故障从首次曝光到官方回应的完整脉络。

任务规划：
- 明确目标：构建带引用的事件时间线，而不是泛泛总结。
- 生成检索 query：公司名 + 故障、官方回应、监管、用户反馈等。
- 确定证据要求：每个事件必须保留 source_url、quote、event_time。
- 确定验证规则：多源支持才标记 supported，单一来源标记 single_source。

输出：
- 事件摘要
- 按时间排序的关键节点
- 每个节点的支持来源
- 不同来源之间的冲突点
- 仍然缺失或无法确认的信息
- 引用列表
```

#### 6.4.2 为什么用 LangGraph

事件脉络任务不是单轮问答，而是一个多阶段、可回退、可验证的工作流。LangGraph 适合用来表达这种状态机：

- 每个节点职责明确，方便调试和替换。
- Graph state 可以保存候选来源、页面正文、证据、事件簇、时间线和报告。
- 可以加入条件分支：来源不足就重新检索，抓取失败就换来源，证据冲突就标记不确定性。
- 可以强制报告生成前经过交叉验证节点，避免模型搜到几篇文章后直接自由发挥。

可以把流程设计成：

```text
ResponsibleTaskPlanner
   |
   v
QueryPlanner
   |
   v
SourceSearch ---- sources not enough ----+
   |                                      |
   v                                      |
PageFetch ---- fetch failed -------------+
   |
   v
EvidenceExtract
   |
   v
EventCluster
   |
   v
TimelineBuilder
   |
   v
CrossValidator ---- weak evidence ------> SourceSearch
   |
   v
ReportWriter
```

#### 6.4.3 LangGraph 节点设计

可以拆成这些节点：

- `ResponsibleTaskPlanner`：先生成可审计任务计划，明确目标、必答问题、检索策略、证据要求、验证规则和安全约束。
- `QueryPlanner`：把任务计划转成具体检索关键词、时间范围、来源偏好和排除条件。
- `SourceSearch`：调用搜索工具，返回候选 URL、标题、摘要、来源类型、初步相关性评分。
- `PageFetch`：抓取页面正文，提取发布时间、作者、站点、正文和可引用片段。
- `EvidenceExtract`：从页面中抽取结构化证据。
- `EventCluster`：把相同或高度相似的证据归并成事件簇。
- `TimelineBuilder`：按事件发生时间排序，构建事件时间线。
- `CrossValidator`：检查每个事件是否有多个来源支持，识别冲突、不确定点和单一来源风险。
- `ReportWriter`：生成带引用的 Markdown 报告。

核心 state 可以这样设计：

```python
class EventTraceState(TypedDict):
    topic: str
    task_plan: TraceTaskPlan
    queries: list[str]
    candidate_sources: list[Source]
    pages: list[Page]
    evidences: list[Evidence]
    event_clusters: list[EventCluster]
    timeline: list[TimelineItem]
    validation_notes: list[ValidationNote]
    report: str
```

结构化证据可以设计成：

```python
class Evidence(TypedDict):
    event_time: str
    actor: str
    action: str
    location: str | None
    claim: str
    source_url: str
    source_title: str
    published_at: str | None
    quote: str
    confidence: float
```

#### 6.4.4 负责任务规划器设计

事件脉络 Agent 不能一上来就搜索。更稳妥的做法是先有一个 `ResponsibleTaskPlanner`，把用户的模糊主题变成一个可执行、可审计的任务计划。

任务计划可以设计成：

```python
class TraceTaskPlan(TypedDict):
    topic: str
    objective: str
    search_queries: list[str]
    required_questions: list[str]
    source_strategy: list[str]
    evidence_requirements: list[str]
    validation_rules: list[str]
    safety_constraints: list[str]
    memory_hints: list[str]
```

当前实现可以升级成“LLM planner + 规则兜底”：

```text
ResponsibleTaskPlanner
  -> 先生成 Rule Plan
       - 根据 topic 生成固定 query 模板
       - 从 EventTraceMemory 召回历史 evidence
       - 把历史 actor / company alias / product name 补进 query
       - 固定生成 required_questions、source_strategy、evidence_requirements、validation_rules、safety_constraints
  -> 如果开启 --llm-plan，再调用 LLM Planner
       - 基于 Rule Plan 补充实体别名、时间范围、更多 query、来源类型
       - 只允许返回 TraceTaskPlan JSON
  -> Schema Validator / Policy Filter
       - 校验 LLM 输出字段
       - 去掉危险、不合规或无关的检索计划
  -> Merge
       - 保留 Rule Plan 的基础 query、证据标准和安全约束
       - 合并 LLM 补充项
       - LLM 失败或输出不合法时直接返回 Rule Plan
```

这样设计的好处是既能利用大模型补充更灵活的检索策略，又不会让模型完全自由规划。规则计划提供稳定底座，LLM 只做增强；如果 LLM 调用失败、超时、返回非 JSON 或字段不合法，系统自动回退到规则计划。

启动方式可以设计成显式开关，避免每次事件追踪都额外消耗模型调用：

```bash
mini-agent trace "某公司产品故障" --llm-plan
```

不开 `--llm-plan` 时，使用纯规则规划器；开启后，走 LLM planner，规则 planner 兜底。

如果要让模型参与判断引用是否支持结论，可以额外开启：

```bash
mini-agent trace "某公司产品故障" --llm-judge
```

`--llm-judge` 只让模型基于 quote 判断 claim 是否被支持，不允许使用外部知识；模型失败或输出不合法时回到规则 judge。

它主要负责：

- 明确任务目标：例如“生成带引用的事件脉络报告”，而不是“总结一下新闻”。
- 拆出必答问题：最早发生了什么、关键参与方是谁、官方回应是什么、哪些点仍有争议。
- 生成检索策略：主题词、别名、官方回应、监管文件、争议来源、时间线关键词。
- 规定证据要求：每条事件必须带 `source_url`、`quote`、`event_time`、`published_at`。
- 规定验证规则：两条以上独立来源才标记 `supported`，单来源标记 `single_source`，来源冲突标记 `conflicted`。
- 规定安全约束：不访问内网地址、不抓私有材料、不把敏感内容写入长期记忆。

规划器和 Memory 的关系：

```text
用户新请求
  -> 读取 Workspace Profile
       - 公司别名
       - 可信来源
       - 黑名单来源
       - watch keywords
  -> 向量召回 Workspace Notes
       - 人工备注
       - 背景说明
  -> 召回 Long-term Evidence Memory
       - 相似事件
       - 历史 evidence
       - 已验证事件簇
  -> 生成 TraceTaskPlan
```

这样 `QueryPlanner` 不再凭空生成 query，而是基于任务计划生成 query。例如长期跟踪某公司时，规划器会把公司别名、产品名、历史争议点和可信来源一起放进搜索策略。

可以在最终报告里保留 `Task Plan` 段：

```text
## Task Plan
- Objective: Build a cited event trace that separates confirmed facts, single-source claims, conflicts, and information gaps.
- Search queries: Acme outage, Acme outage timeline, Acme official response
- Required questions: What happened first? Who responded? Which claims are multi-source?
- Validation rules: supported / single_source / conflicted
```

面试时可以强调：

> 我没有让 Agent 直接搜索和写报告，而是先加了一个负责任务规划器。它默认会先生成规则计划，保证基础 query、证据标准、验证规则和安全约束稳定可测；如果开启 LLM planner，模型只能基于规则计划补充结构化字段，比如实体别名、时间范围、更多 query 和来源类型。LLM 输出必须经过 schema 校验、去重和安全过滤，失败时自动回退到规则计划。报告里也会保留 Task Plan，方便审计 Agent 为什么这么搜、为什么这么判断证据强弱。

#### 6.4.5 工具层设计

和 Mini-Agent 当前工具系统结合，可以扩展这些工具：

- `web_search`：根据 query 检索候选来源。
- `fetch_page`：抓取页面正文和 metadata。
- `extract_evidence`：调用 LLM，把正文抽取成结构化证据。
- `cluster_events`：按时间、主体、动作和语义相似度归并事件。
- `validate_events`：检查事件簇是否有多源支持，识别冲突。
- `write_report`：生成 Markdown 报告，并保留引用链接。

也可以把 LangGraph 看成上层业务编排，把 Mini-Agent 的工具系统作为底层执行能力：

```text
Event Trace LangGraph
   |
   +--> Mini-Agent Tool System
          - web_search
          - fetch_page
          - extract_evidence
          - vector_memory
          - file tools
```

`event_trace` 和普通 `web_search` 的定位不同：

- `web_search` 是信息检索工具，适合快速查资料、拿候选链接、回答轻量问题。它返回搜索结果和摘要，后续如何筛选、交叉验证、组织时间线，主要依赖主 Agent 自己继续推理。
- `event_trace` 是高阶研究工作流，适合“事件脉络、证据链、争议点、带引用报告”这类任务。它内部会规划 query、搜索来源、抓取页面、抽取 evidence、聚类事件、构建时间线、做多源验证，并把 `report.md`、`state.json`、`audit.jsonl` 写到 workspace。

所以二者不是替代关系，而是分层关系：

```text
轻量问题 / 快速概览
  -> web_search
  -> 主 Agent 直接总结

证据型事件研究 / 可追溯报告
  -> event_trace
  -> workflow 生成 evidence + timeline + validation + report
```

实际效果上，`web_search` 可能给出“看起来不错”的事件总结，但它容易出现几个风险：

- 搜索摘要混杂多个页面内容，主 Agent 可能把摘要当成事实。
- 时间线、地名、战役名称容易被模型改写或污染。
- 引用只说明“看过哪些来源”，不一定证明每个结论都被原文支持。
- 没有明确区分 `supported`、`single_source`、`conflicted`、`unsupported`。
- 结果不落盘，后续难以复盘搜索过程和证据链。

`event_trace` 的优势是把这些风险显式工程化处理：

- 每条 evidence 保留 `source_url`、`quote`、`event_time`、`published_at`。
- 每个事件簇会经过引用支持判断和多源验证。
- 单来源、冲突和无支持结论会被标记，而不是混入确定事实。
- 运行过程写入 `.event_trace/runs/<run_id>/`，方便复盘和评测。
- 主 Agent 只接收紧凑摘要和报告路径，避免网页正文污染主上下文。

触发策略可以这样设计：

- 用户只是问“某事件是什么、最近有什么进展”时，优先 `web_search`。
- 用户问“事件脉络、时间线、证据链、争议点、带引用报告、生成 report.md”时，优先 `event_trace`。
- 如果 `event_trace` 返回的报告还不够细，主 Agent 再读取 `report.md` 或 `state.json` 继续加工。

##### `event_trace` 深度研究模式规划

当前 `event_trace` 已经有结构化事件追踪的骨架，但如果要更明确地承担“事件深度研究”任务，应该把能力拆成两种模式：

```text
quick 模式：
  目标：快速生成事件脉络和引用报告
  适用：用户只需要了解大致过程、关键时间线、主要来源
  策略：规则 planner + 搜索/抓取/抽证据/验证/报告

deep 模式：
  目标：生成更接近研究报告的证据型分析
  适用：用户要求深度研究、争议点、多方立场、证据链、可复盘报告
  策略：增强 planner + 多轮 gap search + 来源质量分层 + 争议矩阵 + 深度报告结构
```

工具参数可以增加：

```text
research_depth: "quick" | "deep"
time_range: str | None
focus: list[str] | None
```

其中：

- `research_depth` 控制运行策略和报告结构。
- `time_range` 用于收敛大跨度事件，例如“2022-02 到 2024-12”。
- `focus` 用于约束研究重点，例如“军事阶段、外交谈判、制裁影响、争议事件、各方立场”。

deep 模式的最小可用升级：

1. **默认开启更强规划**
   - `deep` 下默认启用 LLM planner 和 LLM judge。
   - 如果没有 LLM 配置或调用失败，仍然回退规则 planner / rule judge。
   - planner prompt 中加入 `time_range` 和 `focus`，避免大事件被泛泛搜索。

2. **多轮 gap search**
   - 在 `CrossValidator` 后检查信息缺口。
   - 如果没有足够 supported 事件、存在大量 single_source，或必答问题没有覆盖，就追加 gap query。
   - gap query 可以围绕“官方回应、监管/国际组织、关键战役、争议说法、时间范围”生成。

3. **来源质量分层**
   - 给来源增加 `source_type` 或 `source_quality`。
   - 优先级示例：official / primary_document / reputable_media / expert_analysis / social_or_forum / unknown。
   - 报告里说明哪些事件来自官方或权威来源，哪些只是媒体或单来源说法。

4. **争议点矩阵**
   - 对 `conflicted` 和 `single_source` 事件生成单独章节。
   - 每个争议点列出：争议 claim、支持来源、反向来源、当前判断、还缺什么证据。

5. **claim-level citation table**
   - 报告不仅有 timeline，还要有证据表。
   - 表格字段：时间、claim、状态、来源数量、关键 quote、引用编号。

6. **深度报告结构**
   - quick 报告偏 timeline。
   - deep 报告应该包含：

```text
## Executive Summary
## Scope and Method
## Key Timeline
## Phase Analysis
## Evidence Table
## Conflicts and Unverified Claims
## Source Quality Notes
## Open Questions
## References
```

7. **主 Agent 触发策略**
   - 用户只说“事件脉络”：可以先 quick。
   - 用户说“深度研究、证据链、争议点、各方立场、生成研究报告”：走 deep。
   - 用户主题跨度很大，例如“俄乌战争”，如果没有时间范围，deep 模式要先自动按阶段拆分，或在报告中明确 scope。

第一版实现可以先做最小闭环：

- `EventTraceTool` 增加 `research_depth`、`time_range`、`focus` 参数。
- `execute_event_trace()` 接收这些参数。
- `deep` 模式下默认把 `llm_plan` 和 `llm_judge` 视为开启。
- `TraceTaskPlan` 增加 `time_range` / `focus` 对 query 的影响。
- `ReportWriter` 根据 `research_depth` 输出 enhanced report sections。
- 测试覆盖 quick/deep 两种模式，确认 deep 报告包含 evidence table、conflicts/open questions 等章节。

##### 集成到主 Agent：先做 `event_trace` 工具，而不是先做 subagent

当前 `event_trace` 已经不是一个纯脚本，而是有独立 workflow 对象、状态结构、运行目录和审计记录：

- 核心工作流在 `mini_agent/event_trace.py` 的 `EventTraceAgent`。
- CLI 的 `mini-agent trace ...` 只是对这个 workflow 的一层包装。
- 主 Agent 当前已经有统一 `Tool` 抽象和工具调用闭环。
- 工具执行入口集中在 `mini_agent/agent.py`，新增工具不需要改主循环。

所以更适合的第一阶段集成方式是：把事件脉络能力包装成一个主 Agent 可调用的 `EventTraceTool`，而不是先实现完整 subagent 框架。

选择工具方案的原因：

- **复用现有架构成本最低**：Mini-Agent 已经有成熟的 `Tool` 接口、schema 暴露、执行分发和工具结果回填；`event_trace` 只需要包一层工具适配器。
- **保持主 Agent 主循环稳定**：不需要新增 subagent registry、自动委派协议、独立 agent loop、嵌套取消、跨 agent 日志和 token 管理。
- **已经能获得主要隔离收益**：`EventTraceAgent` 内部独立完成搜索、抓取、证据抽取、聚类、验证和报告生成；主会话只接收摘要、验证状态和报告路径，不把大量网页正文和中间证据塞进主上下文。
- **更容易做安全和审计**：事件追踪专属的网络沙箱、workspace 输出路径限制、run recorder、audit.jsonl 可以留在 workflow 内部；工具只返回结构化结果。
- **更容易测试和回归**：可以复用现有 `tests/test_event_trace.py` 和 `tests/test_event_trace_cli.py`，再补一组 `EventTraceTool` 单测，验证主 Agent 能通过工具调用触发完整 workflow。
- **符合当前能力形态**：事件脉络不是一个需要持续对话的通用子 Agent，而是一个专用研究工作流，天然适合做成“高阶工具”。

和 Claude Code subagent 的关系：

Claude Code 里 subagent 是自然方案，因为它已经内建 subagent 注册、独立上下文、工具白名单、权限模式和 hooks。Mini-Agent 当前还没有这些一等基础设施。如果为了 `event_trace` 先补完整 subagent 框架，会把改造范围从“接入一个能力”扩大成“重做一套多 Agent Runtime”。

可以把 `EventTraceTool` 看成当前阶段的轻量委派边界：

```text
主 Agent
  -> 判断用户请求是事件脉络 / 时间线 / 证据链任务
  -> 调用 event_trace 工具
       -> 内部运行 EventTraceAgent workflow
       -> 搜索 / 抓取 / 抽证据 / 聚类 / 验证 / 写报告
       -> 写 workspace/.event_trace/runs/<run_id>/
  -> 工具返回摘要 + 验证状态 + report path + state path
  -> 主 Agent 基于工具结果给用户最终回答
```

###### 实施计划

第一步：新增工具适配器。

新建 `mini_agent/tools/event_trace_tool.py`，实现一个继承 `Tool` 的 `EventTraceTool`：

```python
class EventTraceTool(Tool):
    @property
    def name(self) -> str:
        return "event_trace"

    @property
    def description(self) -> str:
        return (
            "Trace a public event timeline with cited evidence, source validation, "
            "conflict detection, and a Markdown report written inside the workspace."
        )
```

建议参数：

```text
topic: str
sources: list[str] | None
max_sources: int
use_memory: bool
llm_plan: bool
llm_extract: bool
llm_judge: bool
output: str | None
```

其中 `sources` 用于用户已经给出 URL 或本地材料的场景；`output` 必须走 workspace 路径校验；没有 `output` 时默认写到 run 目录里的 `report.md`。

第二步：把 CLI 里的构造逻辑抽成可复用函数。

当前 `run_event_trace()` 里已经包含：

- 读取 config。
- 创建 Tavily search provider。
- 创建 memory。
- 创建 LLM planner / extractor / judge。
- 创建 `EventTraceRunRecorder`。
- 创建并运行 `EventTraceAgent`。
- 写 report 和 state。

这部分不要在工具里复制一遍，建议抽出一个内部函数，例如：

```python
async def execute_event_trace(
    *,
    topic: str,
    workspace_dir: Path,
    sources: list[str] | None = None,
    max_sources: int = 8,
    use_memory: bool = True,
    llm_plan: bool = False,
    llm_extract: bool = False,
    llm_judge: bool = False,
    output: str | None = None,
) -> EventTraceToolResult:
    ...
```

CLI 和 `EventTraceTool.execute()` 都调用这个函数。这样命令行入口和主 Agent 工具入口共享同一套行为，避免后续维护两份逻辑。

第三步：设计工具返回值，控制主上下文大小。

工具不要把完整 `state.json` 或所有 evidence 直接返回给主 Agent，只返回高信号摘要：

```json
{
  "run_id": "20260611T120000Z",
  "report_path": ".event_trace/runs/20260611T120000Z/report.md",
  "state_path": ".event_trace/runs/20260611T120000Z/state.json",
  "timeline_count": 8,
  "supported_count": 5,
  "single_source_count": 2,
  "conflicted_count": 1,
  "summary": "Generated a cited event trace with 8 timeline items..."
}
```

如果用户需要完整证据链，主 Agent 再用 `read_file` 读取 `report.md`，而不是工具一次性返回所有中间材料。

第四步：在工具初始化阶段注册。

在 `mini_agent/config.py` 的 `ToolsConfig` 增加开关：

```python
enable_event_trace: bool = False
```

在 `mini_agent/cli.py` 的 `add_workspace_tools()` 中注册：

```python
if config.tools.enable_event_trace:
    tools.append(
        EventTraceTool(
            workspace_dir=str(workspace_dir),
            config=config,
        )
    )
```

事件追踪需要 workspace 路径、cache、memory、run 目录，所以它应该和文件工具、bash 工具一样放在 workspace-dependent tools 中，而不是 base tools。

第五步：补充 system prompt 提示，让模型知道何时调用。

在系统提示里增加一段简短规则：

```text
When the user asks to reconstruct an event timeline, investigate an incident,
compare sources, build an evidence chain, or produce a cited chronology, prefer
the event_trace tool instead of doing ad hoc web search and summarization.
```

这样模型不会把事件追踪拆成普通 `web_search` + `read_file` 的临时流程，而是优先调用专用高阶工具。

第六步：安全和审计边界。

`EventTraceTool` 内部要保留这些约束：

- URL 抓取继续使用 `NetworkPolicy`，默认阻止 localhost、内网、link-local、reserved address。
- `output`、`report_path`、`state_path` 必须限制在 workspace 内。
- cache、memory、run 目录统一写入 `workspace/.event_trace/`。
- 工具不执行 shell 命令。
- LLM planner / extractor / judge 都必须 schema validate，失败时规则兜底。
- 工具结果里明确标记 `supported`、`single_source`、`conflicted`，不要把单来源结论伪装成确定事实。

第七步：测试。

新增测试重点：

- `EventTraceTool` 用本地 source 文件能跑完整链路。
- 工具返回内容包含 `report_path`、`state_path`、timeline 统计和摘要。
- `output` 写到 workspace 外时拒绝。
- 没有 Tavily key 且没有 sources 时返回 warning，但不崩溃。
- LLM planner / extractor / judge 关闭时仍能规则运行。
- 主 Agent 拿到 fake LLM tool call 后能正确执行 `event_trace` 工具并把结果回填。

第八步：保留 CLI 作为调试和评测入口。

`mini-agent trace ...` 和 `mini-agent trace-eval ...` 继续保留：

- CLI 适合人工调试、离线评测和演示。
- 主 Agent 工具适合自然语言触发和组合任务。
- 两者共享 `execute_event_trace()`，保证行为一致。

最终对外表现：

```text
用户：帮我梳理某公司产品故障事件脉络，要求给引用和争议点。

主 Agent：
  -> 调用 event_trace(topic="某公司产品故障", llm_plan=True, llm_judge=True)
  -> 工具生成 .event_trace/runs/<run_id>/report.md
  -> 主 Agent 回复：
       已生成事件脉络报告
       - supported: ...
       - single_source: ...
       - conflicted: ...
       - 报告路径：...
```

后续如果项目里出现多个类似能力，例如 `code_review_agent`、`security_audit_agent`、`data_analysis_agent`，再抽象真正的 subagent 框架会更自然。那时可以统一设计：

- subagent registry。
- 独立 system prompt。
- 工具 allowlist / denylist。
- 子 agent 上下文窗口。
- hooks 生命周期。
- 权限和审计策略。
- 子 agent 结果压缩协议。

一句话总结：

> 我会先把事件脉络能力做成主 Agent 的高阶工具，而不是直接做 subagent。原因是当前 Mini-Agent 已经有稳定的 Tool 抽象，而 `EventTraceAgent` 本身已经是一个独立 workflow；用工具包装可以低成本接入主 Agent，同时保留上下文隔离、专用安全策略、审计文件和评测能力。等类似独立能力变多之后，再把这些高阶工具背后的共性抽象成真正的 subagent runtime。

#### 6.4.6 Memory 系统设计

事件脉络 Agent 需要的不只是“聊天记忆”，而是面向证据和事件的检索式 memory。可以分成三层：

```text
Run Memory
  当前任务内状态，放在 LangGraph state 里

Workspace Memory
  同一项目或同一主题下可复用的来源、事件簇、实体别名、已验证事实

Long-term Evidence Memory
  跨任务沉淀的结构化证据和向量索引
```

##### Run Memory

Run Memory 只服务当前一次事件梳理，主要存在 LangGraph state 里：

- 当前查询主题。
- 已生成的搜索 query。
- 已抓取页面。
- 已抽取证据。
- 已归并事件簇。
- 交叉验证结果。
- 报告草稿。

它的目标是让工作流可恢复、可调试、可回放。

##### Workspace Memory

Workspace Memory 解决同一主题反复分析时的复用问题。例如长期跟踪某公司、某政策或某地区事件，可以记录：

- 高可信来源列表。
- 低质量或重复来源黑名单。
- 实体别名，例如公司简称、产品名、人物名。
- 已确认的关键时间点。
- 之前报告中已经验证过的事件簇。

这样下次分析相近主题时，`QueryPlanner` 可以先从 memory 里召回实体别名和可信来源，`SourceSearch` 也可以优先检索这些来源。
Workspace Memory 是配置型数据，不适合只靠向量召回。

  比如：

  {
    "company": "Acme",
    "aliases": ["Acme Inc.", "ACME", "Acme Cloud"],
    "trusted_sources": ["sec.gov", "acme.com/newsroom"],
    "blocked_sources": ["content-farm.example"],
    "watch_keywords": ["outage", "recall", "lawsuit"]
  }

Workspace Memory 存项目级上下文，比如公司别名、可信来源、黑名单和人工偏好，其中结构化 profile 用精确读取，文本备注才做向量召回。Long-term Evidence Memory 存历史证据和事件簇，用结构化库保证可追溯，用向量索引用来召回相似事件。新请求进来时，QueryPlanner 会先读取 workspace profile，再向量召回 workspace notes 和 historical evidence，最后生成更有针对性的检索 query。

##### Long-term Evidence Memory

长期记忆更适合用“结构化存储 + 向量检索”的组合：

```text
SQLite / JSONL
  存 evidence_id、topic、event_time、actor、claim、source_url、quote、confidence

Vector Store
  存 claim + quote + source_title 的 embedding
  支持按语义召回相似事件和历史证据
```

写入时机：

- `EvidenceExtract` 后写入候选证据，但标记为 `unverified`。
- `CrossValidator` 后更新证据状态为 `supported`、`conflicted` 或 `single_source`。
- `ReportWriter` 后把最终事件簇和引用关系沉淀为可复用记忆。

召回时机：

- `QueryPlanner` 召回历史相关主题和实体别名。
- `EvidenceExtract` 召回相似证据，帮助判断是不是旧事件重复报道。
- `EventCluster` 召回历史事件簇，避免重复建簇。
- `CrossValidator` 召回历史支持来源，辅助多源验证。

关键原则：

- 记忆里必须保存来源 URL 和原文片段，不能只保存模型总结。
- 证据要区分 `event_time` 和 `published_at`，避免把报道时间误认为事件发生时间。
- 记忆要带 workspace/topic 过滤，避免不同事件之间互相污染。
- 被判定为冲突或低可信的证据不要删除，而是带状态保存，方便后续解释争议来源。

#### 6.4.7 能力分层和当前缺口

事件脉络 Agent 可以按 LLM、Runtime、Harness 三层来拆能力。这样面试时能说清楚：哪些已经是基础可运行能力，哪些是后续升级方向。

##### LLM 能力

基础能力：

- `LLM Planner`：基于规则计划补充实体别名、时间范围、更多 query 和来源类型。
- `Rule Planner Fallback`：LLM 失败、超时、返回非法 JSON 时回退规则计划。
- `LLM Evidence Extractor`：从页面正文抽取 `event_time`、`actor`、`claim`、`quote`、`confidence`。
- `LLM Judge`：只基于 quote 判断 claim 是否被支持，评估 citation faithfulness；默认有规则兜底。
- `Conflict Detector`：在多源证据中识别确认/否认、上涨/下跌、中断/恢复等相反信号；默认先用规则检测。
- `Schema Validation`：LLM planner 和 evidence extractor 的输出都要经过结构化校验，字段不合法就跳过或降级。

升级能力：

- `LLM Report Writer`：用 LLM 生成更自然的报告，但必须只基于 evidence 写，不能自由补事实。
- `Prompt Regression`：固定一批样本，评估 prompt 或模型升级后是否引入更多 unsupported claim。

##### Runtime 能力

基础能力：

- LangGraph 工作流编排：规划、搜索、抓取、抽取、聚类、时间线、交叉验证、报告生成。
- 网络沙箱：抓取页面前拦截 localhost、内网地址、link-local、metadata 等非公开网络目标。
- 页面缓存：抓取成功的页面缓存到 workspace 下，便于复现、减少重复请求。
- 超时和大小限制：搜索和抓取要有 timeout，页面响应大小要有限制。
- Memory 写入：把 evidence 以 JSONL 形式沉淀，并保留 source_url、quote、验证状态。
- Run 目录：每次运行生成 `run_id`，持久化 `state.json`、`report.md` 和 `audit.jsonl`。
- 审计日志：记录每个节点耗时、输入输出数量和失败原因，方便复盘。
- Workspace 路径沙箱：`--output`、`--json`、cache、memory 和 run 目录都限制在 workspace 内。

升级能力：

- LangGraph state 持久化：长任务中断后可以恢复，而不是从头跑。
- 节点级 retry/rate limit：搜索、抓取、LLM 抽取分别配置重试和限流。
- 可观测性：记录每个节点耗时、输入输出数量、失败原因、LLM token 使用量。
- 恢复执行：从已有 `state.json` 继续运行未完成的 LangGraph 节点。

运行目录可以设计成：

```text
workspace/.event_trace/runs/<run_id>/
  state.json
  report.md
  audit.jsonl
```

其中：

- `state.json` 保存当前 Graph state，方便复盘和后续恢复。
- `report.md` 保存最终事件报告。
- `audit.jsonl` 按节点记录运行事件，例如节点名、耗时、输入输出数量和错误信息。

用户显式传入输出文件时也要走 workspace 沙箱：

```bash
mini-agent trace "某公司事件" --output reports/event.md --json reports/state.json
```

相对路径会解析到 workspace 内；绝对路径必须仍然位于 workspace 下，否则拒绝写入。

##### Harness / Eval 能力

基础能力：

- 单元测试：验证本地来源能跑完整链路。
- Planner 测试：验证 LLM planner 能合并规则计划，坏 JSON 能回退规则计划。
- Fetcher 测试：验证网络沙箱能阻止内网目标，缓存能复用页面。
- Schema 测试：验证 LLM 输出非法字段时不会污染 evidence。
- Eval Harness：基于封闭集 state 计算 `citation_coverage`、`unsupported_claim_rate`、`required_event_recall`。

升级能力：

- 封闭集 Eval：准备本地 HTML / 文本快照和 gold timeline，保证 CI 稳定。
- 节点评测：分别评 `SourceSearch`、`PageFetch`、`EvidenceExtract`、`EventCluster`、`TimelineBuilder`、`CrossValidator`。
- 引用忠实度评测：重点看 `citation_coverage`、`citation_faithfulness`、`unsupported_claim_rate`。
- 回归 Benchmark：每次改 prompt、模型、schema、搜索策略后跑同一批样本，防止效果退化。

一句话总结：

> LLM 负责更聪明地规划、抽取和判断；Runtime 负责安全稳定地跑完整条链路；Harness 负责证明这条链路真的可靠。基础能力先保证能运行、可追溯、可降级，升级能力再提升判断质量、恢复能力和系统化评测。

#### 6.4.8 评测系统设计

这个业务场景的评测不能只看“回答是否流畅”，而要评测整条证据链。可以做一个 Eval Harness，输入固定事件主题和参考资料，驱动 LangGraph 跑完整流程，然后从多个维度打分。

##### 评测数据集

可以准备两类数据：

- 封闭集：给定一组固定网页快照或本地 HTML，评测结果稳定，适合 CI。
- 开放集：允许实时搜索，评测真实可用性，但结果会随互联网变化，适合人工验收或定期 benchmark。

每条样本包含：

```text
topic
sources
reference_sources
gold_timeline
required_events
known_conflicts
expected_citations
```

可以把封闭集样本保存成 JSON：

```json
{
  "topic": "Acme outage",
  "sources": ["source_a.html", "source_b.html"],
  "required_events": ["Acme reported outage"],
  "expected_citations": ["source_a.html"]
}
```

然后用 CLI 跑完整 eval：

```bash
mini-agent trace-eval cases/acme_outage.json --output eval/acme_result.json
```

`trace-eval` 会读取本地 sources，运行完整事件脉络 Agent，然后输出 `citation_coverage`、`unsupported_claim_rate`、`required_event_recall` 等指标。相对 source 路径按 case 文件所在目录解析，输出路径仍然受 workspace 沙箱限制。

##### 节点评测

按节点分别评测，比只评最终报告更容易定位问题：

- `SourceSearch`：候选来源相关性、来源多样性、权威来源覆盖率。
- `PageFetch`：抓取成功率、正文提取完整度、发布时间提取准确率。
- `EvidenceExtract`：事件时间、主体、动作、claim、quote 的抽取准确率。
- `EventCluster`：重复事件合并准确率，错误合并率。
- `TimelineBuilder`：时间顺序准确率，关键事件召回率。
- `CrossValidator`：多源支持判断准确率，冲突识别准确率。
- `ReportWriter`：引用完整性、事实忠实度、是否区分确定事实和不确定信息。

##### 核心指标

可以定义这些指标：

- `source_precision`：候选来源里相关来源占比。
- `source_diversity`：不同站点、不同类型来源的覆盖情况。
- `evidence_f1`：结构化证据抽取的准确率和召回率。
- `timeline_order_accuracy`：时间线排序是否正确。
- `required_event_recall`：标准关键事件是否被覆盖。
- `citation_coverage`：报告中的关键结论是否都有引用。
- `citation_faithfulness`：引用是否真的支持对应结论。
- `conflict_detection_recall`：已知冲突点是否被识别。
- `unsupported_claim_rate`：没有来源支撑的结论占比，越低越好。

其中最重要的是 `citation_faithfulness` 和 `unsupported_claim_rate`，因为事件脉络报告最怕“看起来完整，但引用不支持结论”。

##### 自动评测方式

可以组合三种评测：

- 规则评测：检查每条时间线是否有 source_url，是否包含 quote，时间格式是否可解析。
- Gold 对齐：把输出事件和 gold timeline 做语义匹配，计算关键事件召回和时间顺序准确率。
- LLM Judge：让评审模型只基于引用片段判断 claim 是否被支持，避免凭常识打分。

LLM Judge 的提示词要限制得很窄：

```text
只根据给定 quote 判断 claim 是否被支持。
如果 quote 没有直接支持 claim，输出 unsupported。
不要使用外部知识。
```

##### 回归测试

每次改模型、prompt、搜索策略或抽取 schema 后，跑同一批封闭集样本，比较：

- 关键事件召回是否下降。
- unsupported claim 是否上升。
- 抓取失败率是否上升。
- 报告引用是否丢失。
- 平均工具调用次数和耗时是否异常增加。

这样这个业务场景就不只是 Demo，而是有可持续迭代的工程闭环。

##### 面试讲法

> 我会把事件脉络 Agent 做成 LangGraph 工作流，而不是让模型一次性搜索总结。Graph 里每个节点都有明确状态输入输出：检索来源、抓页面、抽证据、聚类事件、构建时间线、交叉验证、写报告。Memory 也不是简单聊天历史，而是分成当前任务 state、workspace 级主题记忆和长期 evidence memory，证据必须带来源 URL、原文 quote 和验证状态。评测上我会做 Eval Harness，既评最终报告，也评每个节点，重点看 citation faithfulness、unsupported claim rate、关键事件召回和时间线顺序准确率。这样它就从一个演示型 Agent 变成了一个可以迭代和验收的业务系统。

## 7. 可能被追问的问题

### 7.1 为什么要抽象 LLM Provider？

因为 Anthropic/OpenAI 协议消息结构和工具调用格式不同。

抽象后，Agent 主循环不依赖具体协议，切换模型供应商时主要改适配层。

### 7.2 为什么需要 message summary？

Agent 执行真实任务会产生大量工具结果，直接保留会超上下文。

摘要可以保留阶段性结果，降低 token 成本。

### 7.3 MCP 和普通工具有什么区别？

普通工具是本地 Python 类。

MCP 是外部 server 暴露工具，Agent 通过协议动态发现和调用。

MCP 的优势是扩展性强，可以接知识库、网页搜索、数据库、企业内部系统等外部能力。

### 7.4 Skill 为什么按需加载？

Skill 内容很长，全部放入 system prompt 会浪费上下文。

先暴露 metadata，需要时再加载完整指导，可以降低上下文成本。

### 7.5 当前项目不足是什么？

可以诚实说：

- 安全沙箱还不够强
  - 沙箱是一套隔离运行环境，把程序、代码、进程、用户操作限制在独立封闭空间内运行
  - 沙箱不是只靠 prompt 约束模型，而是放在 Runtime 和 Tool 执行层。文件操作限制在 workspace，bash 命令有 allowlist/denylist 和危险确认，网页抓取有网络访问边界，memory 按 workspace/company 隔离。
- 记忆只是 JSON，不支持语义检索
- 工具权限控制较弱
- 没有复杂任务规划器
- 多 Agent 协作还没做

这个回答能体现你真的理解项目边界。

## 8. 推荐面试叙事

可以这样讲：

> 我复现并扩展了一个 Mini Agent Runtime。最开始我关注的是 Agent 的核心闭环：LLM 如何选择工具、工具结果如何回填、什么时候停止。之后我把它拆成三层：LLM 协议适配层、Agent 执行层、工具扩展层。为了让它能处理真实工程任务，我加入/研究了长上下文摘要、后台 Shell 管理、MCP 动态工具接入、Skills 渐进式加载和完整日志。我的后续改造重点是安全沙箱、结构化长期记忆，以及用 LangGraph 编排“事件脉络 Agent”：从检索来源、抽取证据、构建时间线到多源验证和带引用报告生成。

## 9. 简历写法

### 项目名称

Mini-Agent Runtime 与事件脉络研究工作流

### 项目背景

面向复杂工程任务和信息分析任务，传统单轮 LLM 问答缺少工具调用闭环、上下文管理、安全边界、证据追踪和可评测能力。项目基于 Mini-Agent 构建轻量级 Agent Runtime，支持多轮 LLM 工具调用、Provider 协议适配、MCP/Skills 扩展、记忆系统和执行日志；并在此基础上实现 `event_trace` 事件脉络研究工作流，用于自动规划检索、抓取来源、抽取证据、构建时间线、多源验证并生成带引用报告。

### 主要工作

- 设计 Agent Runtime 主循环，支持 LLM 多轮推理、工具调用解析、工具执行、结果回填、最大步数控制、取消清理、执行日志和 token usage 跟踪。
- 实现消息历史管理与长上下文压缩：维护 system/user/assistant/tool 消息链路，保留 thinking/tool_calls/tool_result；基于本地 token 估算和 API usage 触发执行过程摘要，避免长任务上下文溢出。
- 抽象统一 LLM Provider 层，兼容 Anthropic / OpenAI 风格协议，统一处理 message、thinking/reasoning、tool calls、finish reason 和 token usage。
- 扩展工具系统，接入文件读写、Shell 前后台执行、Web Search、MCP 工具、Claude Skills 渐进式加载、session memory 和 vector memory。
- 将事件脉络能力封装为主 Agent 可调用的 `event_trace` 高阶工具，并增加事件脉络 / 时间线 / 证据链请求的自动路由，避免模型绕过专用工作流直接做普通搜索总结。
- 基于 LangGraph 风格状态机实现 `EventTraceAgent`，编排 Planner、SourceSearch、PageFetch、EvidenceExtract、EventCluster、TimelineBuilder、CrossValidator、ReportWriter 等节点。
- 设计 LLM Planner + 规则兜底机制，生成检索 query、来源策略、证据要求和验证规则；对 LLM 输出做 schema 校验，失败时回退规则抽取和规则判断。
- 实现结构化证据模型，保存 `event_time`、`actor`、`claim`、`source_url`、`quote`、`confidence`、`validation_status`，支持事件聚类、引用忠实度判断、冲突检测和多源交叉验证。
- 增强安全与可观测性：实现网络沙箱、workspace 输出路径沙箱、页面大小限制、页面缓存、run 目录、`state.json`、`report.md`、`audit.jsonl` 和节点级运行记录；兼容代理 fake-ip 场景，同时继续拦截直接内网/保留地址访问。
- 构建 `trace-eval` 评测入口和封闭集 Eval Harness，支持本地 sources 回放，评估 `citation_coverage`、`unsupported_claim_rate`、`required_event_recall`、时间线顺序和引用忠实度等指标。

### 项目收益

- 将普通 LLM 问答升级为可执行、可追踪、可评测的 Agent Runtime，提升复杂任务处理的稳定性和工程可控性。
- 通过专用 `event_trace` 工作流替代一次性搜索总结，降低长链路研究任务中的幻觉和无引用结论风险。
- 通过结构化 evidence、原文 quote、source URL 和 validation status，提高事件报告的可追溯性和可审计性。
- 通过 LLM + 规则兜底的混合设计，在保留语义理解能力的同时提升系统稳定性、可测试性和失败可恢复性。
- 通过网络沙箱、workspace 沙箱、运行目录和 audit 日志，让 Agent 的外部访问、文件输出和研究过程具备明确边界。
- 通过 Eval Harness 和固定样本回归，把 Agent 输出从“看起来合理”转为可用指标持续评估。

### 简历精简版

```text
Mini-Agent Runtime 与事件脉络研究工作流
- 构建轻量级 Agent Runtime，支持多轮 LLM 工具调用、消息历史管理、长上下文摘要、取消清理、执行日志和 token usage 跟踪。
- 抽象统一 LLM Provider 与工具系统，兼容 Anthropic/OpenAI 协议，接入文件、Shell、Web Search、MCP、Skills、session/vector memory 等能力。
- 将事件脉络研究封装为 `event_trace` 高阶工具，支持事件脉络/时间线/证据链请求自动路由，避免模型绕过专用工作流直接搜索总结。
- 基于 LangGraph 风格状态机实现事件研究工作流，编排检索规划、来源搜索、页面抓取、证据抽取、事件聚类、时间线生成、多源验证和带引用报告输出。
- 设计结构化 evidence 模型和 LLM + 规则兜底机制，保留 source_url、quote、event_time、validation_status，支持引用忠实度判断、冲突检测和失败回退。
- 增强安全与可观测性，实现网络沙箱、workspace 输出沙箱、页面缓存、run state/report/audit 持久化，并兼容代理 fake-ip 网络环境。
- 构建 `trace-eval` 封闭集评测入口，评估 citation_coverage、unsupported_claim_rate、required_event_recall、时间线顺序和引用忠实度，支撑回归测试。
```

### 更适合简历的一段式描述

> 复现并扩展 Mini-Agent Runtime，设计多轮 LLM 工具调用闭环、消息历史管理、长上下文摘要、取消清理、Provider 协议适配和可扩展工具系统；在此基础上实现 `event_trace` 事件脉络研究工作流，通过 LangGraph 风格状态机编排检索规划、来源搜索、页面抓取、结构化证据抽取、事件聚类、多源验证和带引用报告生成，并补充网络沙箱、workspace 输出沙箱、run state/audit 持久化和 `trace-eval` 回归评测，提升 Agent 在复杂信息分析任务中的可追溯性、稳定性和可评测性。

## 10. 面试时不要这样说

避免说：

- “这是我完全从零写的项目”
- “这个 Agent 有自主意识”
- “MCP 就是插件”
- “记忆系统很智能”
- “可以无限上下文”

更专业的说法：

- “我复现并改造了这个 Agent Runtime”
- “它通过工具调用闭环完成任务执行”
- “MCP 是一种外部工具协议”
- “当前记忆是轻量 JSON notes，后续可以升级为检索式记忆”
- “通过摘要机制支持长任务，而不是物理意义上的无限上下文”

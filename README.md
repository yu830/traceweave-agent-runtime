# TraceWeave Agent Runtime

TraceWeave 是一个从零实现的最小可用 Agent Runtime。项目主体是 Python 包 `traceweave_agent_runtime`，提供终端 CLI 和本地网页对话界面。网页只是薄 UI，底层仍然调用同一个自研 `AgentRuntime.run_turn(...)` 循环。

项目没有使用 LangGraph、OpenHands、OpenClaw、LangChain Agent Executor、AutoGen、CrewAI 或 LlamaIndex Agent Runtime 作为主流程。核心 Agent Runtime 的循环、工具协议、输出解析、工具注册、session 存储、context 构造、压缩和 trace 都在本仓库内自行实现。

演示视频: [docs/demo/traceweave-web-demo.mp4](docs/demo/traceweave-web-demo.mp4)

## 索引

- [一、快速运行](#一快速运行)
- [二、真实 LLM API 配置](#二真实-llm-api-配置)
- [三、系统设计](#三系统设计)
- [四、工具注册与 Agent Loop](#四工具注册与-agent-loop)
- [五、Session、Context 与 Memory](#五sessioncontext-与-memory)
- [六、Trace 与异常处理](#六trace-与异常处理)
- [七、测试用例](#七测试用例)
- [八、AI Prompt 与问题解决记录](#八ai-prompt-与问题解决记录)
- [九、架构设计题完整回答](#九架构设计题完整回答)
- [十、参考资料](#十参考资料)

## 一、快速运行

### 1. 安装依赖

Windows PowerShell:

```powershell
git clone https://github.com/yu830/traceweave-agent-runtime.git
cd traceweave-agent-runtime
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Python 版本要求: 3.11 或更新。

### 2. 初始化数据库

```powershell
traceweave init-db
```

### 3. 终端对话

```powershell
traceweave chat --user-id alice --session-id weather --message "查一下上海明天的天气，并记一个待办：明天带伞。"
traceweave list-todos --user-id alice --session-id weather
traceweave show-messages --user-id alice --session-id weather
traceweave show-traces --user-id alice --session-id weather
```

### 4. 本地网页界面

```powershell
traceweave serve --host 127.0.0.1 --port 8787
```

浏览器打开:

```text
http://127.0.0.1:8787
```

## 二、真实 LLM API 配置

项目运行时使用 OpenAI-compatible LLM API。公开仓库不保存明文密钥，真实 key 通过 `.env` 或系统环境变量注入。

复制 `.env.example` 为 `.env`，填入真实 API key:

```env
OPENAI_API_KEY=<your-real-api-key>
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_MODEL=qwen/qwen3-next-80b-a3b-instruct
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_TOKENS=2048
OPENAI_TEMPERATURE=0

TRACEWEAVE_DB_PATH=.traceweave/traceweave.sqlite3
SEARCH_PROVIDER=mock
RUN_LLM_TESTS=1
```

`.env` 已被 `.gitignore` 排除，仓库只保留非敏感配置模板。上面的 endpoint 和模型名可公开；API key 不应出现在 README、提交历史或 issue 中。

## 三、系统设计

```text
CLI / Web UI / Tests / Examples
        |
        v
AgentRuntime.run_turn(user_id, session_id, user_input)
        |
        +--> SQLiteStore: sessions, messages, todos, summaries, traces
        +--> ContextBuilder: system policy, tool schemas, summary, todos, recent messages
        +--> LLM Adapter: OpenAI-compatible API or FakeLLM
        +--> ActionParser: JSON extraction and Pydantic validation
        +--> ToolRegistry: JSON Schema validation and handler execution
        +--> TraceLogger: llm_request, llm_response, tool_call, tool_result, errors
```

关键边界:

- `runtime/agent_runtime.py`: 自研 Agent Loop。
- `runtime/parser.py`: LLM JSON Action Protocol 解析。
- `runtime/actions.py`: `tool_call` 与 `final_answer` 的结构约束。
- `tools/registry.py`: 工具注册、JSON Schema 校验、执行和错误捕获。
- `store/sqlite_store.py`: session、消息、待办、summary、trace 持久化。
- `runtime/context_builder.py`: 构造每次 LLM 调用的 context。
- `runtime/compression.py`: 基础确定性压缩。
- `web_app.py`: 本地网页 UI，复用同一个 runtime。

## 四、工具注册与 Agent Loop

### Agent Loop

`AgentRuntime.run_turn(...)` 的主流程:

1. 接收用户输入并写入 `messages`。
2. 构造 context: system policy、工具 schema、summary、open todos、recent messages、本轮 tool results、当前用户消息。
3. 调用真实 LLM API 或测试用 FakeLLM。
4. 解析 LLM 输出:
   - `tool_call`: 执行工具，把工具结果摘要放回下一步 context。
   - `final_answer`: 写入 assistant message 并返回用户。
5. 如果超过 `max_steps`，记录 `max_steps_reached` 并返回可解释错误。

### JSON Action Protocol

模型必须返回一个 JSON 对象:

```json
{
  "action": "tool_call",
  "reasoning_summary": "需要查询天气并记录待办",
  "tool_call": {"name": "weather", "arguments": {"location": "上海"}},
  "final_answer": null
}
```

或者:

```json
{
  "action": "final_answer",
  "reasoning_summary": "工具结果已齐全",
  "tool_call": null,
  "final_answer": "上海明天的天气是30°C，多云。已为您添加待办：明天带伞。"
}
```

项目只保存 `reasoning_summary`，不要求或保存完整 chain-of-thought。

### 工具列表

| 工具 | 用途 | 说明 |
| --- | --- | --- |
| `calculator` | 安全算术计算 | 使用 AST 白名单，不使用 `eval` |
| `search` | 搜索 | 默认 mock，支持可选真实 endpoint |
| `todo` | session 级待办 | add/list/complete/update |
| `weather` | 天气查询 | deterministic mock，便于稳定测试与演示 |
| `read_docs` | 读取项目文档 | 限制在 `docs/` 和 `examples/sample_docs/` |
| `datetime` | 当前时间 | 支持 IANA timezone |
| `note` | session 级笔记 | add/list |

每个工具都包含:

- `name`
- `description`
- `parameters_schema`
- `handler`
- `is_read_only`
- `timeout_seconds`

## 五、Session、Context 与 Memory

### Session 隔离

所有持久化记录都包含 `user_id` 与 `session_id`。查询 messages、todos、summaries、notes、traces 时都会同时过滤这两个字段。

例子:

- `alice/weather`: 查天气、记带伞待办。
- `alice/weekly`: 写周报、记提交周报待办。
- 两个 session 共享数据库，但状态互不污染。

### Context 放置顺序

每次 LLM 请求按如下顺序构造:

1. System Prompt
2. Runtime Policy
3. Tool Schema Block
4. Relevant Memory Block
5. Session Summary Block
6. Open Todos Block
7. Recent Messages Block
8. Tool Results Block
9. Current User Message

### Memory 的召回时机与放置方式

本项目实现的是 session memory，而不是完整长期向量记忆系统。

召回时机:

- 每次 `run_turn` 调 LLM 前召回。
- 压缩触发时先更新 summary，再进入新的 LLM 请求。
- 工具执行后，下一步 loop 立即把本轮工具结果摘要放回 context。

召回内容:

- 最近未压缩消息。
- 最新 session summary。
- 当前 session 的 open todos。
- 本轮已执行工具结果摘要。
- `Relevant Memory Block` 预留给未来长期语义记忆。

放置方式:

- summary、todos、recent messages、tool results 放在当前用户消息之前。
- 完整 trace 和完整工具 payload 不直接塞入 prompt，只进入 SQLite trace 表，避免 context 过长。

### Context 压缩

`DeterministicCompressor` 会在消息数量或 token 估算超过阈值时:

1. 保留最近 N 条消息。
2. 把更早的未压缩消息写成 summary。
3. 标记旧消息为 summarized。
4. 保留结构化状态，比如 open todos，不只依赖自然语言摘要。

演示:

```powershell
python examples\demo_context_compression.py
traceweave compress --user-id alice --session-id weather
```

## 六、Trace 与异常处理

Trace 存储在 `tool_traces` 表，可通过 CLI 或 Web UI 查看。

记录事件:

- `llm_request`
- `llm_response`
- `parser_error`
- `tool_call`
- `tool_result`
- `tool_error`
- `final_answer`
- `max_steps_reached`
- `compression`

异常处理:

- LLM API 异常会被包装为 `LLMAPIError`。
- LLM JSON 解析失败会返回可读错误并写 trace。
- 工具参数不符合 schema 会返回 `ToolArgumentValidationError`。
- 工具内部错误会被捕获为 `ToolExecutionError`。
- 无限工具循环由 `max_steps` 截断。

## 七、测试用例

运行:

```powershell
python -m pytest
```

测试覆盖:

- parser 能解析 `tool_call` 与 `final_answer`。
- 工具注册、重复注册、JSON Schema 校验。
- calculator 安全计算与危险表达式拒绝。
- todo 增删改查与 session 隔离。
- search mock fallback。
- agent loop: direct answer、tool call then final、max steps、tool error。
- context builder 包含 schema、summary、recent messages、tool results。
- compression 触发与 open todos 保留。
- trace logger 写入。
- web API 复用 runtime。
- 真实 LLM 集成测试由 `RUN_LLM_TESTS=1` 和真实 API 配置控制。

## 八、AI Prompt 与问题解决记录

完整记录见 `docs/ai_prompts_and_issue_log.md`。本项目使用 AI 作为工程辅助工具，但核心 Agent Runtime 的边界、取舍、测试和安全策略由人工审查确认。

### 使用原则

- AI 用于辅助设计、代码生成、测试补充和审查，不替代人工判断。
- 核心 Agent Runtime 边界由人工确定: parser、tool registry、store、context builder、compression、trace、CLI/Web UI。
- 主流程不依赖 LangGraph、OpenHands、OpenClaw 等现有 Agent 框架。
- 测试结果必须来自真实命令输出。
- 真实 LLM API 通过 `.env` 或环境变量配置，不把 API key 写入仓库。

### 关键 Prompt 方向

1. 从零实现最小可用 Agent Runtime: 产出 `AgentRuntime.run_turn(...)`、`ActionParser`、`ToolRegistry`、`SQLiteStore`、`ContextBuilder` 和 `TraceLogger`。
2. 设计 provider-neutral JSON Action Protocol: 不依赖单一厂商的 native function calling，由 runtime 自行解析、校验和执行工具。
3. 实现工具系统: 支持 calculator、search、todo、weather、read_docs 等工具，并为每个工具提供名称、描述和参数 schema。
4. 实现 session 隔离: 所有 messages、todos、summaries、notes、traces 都按 `user_id + session_id` 过滤。
5. 实现 context 管理与压缩: 最近消息保留原文，旧消息写入 summary，open todos 作为结构化状态单独注入。
6. 加入本地 Web UI: 作为 CLI 之外的交互界面，但不改变底层 runtime 主流程。

### 关键问题与修复

- 工具循环重复调用: 将本轮 tool result summaries 放入下一步 context，并在 runtime policy 中要求工具完成后返回 `final_answer`。
- LLM 输出格式不稳定: 使用 JSON Action Protocol + Pydantic 校验，解析失败写入 trace 并返回可读错误。
- calculator 安全风险: 使用 AST 白名单，不使用 `eval`。
- read_docs 路径风险: 限制读取范围，避免路径穿越。
- session 数据串扰: SQLite 查询统一按 `user_id + session_id` 过滤，并添加 session 隔离测试。
- API 超时: 增加 timeout、max tokens、temperature 配置，并切换到更稳定的 OpenAI-compatible Qwen 模型。

## 九、架构设计题完整回答

### 模块一: Context / Performance

#### 1. 第一轮长窗口或多模态输入导致 first token 变慢，如何低成本从 5-10 秒压到 2 秒？

目标不是让模型 2 秒内完成完整深度理解，而是让用户 2 秒内看到可信的第一响应，同时把重处理移到后台或提前完成。

方案:

1. 输入预处理前移: 文件上传、OCR、音视频抽帧、PDF 分段、embedding、摘要在用户点击发送前或上传后立即异步做。
2. 首屏快速响应: 第一轮先返回“已收到，我正在解析 N 个文件/图片”，同时展示解析进度；不要等全量 context 处理完才输出第一个 token。
3. 分层摘要: 多模态和长文档先变成结构化摘要、目录、关键实体、待查证问题，再把少量高价值内容给主模型。
4. 缓存与复用: 对相同文件 hash、图片 hash、embedding、OCR 结果、chunk summary 做缓存。
5. 模型分工: 用小模型或规则先做路由和粗摘要，大模型只处理必要片段。
6. Prompt 缩短: 第一轮只放任务、约束、索引和最高相关片段，完整原文放到可检索存储。
7. 流式输出: 即使后端还在处理，也先流出状态、计划和已完成解析结果。

权衡:

- 优点: 成本低，用户体验明显改善。
- 风险: 过早回答可能遗漏细节，所以第一响应要明确是“正在解析”，最终答案必须在后台解析完成后更新。

#### 2. 一个 session 连续聊了 200 轮，context 快爆了，如何压缩并保持流畅？

我会用分层压缩，不把所有历史揉成一段不可追溯摘要。

上下文层级:

1. 最近窗口: 最近 8-20 轮原文保留。
2. Session summary: 更早对话压缩成目标、结论、未完成事项、用户偏好、关键事实。
3. 结构化状态: todos、notes、决策、文件引用、工具结果索引单独存表。
4. Trace 外置: 完整工具结果和 LLM 请求不塞回 prompt，只在需要审计或追问时检索。
5. 可回溯引用: summary 记录覆盖的 message id 范围。

压缩流程:

1. 每轮写入消息后估算 token 和未压缩消息数。
2. 超阈值时选取旧消息压缩，保留最新 N 条。
3. 生成或更新 session summary。
4. 标记旧消息 summarized。
5. 下次 context 使用 summary + open todos + recent messages + 当前工具结果。

流畅性保证:

- 用户刚提到的内容必须保留原文。
- 任务状态必须结构化，不只靠自然语言摘要。
- 压缩摘要要包含“已完成、未完成、用户偏好、待确认问题”。
- 如果用户追问旧细节，先用 summary 判断，再按 message id 或 trace 检索原文。

### 模块二: Memory

#### 1. 用户半个月后问以前问过的问题，Agent 如何做 memory 召回更合理？

不要把半个月所有聊天都塞进 prompt，而是做“意图识别 + 候选召回 + 过滤 + 带来源注入”。

流程:

1. 判断当前问题是否需要历史记忆: 是否出现“上次、之前、我以前、那个方案”等信号。
2. 召回候选: 同时查结构化 memory、session summaries、语义向量、关键词索引。
3. 过滤: 按 user_id、时间、相似度、置信度、是否过期、是否与当前任务冲突过滤。
4. 注入: 只把 3-8 条短 memory snippets 放入 Relevant Memory Block，并带来源和时间。
5. 不确定时说明: 如果记忆可能过期，回答时说“我记得之前是 X，但可能需要重新确认”。
6. 更新: 如果用户纠正记忆，写入新 memory 并降低旧 memory 置信度。

关键点:

- 稳定偏好可以长期保留。
- 临时事实要设置过期策略。
- 用户要能查看、删除、禁用记忆。

#### 2. Agent memory 经典框架是什么？趋势是什么，头部玩家怎么做？

经典框架可以分为四层:

1. Working memory: 当前轮和短期上下文，放在 prompt 里。
2. Episodic memory: 会话片段、事件、历史任务摘要，适合语义检索。
3. Semantic memory: 用户偏好、长期事实、实体关系、项目知识。
4. Procedural memory: 用户喜欢的工作流、工具策略、输出格式、操作习惯。

典型读写链路:

1. 写入: 从对话、工具结果、用户显式指令中提取候选 memory。
2. 整理: 去重、合并、打标签、标来源、设置信心和过期时间。
3. 召回: 根据当前任务做 hybrid retrieval。
4. 注入: 把少量高价值 memory 放到 context。
5. 反馈: 用户纠错后更新或删除。

发展趋势:

- 从“全量历史检索”转向“结构化、可解释、可控”的 memory。
- 从单纯向量库转向混合检索: keyword、embedding、graph、recency、user pin。
- 更重视隐私和用户控制: 可查看、可删除、可禁用、可优先级排序。
- memory 与工具、文件、任务状态融合，不再只是聊天摘要。

头部玩家方向:

- ChatGPT memory 强调自动记住有用上下文、用户可控、可关闭和管理。
- OpenAI API 侧更强调由应用开发者自己管理工具、文件和状态，Responses API 中工具调用和工具输出是独立 item。
- Anthropic/Claude 强调工具使用、长上下文和 tool result 管理，Claude tool use 文档中区分 client tools 与 server tools。
- Claude Code 这类 coding agent 更强调代码库上下文、终端工具、文件 diff、任务过程和审计轨迹。

### 模块三: Task

#### 1. 长程任务中大模型可能忘掉目标，有哪些解决方案？优缺点是什么？

方案一: 显式任务状态机

- 做法: 把任务拆成 pending/running/blocked/done，每步更新状态。
- 优点: 可恢复、可审计、不会只靠 prompt 记忆。
- 缺点: 实现成本高，需要定义状态迁移。

方案二: Plan + Checklist

- 做法: 开始时生成计划，每轮执行后更新 checklist。
- 优点: 简单有效，适合 coding 和文档任务。
- 缺点: 模型可能机械执行旧计划，需要允许重规划。

方案三: Goal Reminder

- 做法: 每次 LLM 调用都注入目标、约束、当前阶段、停止条件。
- 优点: 成本低。
- 缺点: context 增加，目标写得差会误导。

方案四: 任务日志与周期性总结

- 做法: 记录每步动作、工具结果、决策原因，长任务定期压缩。
- 优点: 支持恢复和复盘。
- 缺点: 摘要质量影响后续执行。

方案五: 外部校验器

- 做法: 用测试、lint、断言、reviewer agent 或规则检查是否偏离目标。
- 优点: 能发现模型自信但错误。
- 缺点: 需要可验证目标和额外计算。

我的选择:

- MVP 用 checklist + goal reminder + trace。
- 生产系统用状态机 + durable queue + verifier。

#### 2. 用户要求每天早上 9 点根据昨天聊天情况做复盘总结，如何设计？

这不是普通 chat turn，而是 scheduled job。

组件:

- `scheduled_jobs`: user_id、cron、timezone、status、last_run_at。
- `job_runs`: job_id、local_date、status、started_at、finished_at、error。
- `messages/summaries/traces`: 复盘数据来源。
- `notifications`: 站内通知、邮件或下次打开时展示。

流程:

1. 用户创建任务: “每天 9 点复盘昨天聊天”。
2. Scheduler 按用户 timezone 找到 due job。
3. 用 lease/idempotency key 抢占任务，防止重复执行。
4. 查询昨天 00:00-23:59 的 sessions、messages、todos、tool traces。
5. 生成复盘: 完成事项、未完成事项、重要决定、风险、明日建议。
6. 存入 summaries 或 daily_reports。
7. 推送通知或写入用户下次 session 的 memory block。

关键设计:

- 用 `user_id + local_date` 做幂等。
- 如果昨天没有聊天，也生成“无活动”记录，避免用户以为系统坏了。
- 失败要可重试，但不能重复发多份总结。

### 模块四: Tool / Session Runtime

#### 1. 同步工具和异步工具如何设计？异步工具不能让用户一直等，但结果重要怎么办？

工具分两类:

- 同步工具: calculator、todo、mock weather，通常几秒内完成。
- 异步工具: 长网页抓取、批量文件分析、视频生成、长代码执行，可能几十秒到几小时。

设计:

1. ToolDefinition 声明 execution_mode: `sync` 或 `async`。
2. sync 工具在当前 loop 内执行，结果直接回传给 LLM。
3. async 工具创建 `tool_jobs`，返回 `job_id` 和 queued/running 状态。
4. Agent 立即回复用户: “任务已开始，完成后通知你”。
5. worker 执行异步任务，完成后写入 `tool_traces` 和 `tool_results`。
6. 通知层通过 WebSocket、站内通知、邮件或下次打开时提醒。
7. 如果用户继续追问，用 `job_id` 查询状态或读取结果。

注意:

- 异步工具必须有 correlation id。
- 结果要持久化，不能只在内存里。
- 失败要写明 error_type、可重试次数和用户可见摘要。

#### 2. session state 为 busy 时，新消息或异步工具完成事件到达，runtime 怎么处理？

不要嵌套调用同一个 session 的 runtime，否则会乱序和状态竞争。

设计:

1. session 有状态: `idle`、`busy`、`waiting_tool`、`failed`。
2. run_turn 前先获取 session lease。
3. 如果 session busy:
   - 新用户消息进入 `event_queue`。
   - 异步工具完成事件也进入 `event_queue`。
4. 当前 turn 完成后，按 sequence 顺序 drain queue。
5. 如果 async tool 完成时 session 正在等待它，可以唤醒 runtime 继续总结。
6. 如果用户新消息与工具完成冲突，按策略处理:
   - 保守策略: 严格顺序。
   - 高级策略: 根据事件类型合并，例如“用户取消任务”优先于“工具完成”。

关键:

- 所有事件都要有 sequence 和 created_at。
- session lease 要有 TTL，防止进程崩溃后永远 busy。
- 对用户可见状态要明确: running、queued、waiting。

### 模块五: Agent Runtime 架构对比

#### 1. Claude Code 工具输出方式和 GLM/豆包等 OpenAI-compatible function calling 有什么不同？优缺点是什么？

Claude Code 更像 host-orchestrated agent: 工具执行、文件修改、终端输出、权限确认和 diff 都由宿主 runtime 管理。模型提出行动，宿主执行工具，再把结果作为独立事件交回模型或展示给用户。

OpenAI-compatible function calling 更像 provider/API-level protocol: 应用把 tool schema 发给模型，模型返回结构化 tool call，应用执行工具后再把 tool output 作为下一轮消息发回模型。不同厂商虽然兼容 OpenAI 格式，但细节可能不同，例如 tool call 字段、流式增量、JSON 严格度、错误格式。

Claude Code 风格优点:

- 工具输出更适合工程任务: 文件 diff、命令输出、权限、失败日志都可审计。
- 宿主能做更强的安全控制和交互确认。
- 对复杂 coding workflow 更自然。

Claude Code 风格缺点:

- runtime 复杂，和宿主环境耦合。
- 不容易迁移到普通 API 服务。

Function calling 优点:

- schema 结构清晰，适合业务系统集成。
- 服务端/客户端边界明确。
- 多数 OpenAI-compatible 供应商可以复用同一套基本协议。

Function calling 缺点:

- 供应商兼容细节不完全一致。
- 工程任务中的 stdout、文件 diff、长日志、权限确认需要应用层额外设计。
- 模型有时会重复调用工具或参数抽取错误，需要 runtime 防护。

TraceWeave 的选择:

- 使用自有 JSON Action Protocol，不依赖某个 provider 的 native function calling。
- 好处是 portable、可测试、可审计。
- 代价是要自己写 parser、校验和 prompt 防护。

#### 2. OpenHands 状态机设计有什么优缺？更优雅的实现方式是什么？

OpenHands 这类系统的状态机思路是合理的: Agent 不是单轮聊天，而是由状态、事件、工具、环境和用户反馈驱动的循环。

优点:

- 状态清晰: 当前在思考、执行、等待用户、等待工具还是失败。
- 易恢复: 崩溃后可以从状态和事件日志恢复。
- 易审计: 每一步动作、观察、结果都有记录。
- 适合长程任务: 不依赖模型自己记住全部过程。

缺点:

- 状态数量容易膨胀，变成复杂分支。
- 如果状态和事件边界设计不好，会出现 busy、重复执行、乱序事件。
- 对简单任务显得重。
- 状态机逻辑和 prompt/tool 调用混在一起时维护困难。

更优雅的实现:

1. Event-sourced runtime: 所有用户消息、tool call、tool result、取消、恢复都作为事件追加。
2. Reducer 计算 session state: state 是事件流的投影，而不是到处手动改字段。
3. Durable queue: 所有外部事件排队处理，保证顺序和幂等。
4. Step executor: 每次只执行一个可恢复 step。
5. Policy 层与执行层分离: LLM 负责提出 action，runtime 负责校验、授权、执行、记录。
6. Typed action schema: 所有 action 都有严格 schema 和版本号。

这样可以兼顾 OpenHands 状态机的可恢复性，又减少状态爆炸和并发混乱。

## 十、参考资料

- OpenAI Function Calling: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI Tools: https://developers.openai.com/api/docs/guides/tools
- OpenAI ChatGPT Memory FAQ: https://help.openai.com/articles/8590148-memory-faq
- Anthropic Claude Tool Use: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- Claude Code Docs: https://code.claude.com/docs/en/quickstart

# AI Prompt 与问题解决记录

本文记录 TraceWeave Agent Runtime 开发中如何使用 AI 辅助，以及哪些关键问题由人工判断、验证和修复。AI 被用作工程助手，不作为不经审查的最终决策者。

## 使用原则

- AI 只辅助设计、代码生成、测试补充和审查，不替代人工判断。
- 核心 Agent Runtime 边界由人工确定: parser、tool registry、store、context builder、compression、trace、CLI/Web UI。
- 主流程不依赖 LangGraph、OpenHands、OpenClaw 等现有 Agent 框架。
- 测试结果必须来自真实命令输出，不能伪造。
- 真实 LLM API 需要通过 `.env` 配置，不把 API key 写进仓库。

## 关键 Prompt 记录

### Prompt 1: 从零实现最小可用 Agent Runtime

目标:

- 创建 Python 项目 `traceweave-agent-runtime`。
- 实现自研 Agent Loop。
- 不使用现有 Agent 框架做主流程。

产出:

- `AgentRuntime.run_turn(...)`
- `ActionParser`
- `ToolRegistry`
- `SQLiteStore`
- `ContextBuilder`
- `TraceLogger`

### Prompt 2: 设计 provider-neutral JSON Action Protocol

目标:

- 不依赖某个供应商的 native function calling。
- 让 OpenAI-compatible endpoint 只返回 JSON 文本。
- Runtime 自己解析、校验和执行工具。

协议字段:

- `action`: `tool_call` 或 `final_answer`
- `reasoning_summary`: 简短执行摘要
- `tool_call`: 工具名和参数
- `final_answer`: 最终回复

人工决策:

- 不保存完整 chain-of-thought。
- 只保存简短 `reasoning_summary` 作为可审计摘要。

### Prompt 3: 实现工具系统

目标:

- 至少支持 calculator、search、todo、weather、read_docs。
- 每个工具有名称、描述、参数 schema。
- 工具参数必须经过 JSON Schema 校验。

产出:

- `tools/base.py`
- `tools/registry.py`
- `tools/calculator.py`
- `tools/search.py`
- `tools/todo.py`
- `tools/weather.py`
- `tools/read_docs.py`

人工修正:

- calculator 使用 AST 白名单，避免 `eval` 风险。
- read_docs 限制读取目录，避免路径穿越。
- weather/todo schema 增加参数描述，减少模型乱填默认值。

### Prompt 4: 实现 session 隔离和持久化

目标:

- 同一用户不同窗口使用不同 `session_id`。
- 用户 A 的窗口 1 和窗口 2 互不影响。

产出:

- 所有 messages、todos、summaries、notes、traces 都带 `user_id` 与 `session_id`。
- SQLite 查询统一按 `user_id + session_id` 过滤。

人工验证:

- `tests/test_session_store.py`
- `tests/test_todo.py`
- `examples/demo_session_isolation.py`

### Prompt 5: 实现 context 管理和压缩

目标:

- 支持持续对话和追问。
- 支持最大轮次限制。
- context 过长时做基础压缩。

产出:

- `ContextBuilder`
- `DeterministicCompressor`
- `max_steps`
- `max_recent_messages`
- `max_context_tokens`

人工决策:

- 最近消息保留原文。
- 旧消息写入 summary。
- open todos 作为结构化状态单独注入。
- 完整 trace 不进入 prompt。

### Prompt 6: 加入本地 Web UI

目标:

- 题目允许“终端或网页操作录屏”。
- Web UI 只作为薄界面，不替代 runtime。

产出:

- `traceweave serve --host 127.0.0.1 --port 8787`
- `web_app.py`
- Todos 和 Trace 面板
- `tests/test_web_app.py`

人工判断:

- Web UI 符合题目，因为核心 loop 仍然调用 `AgentRuntime.run_turn(...)`。
- 没有引入前端框架或 Agent 框架，降低交付复杂度。

## 问题与修复记录

### 问题 1: 不能使用现有 Agent 框架

风险:

- 使用 LangGraph/OpenHands/OpenClaw 会违反题目“核心 Agent Runtime 自行实现”。

处理:

- 只使用普通 Python 依赖。
- Agent loop、parser、tool registry、store、context、compression、trace 都自己写。

### 问题 2: OpenAI-compatible function calling 兼容性不一致

风险:

- 不同供应商对 tool call、stream、JSON 格式支持不完全一致。

处理:

- 使用自有 JSON Action Protocol。
- LLM 只输出 JSON 文本。
- Runtime 自己解析和校验。

### 问题 3: calculator 安全风险

风险:

- 如果直接 `eval` 用户输入，可能执行任意代码。

处理:

- 使用 Python AST 解析。
- 只允许数字、加减乘除、幂、取负等安全节点。

### 问题 4: session 数据串扰

风险:

- 用户 A 的窗口 1 和窗口 2 待办混在一起。

处理:

- 所有持久化表都存 `user_id` 和 `session_id`。
- 查询统一过滤两者。
- 添加 session 隔离测试。

### 问题 5: LLM 重复调用同一个工具

现象:

- 模型在 weather/search 后没有 final answer，而是重复调用工具直到 `max_steps`。

修复:

- Runtime 记录本轮所有 tool result summaries。
- 下一步 LLM context 中加入 Tool Results Block。
- 当前 user message 后追加“本轮已有工具结果”，提醒不要重复调用。
- Runtime Policy 明确工具完成后要 `final_answer`。

### 问题 6: NVIDIA GLM-5.2 请求超时

现象:

- `z-ai/glm-5.2` 在 NVIDIA endpoint 上最小 chat 请求也可能 read timeout。

处理:

- 切换到更稳定的 `qwen/qwen3-next-80b-a3b-instruct`。
- 增加 `OPENAI_TIMEOUT_SECONDS`。
- 增加 `OPENAI_MAX_TOKENS`。
- 增加 `OPENAI_TEMPERATURE=0`，提高录屏稳定性。

### 问题 7: Web API 验证脚本中文变成问号

现象:

- PowerShell 管道内联 Python 时，中文消息变成 `????????`，模型返回“无法理解”。

处理:

- 验证脚本使用 Unicode escape。
- 浏览器手动输入中文不受影响。

### 问题 8: 本地运行产物可能被误提交

风险:

- `.env`、SQLite 数据库、pid 文件被提交会泄漏密钥或污染仓库。

处理:

- `.gitignore` 排除 `.env`、`.traceweave/`、`.venv/`、缓存目录。
- 提交前检查 staged diff 中无真实 NVIDIA API key 前缀或其他密钥。

## 手工架构决策

- 工具输出完整 payload 只进入 trace，prompt 中只放摘要。
- Todo 和 note 是结构化状态，不靠模型从聊天历史里猜。
- Context 压缩采用确定性策略，便于测试复现。
- Search 和 weather 默认 mock-first，符合题目允许 mock/自定义的要求。
- Web UI 只负责交互展示，核心能力仍在 runtime。

## 验证命令

```powershell
python -m pytest
traceweave init-db
traceweave chat --user-id alice --session-id weather --message "查一下上海明天的天气，并记一个待办：明天带伞。"
traceweave list-todos --user-id alice --session-id weather
traceweave show-traces --user-id alice --session-id weather
traceweave serve --host 127.0.0.1 --port 8787
```

## 当前限制

- Long-term semantic memory 只预留 `Relevant Memory Block`，未实现生产级向量/图谱记忆。
- Weather 是 deterministic mock，不是真实天气 API。
- Search 默认 mock，可配置真实 endpoint。
- 异步工具和 busy session 队列在架构题中设计，MVP runtime 主要实现同步工具。

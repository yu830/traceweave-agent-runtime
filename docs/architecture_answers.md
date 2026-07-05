# 架构设计题完整回答

本文对应笔试架构设计题 5 个模块，每个模块 2 道题均作答。README 主页中也收录了同一组答案，便于 GitHub 首页直接查看。

## 索引

- [模块一: Context / Performance](#模块一-context--performance)
- [模块二: Memory](#模块二-memory)
- [模块三: Task](#模块三-task)
- [模块四: Tool / Session Runtime](#模块四-tool--session-runtime)
- [模块五: Agent Runtime 架构对比](#模块五-agent-runtime-架构对比)

## 模块一: Context / Performance

### 1. 大模型面对第一轮长窗口或多模态输入时 first token 变慢，如何低成本从 5-10 秒压到 2 秒？

核心判断: 不要把“完整理解长输入”和“用户看到第一响应”绑死。2 秒目标应当是首个可信响应或进度反馈，而不是完整最终答案。

方案:

1. 上传即预处理: 文件上传后立即做 OCR、PDF 分段、图片说明、embedding、摘要缓存。
2. 先返回状态: 首 token 返回“已收到，正在解析 3 个文件/图片”，同时显示进度。
3. 分层摘要: 多模态或长文本先压成目录、关键实体、片段索引，再给主模型。
4. 缓存: 以文件 hash、图片 hash、chunk id 缓存 OCR、embedding、摘要和检索结果。
5. 小模型路由: 小模型先判断任务类型和需要读取的片段，大模型只处理必要上下文。
6. Prompt 裁剪: 首轮只放任务、约束、索引和最高相关片段，不塞全量原文。
7. 流式输出: 让用户看到系统开始工作，同时后台继续解析。

用户体验:

- 2 秒内给“已接收 + 正在处理 + 当前进度”。
- 解析完成后再给完整答案。
- 如果后台失败，明确展示失败原因和重试入口。

### 2. 一个 session 连续聊了 200 轮，context 快爆了，怎么压缩并保持流畅？

我会采用分层 context，而不是把 200 轮直接压成一段摘要。

层级:

1. 最近消息: 最近 8-20 轮保留原文。
2. 会话摘要: 更早内容压缩成目标、结论、未完成事项、用户偏好、重要事实。
3. 结构化状态: todos、notes、决策、文件引用、工具结果索引独立存储。
4. Trace 外置: 完整工具输出保存在 trace，不默认进入 prompt。
5. 可回溯范围: summary 记录 start_message_id 和 end_message_id。

流程:

1. 每轮写入消息。
2. 估算未压缩消息数和 token。
3. 超阈值时压缩旧消息，保留最新 N 条。
4. 更新 summary，标记旧消息 summarized。
5. 下一轮 context 使用 summary + open todos + recent messages + tool result summaries。

流畅性保障:

- 近期内容必须保留原文。
- 待办、决策和工具结果索引用结构化表保存。
- 用户问旧细节时，用 summary 定位，再回查原消息或 trace。
- 压缩摘要必须包含“已完成、未完成、偏好、待确认问题”。

## 模块二: Memory

### 1. 用户半个月后问以前问过的问题，Agent 如何做 memory 召回更合理？

合理做法是按需召回，而不是无脑注入历史。

流程:

1. 识别当前问题是否需要记忆: “上次、之前、我以前、那个方案”等是强信号。
2. 候选召回: 查结构化 memory、session summary、语义向量、关键词索引。
3. 过滤: 按 user_id、时间、相似度、置信度、是否过期、是否冲突过滤。
4. 精简注入: 只放少量 memory snippets，带来源、时间、置信度。
5. 过期提示: 对可能变化的信息，说明“这是之前记录，可能需要重新确认”。
6. 用户纠错: 更新 memory，降低旧 memory 权重或标记失效。

原则:

- 用户偏好、长期项目背景适合长期记忆。
- 时间敏感信息要有过期策略。
- 记忆必须可查看、可删除、可禁用。

### 2. Agent memory 经典框架是什么？趋势是什么，头部玩家怎么做？

经典框架:

1. Working memory: 当前轮上下文，直接进入 prompt。
2. Episodic memory: 历史事件、会话片段、任务摘要。
3. Semantic memory: 用户偏好、长期事实、实体关系。
4. Procedural memory: 用户喜欢的工作流、格式、工具习惯。

读写链路:

1. 从对话和工具结果中抽取候选记忆。
2. 去重、合并、标来源、设置信心和过期时间。
3. 当前任务触发检索。
4. 将少量相关记忆注入 context。
5. 根据用户反馈更新或删除。

趋势:

- 从单纯向量库转向 hybrid memory: keyword + embedding + graph + recency + user pin。
- 从不可见黑盒转向用户可控: 查看、禁用、删除、优先级管理。
- 从聊天历史摘要转向任务状态、工具结果、文件知识和用户偏好的融合。

头部玩家方向:

- ChatGPT memory 强调自动记住有用上下文，并允许用户管理、关闭和调整记忆。
- OpenAI API 侧强调应用自己管理状态、工具输出和文件知识；Responses API 中工具调用和工具输出是可关联的独立 item。
- Anthropic Claude tool use 强调模型根据工具描述决定调用，由应用或服务端执行工具并返回结构化结果。
- Claude Code 类 coding agent 更强调代码库上下文、终端工具、文件修改、diff 和审计轨迹。

## 模块三: Task

### 1. 长程任务中模型可能忘掉目标，有哪些解决方案？优缺点是什么？

方案:

1. 显式状态机
   - 优点: 可恢复、可审计、目标不靠模型记忆。
   - 缺点: 实现复杂，需要设计状态迁移。
2. Plan + Checklist
   - 优点: 简单有效，适合 coding 和文档任务。
   - 缺点: 计划可能过期，需要重规划。
3. Goal Reminder
   - 优点: 成本低，每轮提醒目标和停止条件。
   - 缺点: 占 context，写得不好会误导。
4. 任务日志和周期性总结
   - 优点: 支持恢复、复盘和压缩。
   - 缺点: 摘要质量影响后续执行。
5. 外部校验器
   - 优点: 用测试、lint、review 或规则防止跑偏。
   - 缺点: 需要额外成本和可验证目标。

我的取舍:

- MVP: checklist + goal reminder + trace。
- 生产: durable state machine + event queue + verifier。

### 2. 用户要求每天早上 9 点根据昨天聊天情况做复盘总结，如何设计？

这是 scheduled job，不是普通 chat turn。

数据结构:

- `scheduled_jobs`: user_id、cron、timezone、status、last_run_at。
- `job_runs`: job_id、local_date、status、started_at、finished_at、error。
- `daily_reports`: user_id、date、summary、source_session_ids。
- `messages/summaries/traces/todos`: 复盘数据来源。

流程:

1. 用户创建计划任务。
2. Scheduler 按用户 timezone 判断 9 点 due job。
3. 用 lease 和 `user_id + local_date` 做幂等。
4. 查询昨天所有 session 的消息、待办、工具结果。
5. 生成复盘: 完成事项、未完成事项、重要决定、风险、明日建议。
6. 存入 daily_reports。
7. 通过站内通知、邮件或下次对话 memory block 展示。

异常处理:

- 无聊天记录也生成“昨日无聊天活动”。
- 失败可重试，但不重复发送。
- 用户可以暂停、修改时间、删除计划任务。

## 模块四: Tool / Session Runtime

### 1. 同步和异步工具如何设计？异步工具不能让用户一直等，但结果重要怎么办？

同步工具:

- 适合 calculator、todo、mock weather。
- 当前 loop 内执行，结果直接回传 LLM。

异步工具:

- 适合长网页抓取、批量文件分析、视频生成、长代码执行。
- 当前 loop 只创建 job，返回 `job_id` 和状态。

设计:

1. `ToolDefinition.execution_mode = sync | async`。
2. async 工具写入 `tool_jobs`。
3. worker 异步执行并写入 `tool_traces` 和 `tool_results`。
4. UI 展示 queued/running/done/failed。
5. 完成后通过 WebSocket、站内通知、邮件或下次 session 提醒。
6. 用户追问时用 `job_id` 查询状态或读取结果。

关键:

- correlation id 必须持久化。
- 结果不能只存在内存。
- 失败要可见、可重试、可审计。

### 2. session state 为 busy 时，新消息或异步工具完成事件到达，runtime 如何处理？

不要在 busy session 内嵌套启动新的 run_turn。

设计:

1. session 状态: `idle`、`busy`、`waiting_tool`、`failed`。
2. run_turn 前获取 session lease。
3. 如果 busy:
   - 用户新消息进入 `event_queue`。
   - async tool 完成事件也进入 `event_queue`。
4. 当前 step 完成后按 sequence 顺序处理队列。
5. 如果工具完成事件对应等待中的 job，唤醒 session 继续总结。
6. lease 有 TTL，防止进程崩溃后永久 busy。

策略:

- 默认严格顺序，保证可解释。
- 对取消任务、用户纠错等高优先级事件可以插队，但必须有明确规则。

## 模块五: Agent Runtime 架构对比

### 1. Claude Code 工具输出方式和 GLM/豆包等 OpenAI-compatible function calling 有什么不同？优缺点是什么？

Claude Code 更偏 host-orchestrated:

- 模型提出动作。
- 宿主执行文件、终端、搜索、git 等工具。
- 工具结果、diff、权限、错误作为事件回到运行时。
- 更适合代码库和终端环境。

OpenAI-compatible function calling 更偏 API protocol:

- 应用把 tools schema 发给模型。
- 模型返回结构化 tool call。
- 应用执行工具后，把 tool output 发回模型。
- 适合业务 API 集成。

Claude Code 风格优点:

- 工具输出可审计。
- 权限和文件修改更安全。
- 适合长程 coding workflow。

Claude Code 风格缺点:

- runtime 复杂，和宿主环境耦合。
- 不易迁移到普通后端服务。

Function calling 优点:

- schema 清晰。
- 应用边界明确。
- 多家 OpenAI-compatible endpoint 可复用基本形态。

Function calling 缺点:

- 不同供应商兼容细节不完全一致。
- 工程工具的 stdout、diff、权限确认要应用层补。
- 模型可能重复工具调用或参数抽取错误。

TraceWeave 的选择:

- 自己实现 JSON Action Protocol。
- 不依赖 native function calling。
- 好处是 provider-neutral、可测试、可审计。
- 代价是 parser、校验、工具循环防护都要自己实现。

### 2. OpenHands 的状态机设计有什么优缺？更优雅的实现方式是什么？

优点:

- Agent 过程可恢复。
- 状态、动作、观察、错误更清晰。
- 长程任务不只靠 prompt 记忆。
- 容易做审计和回放。

缺点:

- 状态数量容易膨胀。
- busy、等待工具、用户插入消息容易产生竞态。
- 对简单任务显得重。
- 如果 prompt、状态迁移和工具执行耦合，会难维护。

更优雅的实现:

1. Event-sourced runtime: 用户消息、tool call、tool result、取消、恢复全是事件。
2. Reducer 计算 session state: 状态由事件流投影得出。
3. Durable queue: 所有外部事件排队，保证顺序和幂等。
4. Step executor: 每次执行一个可恢复 step。
5. Policy 与 execution 分离: LLM 提 action，runtime 校验和执行。
6. Typed action schema: action 有版本、schema 和权限边界。

这样既保留状态机的可恢复性，又减少状态爆炸和并发混乱。

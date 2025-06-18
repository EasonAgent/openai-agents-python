<!-- 
-->

- news | New tools for building agents [web](https://openai.com/index/new-tools-for-building-agents/)
- OpenAI Agents SDK [doc](https://openai.github.io/openai-agents-python/); [github](https://openai.github.io/openai-agents-python/)

需要关注的
- [x] agent 架构
    - [x] agent
    - [x] runner | 数据无关
    - [x] agents | 交接, orchestrate
    - [x] LLM provider
    - [x] tool
- [ ] data
    - [ ] 数据组织 (RunItem, RunResult, RunResultStreaming)
    - [x] context
    - [ ] 对话信息管理? -- 这个框架里面比较简单, 参见 responses API, 以及 `src/agents/models/openai_chatcompletions.py`
- [x] prompting -- 这里基本就没有prompt, 因为是通用框架
- [ ] utils
    - [x] logging -- 这里的方案也是极简的, 可以参考其在哪些节点进行log
    - [x] tracing -- 实际上是一个比较大的topic, 看看如何使用吧! 
    - [x] hooks -- 在agent/run粒度都可以设置, 重点关注 start/end/handoff/tool_start/end 这5个时间节点
- [ ] coding 风格学习
    - [ ] 统一的 stream/non-stream 处理 | event处理
    - [ ] typing -> 是对于逻辑的清晰抽象!
        - [ ] Generic[TContext]
        - [ ] dataclass v.s. Pydantic
    - [ ] hooks & tracing & logging
    - [ ] 代码执行图! 
    - [ ] dataclass v.s. Pydantic? 
        - [ ] dataclass: [doc](https://docs.python.org/3/library/dataclasses.html)
- [ ] dev
    - [ ] coverage
    - [ ] ruff
    - [ ] mypy
    - [ ] pytest
    - [ ] mkdocs
    - [ ] hatch v.s. poetry
    - [ ] uv
- [ ] IMPL @FA_agents
    - [x] memory? -- GitHub 上有一些 PR/分叉 1) 使用mem0的方案被拒掉了 [pr](https://github.com/openai/openai-agents-python/pull/22/files)
    - [x] Use tool output as agent output | 工具返回结果作为agent输出 [issue](https://github.com/openai/openai-agents-python/issues/117)
    - [x] MCP - 有人提出了一个PR, 但推荐通过官方的SDK来构建server [issue](https://github.com/openai/openai-agents-python/issues/23)
    - [ ] HTTP server [https://github.com/openai/openai-agents-python/issues/126]

## Overview

### 特色
- **Agent loop**: Built-in agent loop that handles calling tools, sending results to the LLM, and looping until the LLM is done.
- **Python-first**: Use built-in language features to orchestrate and chain agents, rather than needing to learn new abstractions.
- **Handoffs**: A powerful feature to coordinate and delegate between multiple agents.
- **Guardrails**: Run input validations and checks in parallel to your agents, breaking early if the checks fail.
- **Function tools**: Turn any Python function into a tool, with automatic schema generation and Pydantic-powered validation.
- **Tracing**: Built-in tracing that lets you visualize, debug and monitor your workflows, as well as use the OpenAI suite of evaluation, fine-tuning and distillation tools.

### 框架设计
- Tool
    - 工具定义: `Tool`, 核心还是函数定义, `FunctionTool|FileSearchTool|WebSearchTool|ComputerTool`
- Handoff
    - 转接定义: `Handoff`, 
    - 提供一个 handoff 方法将agent转换 Handoff
    - 对于特定agent而言, 可以看作一个工具
- Model
    - 模型定义: `Model`, 基本就是 responses API 的抽象
    - 非流式: `get_response` -> `ResponseOutputItem` in responses API
    - 流式: `stream_response` -> `ResponseStreamEvent` in responses API
- Agent
    - 定义: `Agent`. 抽象出agent场景下所用到的数据
- Runner
    - 定义: `Runner`. 负责调用agent和tools, 以及管理agent的生命周期 (hooks)
    - 输出: `RunResult`: input, new_items, raw_responses, final_output, last_agent, to_input_list
    - 更细的粒度: `SingleStepResult`: original_input, model_response, pre_step_items, new_step_items, `next_step` (handoff/final output/run again)
- 流式
    - 输出三种粒度的事件 `StreamEvent`: AgentUpdatedStreamEvent | RunItemStreamEvent | RawResponsesStreamEvent 建模不同的粒度
    - 原子粒度: `RunItem` (MessageOutputItem, HandoffCallItem, HandoffOutputItem, ToolCallItem, ToolCallOutputItem, ReasoningItem)
    - 模型输出的粒度 (responses API): `ResponseStreamEvent`, 见 responses API

responses API
- `ResponseStreamEvent`: 模型输出的粒度 [TODO]

### topics
1. 如何构建一个 agents 服务? 
    - 参考 Runner.run_streamed, 返回的 RunResultStreaming.stream_events() -> AsyncIterator[StreamEvent], 返回事件流!
    - 参见 [issue](https://github.com/openai/openai-agents-python/issues/126)
    - 如何使用? 和 responses API 一样, 可以把所需要的信息给到客户端, 而使用方只需要再传入增量数据即可! 


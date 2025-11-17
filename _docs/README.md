NOTE: 参见 [agent_ref/doc]
NOTE: 目前仅仅clone下来, 未做改写

- openai-agents [github](https://github.com/openai/openai-agents-python/releases); [doc](https://openai.github.io/openai-agents-python/)
- fork: <https://github.com/EasonAgent/openai-agents-python>
- branch: eason
- tag: v0.5.0


## 更新到 0.1.13
1. 支持 LiteLLM 模型 (src/agents/extensions/models/litellm_model.py)
2. 支持 multi_provider (src/agents/models/multi_provider.py)
3. 支持 extra_headers 参数 (src/agents/model_settings.py)
4. 支持非严格JSON输出 (src/agents/agent_output.py)
5. 分离 Converter (src/agents/models/chatcmpl_converter.py)
6. 分离 ChatCmlpStreamHandler (src/agents/models/chatcmpl_stream_handler.py)
7. 对于 RunResultStreaming 增加 `cancel` 方法 (src/agents/result.py)

## 更新到 0.2.0
1. 分离了 AgentBase + Agent, 主要用于支持 real-time
2. 定义了 `Sessions` 来管理会话

## 更新到 0.2.3
1. 支持MCP工具返回 structuredContent

## 更新到 0.2.5
1. 支持了 temporalio [github](https://github.com/temporalio/sdk-python/tree/main/temporalio/contrib/openai_agents)


## RULES
1. 透明封装? 
2. 变更: 将修改点记录到 OVERWRITE.md

NOTE: 参见 [agent_ref/doc]
NOTE: 目前仅仅clone下来, 未做改写

## 更新到 0.1.13
1. 支持 LiteLLM 模型 (src/agents/extensions/models/litellm_model.py)
2. 支持 multi_provider (src/agents/models/multi_provider.py)
3. 支持 extra_headers 参数 (src/agents/model_settings.py)
4. 支持非严格JSON输出 (src/agents/agent_output.py)
5. 分离 Converter (src/agents/models/chatcmpl_converter.py)
6. 分离 ChatCmlpStreamHandler (src/agents/models/chatcmpl_stream_handler.py)
7. 对于 RunResultStreaming 增加 `cancel` 方法 (src/agents/result.py)

## RULES
1. 透明封装? 
2. 变更: 将修改点记录到 OVERWRITE.md

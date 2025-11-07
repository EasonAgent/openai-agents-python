## 配置项
> [doc](https://openai.github.io/openai-agents-python/config/)

1. API keys and clients: 模型配置参见 providers 部分正常定义即可
2. Tracing: 同上
3. Debug logging
    1. 默认采用 `logger = logging.getLogger("openai.agents")`, 未做任何配置; 包括 `openai.agents` 和 `openai.agents.tracing` 两个 logger
    2. Alternatively, you can customize the logs by adding handlers, filters, formatters, etc. You can read more in the [Python logging guide](https://docs.python.org/3/howto/logging.html).
    3. 敏感信息配置:
        1. `export OPENAI_AGENTS_DONT_LOG_MODEL_DATA=1`: 禁止log模型的输入输出
        2. `export OPENAI_AGENTS_DONT_LOG_TOOL_DATA=1`: 禁止log工具的调用和输出

### logging
> see [Python logging guide](https://docs.python.org/3/howto/logging.html).

```python
# op0: 默认配置
from agents import enable_verbose_stdout_logging
enable_verbose_stdout_logging()

# src/agents/__init__.py
def enable_verbose_stdout_logging():
    """Enables verbose logging to stdout. This is useful for debugging."""
    logger = logging.getLogger("openai.agents")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
```


```python
# op1: 手动配置
import logging

logger =  logging.getLogger("openai.agents") # or openai.agents.tracing for the Tracing logger

# To make all logs show up
logger.setLevel(logging.DEBUG)
# To make info and above show up
logger.setLevel(logging.INFO)
# To make warning and above show up
logger.setLevel(logging.WARNING)
# etc

# You can customize this as needed, but this will output to `stderr` by default
logger.addHandler(logging.StreamHandler())
```

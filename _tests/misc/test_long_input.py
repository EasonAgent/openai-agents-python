""" updated: 2025-05-28 

- [x] 测试agents-sdk来遇到输入超长时的情况 -- 直接回传openai-sdk的错误: 
    openai.BadRequestError: Error code: 400 - {'error': {'message': "This model's maximum context length is 128000 tokens. However, your messages resulted in 200022 tokens. Please reduce the length of the messages.", 'type': 'invalid_request_error', 'param': 'messages', 'code': 'context_length_exceeded'}}
"""
import logging
from agents import Agent, Runner
from utils import print_stream_events


async def test_short_input(agent: Agent):
    query = "who was the first president of the united states?"
    # result = await Runner.run(agent, query)
    # logging.info(result.final_output)
    result = Runner.run_streamed(agent, input=query)
    await print_stream_events(result)

async def test_long_input(agent: Agent):
    query = "who was the first president of the united states? "  # 10 tokens
    query *= 20_000  # 200k
    result = Runner.run_streamed(agent, input=query)
    await print_stream_events(result)


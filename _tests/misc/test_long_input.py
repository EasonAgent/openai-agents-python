import logging
from agents import Agent, Runner
from utils import print_stream_events


async def test_short_input(agent: Agent):
    result = await Runner.run(agent, "who was the first president of the united states?")
    logging.info(result.final_output)

    result = Runner.run_streamed(
        agent,
        input="Hello",
    )
    await print_stream_events(result)


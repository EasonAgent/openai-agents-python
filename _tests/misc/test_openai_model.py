from openai import AsyncOpenAI


async def test_openai_model(openai_client: AsyncOpenAI):
    """Test the availability of the OpenAI API."""
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Write a haiku."}],
    )
    print(response.choices[0].message.content)

async def test_openai_model_stream(openai_client: AsyncOpenAI):
    """Test the availability of the OpenAI API."""
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Write a haiku."}],
        stream=True,
    )
    async for chunk in response:
        print(chunk.choices[0].delta.content, end="", flush=True)

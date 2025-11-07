import io
import abc
import asyncio
from typing import Any
from collections.abc import AsyncIterator
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .run import Runner, RunResultStreaming, TraceCtxManager
from .agent import Agent
from .items import TResponseInputItem

DEFAULT_SAMPLE_RATE = 24000

""" --------------------------------------------------------------------------------------------------------------------
# src/agents/voice/input.py
-------------------------------------------------------------------------------------------------------------------- """
@dataclass
class AudioInput:
    """Static audio to be used as input for the VoicePipeline."""
    buffer: npt.NDArray[np.int16 | np.float32]
    """ A buffer containing the audio data for the agent. Must be a numpy array of int16 or float32. """
    frame_rate: int = DEFAULT_SAMPLE_RATE
    """The sample rate of the audio data. Defaults to 24000."""
    sample_width: int = 2
    """The sample width of the audio data. Defaults to 2."""
    channels: int = 1
    """The number of channels in the audio data. Defaults to 1."""
    def to_audio_file(self) -> tuple[str, io.BytesIO, str]:
        """Returns a tuple of (filename, bytes, content_type)"""
    def to_base64(self) -> str:
        """Returns the audio data as a base64 encoded string."""

class StreamedAudioInput:
    """Audio input represented as a stream of audio data. You can pass this to the `VoicePipeline`
    and then push audio data into the queue using the `add_audio` method.
    """
    def __init__(self):
        self.queue: asyncio.Queue[npt.NDArray[np.int16 | np.float32] | None] = asyncio.Queue()
    async def add_audio(self, audio: npt.NDArray[np.int16 | np.float32] | None):
        """Adds more audio data to the stream."""

""" --------------------------------------------------------------------------------------------------------------------
# src/agents/voice/workflow.py

SingleAgentVoiceWorkflow: 封装文本形式的 Agent, 语音场景下仅支持流式输出
SingleAgentWorkflowCallbacks: 回调机制, 支持比如在运行开始执行一些操作 (比如发送欢迎语)
-------------------------------------------------------------------------------------------------------------------- """
class SingleAgentVoiceWorkflow(VoiceWorkflowBase):
    """A simple voice workflow that runs a single agent. Each transcription and result is added to
    the input history.
    For more complex workflows (e.g. multiple Runner calls, custom message history, custom logic,
    custom configs), subclass `VoiceWorkflowBase` and implement your own logic.
    """
    def __init__(self, agent: Agent[Any], callbacks: SingleAgentWorkflowCallbacks | None = None):
        self._input_history: list[TResponseInputItem] = []
        self._current_agent = agent
        self._callbacks = callbacks
    async def run(self, transcription: str) -> AsyncIterator[str]:
        if self._callbacks:
            self._callbacks.on_run(self, transcription)
        # Run the agent
        result = Runner.run_streamed(self._current_agent, self._input_history)
        # Stream the text from the result
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            yield chunk

class VoiceWorkflowBase(abc.ABC):
    """
    A base class for a voice workflow. You must implement the `run` method. A "workflow" is any
    code you want, that receives a transcription and yields text that will be turned into speech
    by a text-to-speech model.
    In most cases, you'll create `Agent`s and use `Runner.run_streamed()` to run them, returning
    some or all of the text events from the stream. You can use the `VoiceWorkflowHelper` class to
    help with extracting text events from the stream.
    If you have a simple workflow that has a single starting agent and no custom logic, you can
    use `SingleAgentVoiceWorkflow` directly.
    """
    @abc.abstractmethod
    def run(self, transcription: str) -> AsyncIterator[str]: ...
    async def on_start(self) -> AsyncIterator[str]:
        """
        Optional method that runs before any user input is received. Can be used
        to deliver a greeting or instruction via TTS. Defaults to doing nothing.
        """

class SingleAgentWorkflowCallbacks:
    def on_run(self, workflow: SingleAgentVoiceWorkflow, transcription: str) -> None:
        """Called when the workflow is run."""

class VoiceWorkflowHelper:
    @classmethod
    async def stream_text_from(cls, result: RunResultStreaming) -> AsyncIterator[str]:
        """Wraps a `RunResultStreaming` object and yields text events from the stream."""

""" --------------------------------------------------------------------------------------------------------------------
# src/agents/voice/pipeline.py

-------------------------------------------------------------------------------------------------------------------- """
class VoicePipeline:
    """An opinionated voice agent pipeline. It works in three steps:
    1. Transcribe audio input into text.
    2. Run the provided `workflow`, which produces a sequence of text responses.
    3. Convert the text responses into streaming audio output.
    """
    async def run(self, audio_input: AudioInput | StreamedAudioInput) -> StreamedAudioResult:
        """Run the voice pipeline."""
    async def _run_single_turn(self, audio_input: AudioInput) -> StreamedAudioResult:
        with TraceCtxManager(...): 
            input_text = await self._process_audio_input(audio_input)
            output = StreamedAudioResult(self._get_tts_model(), self.config.tts_settings, self.config)
            output._set_task(asyncio.create_task(stream_events()))
            return output
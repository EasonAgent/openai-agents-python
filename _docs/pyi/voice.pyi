""" 
- https://platform.openai.com/docs/guides/audio

[project.optional-dependencies]
voice = ["numpy>=2.2.0, <3; python_version>='3.10'", "websockets>=15.0, <16"]

1. VoicePipeline: 建模完成的交互流程. SST -> workflow -> TTS
    - 单轮: 将输入音频转为文本, 过一遍 workflow, 流式输出文本+音频
    - 多轮: 输出同单轮模式 (文本流送入 TTS 模型), 但会通过 STT 模型持续接收音频输入
2. SST: 将连续会话建模为一个 session, 通过 turn_detection 来检测对话轮次 (划分输入到workflow的文本片段)
3. TTS: 处理workflow得到的文本流, 转为音频 (字节流)
    - 设置参数 buffer_size, voice, speed, instructions 等. 
    - text_splitter: Callable[[str], tuple[str, str]] 用于处理文本流, 默认的 get_sentence_based_splitter 根据句子划分

"""
from typing import AsyncIterator, Any, Literal, Callable, Union
from typing_extensions import TypeAlias
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import io, asyncio, abc

from .agent import Agent
from .item import TResponseInputItem
from .run import Runner, RunResultStreaming, TraceCtxManager

""" --------------------------------------------------------------------------------------
# src/agents/voice/input.py

包括流式和静态两种输入方式 (对应两种pipeline)
-------------------------------------------------------------------------------------- """
DEFAULT_SAMPLE_RATE = 24000

@dataclass
class AudioInput:
    """Static audio to be used as input for the VoicePipeline."""
    buffer: npt.NDArray[np.int16 | np.float32]
    # A buffer containing the audio data for the agent. Must be a numpy array of int16 or float32.
    frame_rate: int = DEFAULT_SAMPLE_RATE
    sample_width: int = 2
    channels: int = 1
    def to_audio_file(self) -> tuple[str, io.BytesIO, str]:
        """Returns a tuple of (filename, bytes, content_type)"""
    def to_base64(self) -> str:
        """Returns the audio data as a base64 encoded string."""

class StreamedAudioInput:
    """Audio input represented as a stream of audio data. You can pass this to the `VoicePipeline`
    and then push audio data into the queue using the `add_audio` method.
    """
    def __init__(self):
        self.queue: asyncio.Queue[npt.NDArray[np.int16 | np.float32]] = asyncio.Queue()
    async def add_audio(self, audio: npt.NDArray[np.int16 | np.float32]):
        """Adds more audio data to the stream."""


""" --------------------------------------------------------------------------------------
# src/agents/voice/result.py
-------------------------------------------------------------------------------------- """
class StreamedAudioResult:
    """The output of a `VoicePipeline`. Streams events and audio data as they're generated."""
    def __init__(
        self,
        tts_model: TTSModel,
        tts_settings: TTSModelSettings,
        voice_pipeline_config: VoicePipelineConfig,
    ):
        self.tts_model = tts_model
        self.tts_settings = tts_settings
        self.total_output_text = ""
        self.instructions = tts_settings.instructions
        self.text_generation_task: asyncio.Task[Any] | None = None

    async def stream(self) -> AsyncIterator[VoiceStreamEvent]:
        """Stream the events and audio data as they're generated."""


""" --------------------------------------------------------------------------------------
# src/agents/voice/events.py

事件：主要是流式音频输出
-------------------------------------------------------------------------------------- """
@dataclass
class VoiceStreamEventAudio:
    """Streaming event from the VoicePipeline"""
    data: npt.NDArray[np.int16 | np.float32] | None
    type: Literal["voice_stream_event_audio"] = "voice_stream_event_audio"
@dataclass
class VoiceStreamEventLifecycle:
    """Streaming event from the VoicePipeline"""
    event: Literal["turn_started", "turn_ended", "session_ended"]
    type: Literal["voice_stream_event_lifecycle"] = "voice_stream_event_lifecycle"
@dataclass
class VoiceStreamEventError:
    """Streaming event from the VoicePipeline"""
    error: Exception
    type: Literal["voice_stream_event_error"] = "voice_stream_event_error"

VoiceStreamEvent: TypeAlias = Union[VoiceStreamEventAudio, VoiceStreamEventLifecycle, VoiceStreamEventError]


""" --------------------------------------------------------------------------------------
# src/agents/voice/pipeline.py 整体 STT -> Workflow -> TTS 流程

1. 区分单轮和多轮形式
    单轮: 将输入音频转为文本, 过一遍 workflow, 流式输出文本+音频
    多轮: 输出同单轮模式 (文本流送入 TTS 模型), 但会通过 STT 模型持续接收音频输入
-------------------------------------------------------------------------------------- """
class VoicePipeline:
    """An opinionated voice agent pipeline. It works in three steps:
    1. Transcribe audio input into text.
    2. Run the provided `workflow`, which produces a sequence of text responses.
    3. Convert the text responses into streaming audio output.
    """
    def __init__(
        self,
        *,
        workflow: VoiceWorkflowBase,
        stt_model: STTModel | str | None = None,
        tts_model: TTSModel | str | None = None,
        config: VoicePipelineConfig | None = None,
    ):
        self.workflow = workflow
        self.stt_model = stt_model if isinstance(stt_model, STTModel) else None
        self.tts_model = tts_model if isinstance(tts_model, TTSModel) else None
        self._stt_model_name = stt_model if isinstance(stt_model, str) else None
        self._tts_model_name = tts_model if isinstance(tts_model, str) else None
        self.config = config or VoicePipelineConfig()
        
    async def run(self, audio_input: AudioInput | StreamedAudioInput) -> StreamedAudioResult:
        if isinstance(audio_input, AudioInput):
            return await self._run_single_turn(audio_input)
        elif isinstance(audio_input, StreamedAudioInput):
            return await self._run_multi_turn(audio_input)

    async def _run_single_turn(self, audio_input: AudioInput) -> StreamedAudioResult:
        with TraceCtxManager(
            workflow_name=self.config.workflow_name or "Voice Agent",
            trace_id=None,  # Automatically generated
            group_id=self.config.group_id,
            metadata=self.config.trace_metadata,
            disabled=self.config.tracing_disabled,
        ):
            input_text = await self._process_audio_input(audio_input)
            output = StreamedAudioResult(self._get_tts_model(), self.config.tts_settings, self.config)
            async def stream_events():
                try:
                    async for text_event in self.workflow.run(input_text):
                        await output._add_text(text_event)
                    await output._turn_done()
                    await output._done()
                except Exception as e:
                    await output._add_error(e)
                    raise e
            output._set_task(asyncio.create_task(stream_events()))
            return output

    async def _run_multi_turn(self, audio_input: StreamedAudioInput) -> StreamedAudioResult:
        with TraceCtxManager(...):
            output = StreamedAudioResult(self._get_tts_model(), self.config.tts_settings, self.config)
            transcription_session = await self._get_stt_model().create_session(...)
            async def process_turns():
                try:
                    async for input_text in transcription_session.transcribe_turns():
                        result = self.workflow.run(input_text)  # 这一部分同单轮: 文本流送入 TTS 模型
                        async for text_event in result:
                            await output._add_text(text_event)
                        await output._turn_done()
                except Exception as e:
                    await output._add_error(e)
                    raise e
                finally:
                    await transcription_session.close()
                    await output._done()
            output._set_task(asyncio.create_task(process_turns()))
            return output

    def _get_tts_model(self) -> TTSModel:
        self.tts_model = self.config.model_provider.get_tts_model(self._tts_model_name)
    def _get_stt_model(self) -> STTModel:
        self.stt_model = self.config.model_provider.get_stt_model(self._stt_model_name)


@dataclass
class VoicePipelineConfig:
    """Configuration for a `VoicePipeline`."""
    model_provider: VoiceModelProvider = field(default_factory=OpenAIVoiceModelProvider)
    tracing_disabled: bool = False
    trace_include_sensitive_data: bool = True
    trace_include_sensitive_audio_data: bool = True
    workflow_name: str = "Voice Agent"
    group_id: str = field(default_factory=gen_group_id)
    trace_metadata: dict[str, Any] | None = None
    stt_settings: STTModelSettings = field(default_factory=STTModelSettings)
    tts_settings: TTSModelSettings = field(default_factory=TTSModelSettings)



""" --------------------------------------------------------------------------------------
src/agents/voice/model.py

建模 SST/TTS 模型
1. STTModel -- 在session模式下, 类似提供了一个 stream
    transcribe(input: AudioInput) -> str 处理单轮音频输入
    create_session(input: StreamedAudioInput) -> StreamedTranscriptionSession
        同步函数, 提供 transcribe_turns() -> AsyncIterator[str] 来获取转录文本流
        配置项: turn_detection: dict[str, Any]
2. TTSModel
    run(text: str) -> AsyncIterator[bytes]
    配置项: buffer_size 缓存输出; text_splitter 分割输入文本
-------------------------------------------------------------------------------------- """
DEFAULT_TURN_DETECTION = {"type": "semantic_vad"}
@dataclass
class STTModelSettings:
    """Settings for a speech-to-text model."""
    prompt: str | None = None
    language: str | None = None
    temperature: float | None = None
    turn_detection: dict[str, Any] | None = None
    """The turn detection settings for the model when using streamed audio input."""

class STTModel(abc.ABC):
    """A speech-to-text model that can convert audio input into text."""
    @property
    def model_name(self) -> str:
        """The name of the STT model."""
    
    @abc.abstractmethod
    async def transcribe(
        self,
        input: AudioInput,
        settings: STTModelSettings,
        trace_include_sensitive_data: bool,
        trace_include_sensitive_audio_data: bool,
    ) -> str:
        """Given an audio input, produces a text transcription."""

    @abc.abstractmethod
    async def create_session(self) -> StreamedTranscriptionSession:
        """Creates a new transcription session, which you can push audio to, and receive a stream of text transcriptions."""

class StreamedTranscriptionSession(abc.ABC):
    """A streamed transcription of audio input."""
    @abc.abstractmethod
    def transcribe_turns(self) -> AsyncIterator[str]:
        """Yields a stream of text transcriptions. Each transcription is a turn in the conversation."""
    @abc.abstractmethod
    async def close(self) -> None:
        """Closes the session."""


class TTSModel(abc.ABC):
    @property
    def model_name(self) -> str:
        """The name of the TTS model."""
    @abc.abstractmethod
    def run(self, text: str, settings: TTSModelSettings) -> AsyncIterator[bytes]:
        """Given a text string, produces a stream of audio bytes, in PCM format."""

TTSVoice = Literal["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]
@dataclass
class TTSModelSettings:
    voice: TTSVoice | None = None
    buffer_size: int = 120
    """The minimal size of the chunks of audio data that are being streamed out."""
    dtype: npt.DTypeLike = np.int16
    transform_data: Callable[[npt.NDArray[np.int16 | np.float32]], npt.NDArray[np.int16 | np.float32]] | None
    # A function to transform the data from the TTS model. This is useful if you want the resulting audio stream to have the data in a specific shape already.
    instructions: str = "You will receive partial sentences. Do not complete the sentence just read out the text."
    text_splitter: Callable[[str], tuple[str, str]] = get_sentence_based_splitter()  # 对于输入的文本流, 默认按照句子级别划分
    speed: float | None = None
    """The speed with which the TTS model will read the text. Between 0.25 and 4.0."""

class VoiceModelProvider(abc.ABC):
    @abc.abstractmethod
    def get_stt_model(self, model_name: str | None) -> STTModel: ...
    @abc.abstractmethod
    def get_tts_model(self, model_name: str | None) -> TTSModel: ...



""" --------------------------------------------------------------------------------------
src/agents/voice/workflow.py 抽象文本 -> 文本的处理工作流

- VoiceWorkflowBase: 基础, 仅仅提供:
    run(self, transcription: str) -> AsyncIterator[str] 接口
- SingleAgentVoiceWorkflow: 注意这里的 "single" 指的是单 Runner.run_streamed(), 可以是 agents 
-------------------------------------------------------------------------------------- """
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
    def run(self, transcription: str) -> AsyncIterator[str]:
        """
        Run the voice workflow. You will receive an input transcription, and must yield text that
        will be spoken to the user. You can run whatever logic you want here. In most cases, the
        final logic will involve calling `Runner.run_streamed()` and yielding any text events from
        the stream.
        """

class SingleAgentVoiceWorkflow(VoiceWorkflowBase):
    """A simple voice workflow that runs a single agent. Each transcription and result is added to
    the input history.
    For more complex workflows (e.g. multiple Runner calls, custom message history, custom logic,
    custom configs), subclass `VoiceWorkflowBase` and implement your own logic.
    """
    def __init__(self, agent: Agent[Any], callbacks: SingleAgentWorkflowCallbacks | None = None):
        """Create a new single agent voice workflow."""
        self._input_history: list[TResponseInputItem] = []
        self._current_agent = agent
        self._callbacks = callbacks
        
    async def run(self, transcription: str) -> AsyncIterator[str]:
        self._callbacks.on_run(self, transcription)
        # Add the transcription to the input history
        self._input_history.append({"role": "user", "content": transcription})
        # Run the agent
        result = Runner.run_streamed(self._current_agent, self._input_history)
        # Stream the text from the result
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            yield chunk
        # Update the input history and current agent
        self._input_history = result.to_input_list()
        self._current_agent = result.last_agent
        
class SingleAgentWorkflowCallbacks:
    def on_run(self, workflow: SingleAgentVoiceWorkflow, transcription: str) -> None:
        """Called when the workflow is run."""
        
class VoiceWorkflowHelper:
    @classmethod
    async def stream_text_from(cls, result: RunResultStreaming) -> AsyncIterator[str]:
        """Wraps a `RunResultStreaming` object and yields text events from the stream."""

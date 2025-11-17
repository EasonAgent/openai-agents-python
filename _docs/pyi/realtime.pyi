from typing import Union, Literal
from typing_extensions import NotRequired, TypeAlias, TypedDict

# config
RealtimeAudioFormat: TypeAlias = Union[Literal["pcm16", "g711_ulaw", "g711_alaw"], str]
"""The audio format for realtime audio streams."""


# src/agents/realtime/model.py
class RealtimePlaybackTracker:
    """If you have custom playback logic or expect that audio is played with delays or at different
    speeds, create an instance of RealtimePlaybackTracker and pass it to the session. You are
    responsible for tracking the audio playback progress and calling `on_play_bytes` or
    `on_play_ms` when the user has played some audio."""
    def __init__(self) -> None:
        self._format: RealtimeAudioFormat | None = None
        self._current_item: tuple[str, int] | None = None
        self._elapsed_ms: float | None = None
    def on_play_bytes(self, item_id: str, item_content_index: int, bytes: bytes) -> None:
        """Called by you when you have played some audio."""
    def on_play_ms(self, item_id: str, item_content_index: int, ms: float) -> None:
        """Called by you when you have played some audio."""
    def on_interrupted(self) -> None:
        """Called by the model when the audio playback has been interrupted."""
        self._current_item = None
        self._elapsed_ms = None
    def set_audio_format(self, format: RealtimeAudioFormat) -> None:
        """Will be called by the model to set the audio format."""
    def get_state(self) -> RealtimePlaybackState:
        """Will be called by the model to get the current playback state."""
        item_id, item_content_index = self._current_item
        return {
            "current_item_id": item_id,
            "current_item_content_index": item_content_index,
            "elapsed_ms": self._elapsed_ms,
        }

class RealtimePlaybackState(TypedDict):
    current_item_id: str | None
    """The item ID of the current item being played."""
    current_item_content_index: int | None
    """The index of the current item content being played."""
    elapsed_ms: float | None
    """The number of milliseconds of audio that have been played."""
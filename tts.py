from elevenlabs.client import ElevenLabs
from config import (
    ELEVENLABS_API_KEY,
    DEFAULT_VOICE_ID,
    DEFAULT_MODEL_ID,
    DEFAULT_OUTPUT_FORMAT,
    AUDIO_TMP_PATH,
)

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


def synthesize(text: str, voice_id: str = DEFAULT_VOICE_ID) -> str:
    """Generate speech and write to temp file. Returns file path."""
    stream = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=DEFAULT_MODEL_ID,
        output_format=DEFAULT_OUTPUT_FORMAT,
    )
    with open(AUDIO_TMP_PATH, "wb") as f:
        for chunk in stream:
            if chunk:
                f.write(chunk)
    return AUDIO_TMP_PATH


def list_voices() -> list[dict]:
    """Return available voices from ElevenLabs."""
    response = client.voices.get_all()
    return [
        {"voice_id": v.voice_id, "name": v.name}
        for v in response.voices
    ]

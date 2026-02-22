import os

from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

# Default voice: "George" — natural, conversational
DEFAULT_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

# eleven_turbo_v2_5 for low latency; eleven_multilingual_v2 for quality
DEFAULT_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")

DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
AUDIO_TMP_PATH = "/tmp/talk_mcp_speech.mp3"

# PipeWire sink name — None = system default
PIPEWIRE_SINK = os.environ.get("PIPEWIRE_SINK", None)

# Fallback player: "pw-play" | "afplay" | "mpg123"
AUDIO_PLAYER = os.environ.get("AUDIO_PLAYER", "pw-play")

# Directory for audio files (samples, clips, etc.)
AUDIO_FILES_DIR = os.environ.get("AUDIO_FILES_DIR") or os.path.join(os.path.dirname(__file__), "sample-audio")

# MCP transport: "stdio" (local) or "http" (remote)
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

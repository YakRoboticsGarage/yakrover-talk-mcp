# talk-mcp — Implementation Plan

A voice-output MCP server powered by ElevenLabs. The LLM speaks back using natural, human-like keypoints — not verbatim responses.

---

## Goal

Build `talk-mcp`: an MCP server that:
1. Receives a full LLM response
2. Distills it into spoken keypoints (via LLM system prompt instructions)
3. Sends those keypoints to ElevenLabs TTS
4. Plays audio through a configured output device (HomePod via PipeWire, or any sink)

---

## Project Structure

```
talk-mcp/
├── server.py                        # FastMCP server, tool definitions
├── prompts.py                       # SPOKEN_KEYPOINTS_SYSTEM_PROMPT constant
├── tts.py                           # ElevenLabs synthesis helper
├── audio.py                         # Audio playback via pw-play (with delete flag)
├── config.py                        # Env vars and defaults (incl. AUDIO_FILES_DIR)
├── pyproject.toml                   # Dependencies and entry point
├── sample-audio/
│   ├── template-example.json       # Example template format (tracked in git)
│   ├── templates.json              # Your actual templates (gitignored)
│   └── *.mp3                       # Audio files (gitignored)
├── scripts/
│   ├── setup-homepod.sh            # One-time PipeWire + firewall setup for HomePod
│   └── audio-sink.sh               # Connect/disconnect audio sinks via WirePlumber
└── docs/plan.md                     # This file
```

---

## Core Design: The "Speak in Keypoints" Instruction

The most important part of talk-mcp is telling the LLM **how** to convert its response to speech. This lives as an MCP prompt resource and/or tool description.

### System Prompt for Spoken Output

```
When preparing text to be spoken aloud, follow these rules:

1. Extract only the key points from your response — not the full text.
2. Use short, natural spoken sentences. Max 2 sentences per point.
3. No markdown, no lists, no bullet symbols, no code blocks.
4. Speak like a person giving a quick verbal summary, not reading a document.
5. Aim for 3–5 spoken sentences total. If the answer is simple, 1–2 sentences is fine.
6. Never say "In summary" or "To summarize". Just say the point.
7. Use natural connectors: "Also,", "One thing to note:", "The main idea is", "Keep in mind that"

Example — Full LLM response:
  "The ESP32-S3 supports Wi-Fi 802.11 b/g/n and Bluetooth 5.0 LE.
   It has 512KB SRAM and up to 16MB flash. It's well-suited for IoT
   applications requiring both wireless protocols..."

Spoken keypoints output:
  "The ESP32-S3 has both Wi-Fi and Bluetooth 5 built in.
   It's got plenty of memory for most IoT projects.
   Solid choice if you need both wireless protocols on one chip."
```

This prompt should be embedded in the tool's docstring AND optionally exposed as an MCP prompt resource so Claude Code can reference it directly.

---

## MCP Tools

### `speak(text: str) -> str`
Primary TTS tool. The LLM distills the response into keypoints before calling this.

Language rules (enforced in docstring):
- Only for **English** text — ElevenLabs does not handle Hinglish
- If the reply is Hinglish/Hindi → reply as text, do NOT call `speak()`
- If context fits a Gabbar/Sholay template → use `play_template()` instead

### `speak_raw(text: str) -> str`
Bypass distillation — speak exactly what's passed. For short confirmations only.

### `set_voice(voice_id: str) -> str`
Change the ElevenLabs voice at runtime.

### `list_voices() -> str`
Returns available voices from the ElevenLabs API.

### `list_samples() -> str`
Lists audio files in the configured `AUDIO_FILES_DIR`.

### `play_sample(filename: str) -> str`
Plays an audio file by filename. Does not delete the file after playback.

### `list_templates() -> str`
Lists reply templates from `templates.json`. Each template has a name, file, and description. The LLM reads descriptions to decide when to play each template.

### `play_template(name: str) -> str`
Plays a pre-recorded template by name. **Always prefer over `speak()`** when:
- User mentions "gabbar" or Sholay
- Context matches a template description
- Reply would be in Hinglish

---

## MCP Prompt Resource

Expose the keypoints instruction as a named prompt so Claude Code can call it explicitly:

```python
@mcp.prompt()
def spoken_keypoints_prompt() -> str:
    """Returns the system instructions for converting LLM responses to spoken keypoints."""
    return SPOKEN_KEYPOINTS_SYSTEM_PROMPT  # from prompts.py
```

---

## Config (`config.py`)

```python
import os

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

# Directory for sample audio files and templates
AUDIO_FILES_DIR = os.environ.get("AUDIO_FILES_DIR", os.path.join(os.path.dirname(__file__), "sample-audio"))

# MCP transport: "stdio" (local) or "http" (remote)
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))
```

---

## TTS Helper (`tts.py`)

```python
from elevenlabs.client import ElevenLabs
from config import DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, DEFAULT_OUTPUT_FORMAT, AUDIO_TMP_PATH

client = ElevenLabs()

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
```

---

## Audio Playback (`audio.py`)

```python
import subprocess, os
from config import PIPEWIRE_SINK, AUDIO_PLAYER, AUDIO_TMP_PATH

def play(audio_path: str = AUDIO_TMP_PATH, delete: bool = True):
    cmd = [AUDIO_PLAYER]
    if AUDIO_PLAYER == "pw-play" and PIPEWIRE_SINK:
        cmd.extend(["--target", PIPEWIRE_SINK])
    cmd.append(audio_path)
    subprocess.run(cmd, check=True)
    if delete and os.path.exists(audio_path):
        os.remove(audio_path)
```

---

## Dependencies (`pyproject.toml`)

```toml
[project]
name = "talk-mcp"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
  "mcp[cli]",
  "fastmcp",
  "elevenlabs>=1.0.0",
]

[project.scripts]
talk-mcp = "server:main"
```

Install:
```bash
uv venv && uv pip install -e .
```

---

## Transport Modes

The server supports two transports via `MCP_TRANSPORT` env var:

| Mode | Transport | When to use |
|---|---|---|
| Local | `stdio` (default) | Claude Code on the same machine |
| Remote | `http` | Claude Code on a different machine (e.g. laptop → desktop) |

> **Note:** The old `sse` transport (MCP spec 2024-11-05) is deprecated. Use `http` (Streamable HTTP, MCP spec 2025-06-18) for all remote deployments. FastMCP exposes this at `/mcp`.

---

## Audio Reply Templates

Pre-recorded audio clips played instead of TTS for specific contexts (Hinglish, Gabbar references, etc.).

### Setup

1. Copy example: `cp sample-audio/template-example.json sample-audio/templates.json`
2. Add `.mp3` files to `sample-audio/`
3. Edit `templates.json` — map template names to files with descriptions

### Format

```json
{
  "template-name": {
    "file": "audio-file.mp3",
    "description": "When to play this. The LLM reads this to decide."
  }
}
```

The description is the instruction surface — write it as a clear directive for the LLM.

### Git tracking

- `template-example.json` — tracked (shows format)
- `templates.json` — gitignored (actual templates)
- `*.mp3` — gitignored (audio files)

---

## Language Routing

| Language/Context | Action |
|---|---|
| English | Use `speak()` (ElevenLabs TTS) |
| Hinglish / Hindi | Reply as text only — do NOT call `speak()` |
| Gabbar / Sholay references | Use `play_template()` |
| Template matches context | Prefer `play_template()` over `speak()` |

These rules are enforced via tool docstrings in `server.py`.

---

## Scripts

### `scripts/setup-homepod.sh`
One-time PipeWire RAOP discovery and firewall setup for HomePod. Prompts for HomePod IP, configures UFW, writes `raop-discover.conf`, restarts wireplumber+pipewire, discovers sinks.

### `scripts/audio-sink.sh`
Connect/disconnect audio sinks via WirePlumber (`wpctl`). Commands: `list`, `status`, `connect`, `disconnect`.

---

## Claude Code MCP Config

Add to your Claude Code MCP config (`~/.claude/claude_desktop_config.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "talk-mcp": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/path/to/talk-mcp",
      "env": {
        "ELEVENLABS_API_KEY": "your_key_here",
        "ELEVENLABS_VOICE_ID": "JBFqnCBsd6RMkjVDRZzb",
        "PIPEWIRE_SINK": "your_homepod_sink_name",
        "AUDIO_PLAYER": "pw-play"
      }
    }
  }
}
```

---

## Build Order

Follow this sequence — later files import from earlier ones:

1. `config.py` — env vars and defaults
2. `prompts.py` — the keypoints system prompt string
3. `tts.py` — ElevenLabs synthesis helper
4. `audio.py` — playback via pw-play
5. `server.py` — FastMCP server wiring everything together
6. `pyproject.toml` — deps and entry point

---

## Behaviour Notes

- The `speak()` tool docstring is the primary instruction surface. Claude Code reads tool descriptions, so the distillation rule lives there.
- `speak_raw()` is the escape hatch for confirmations ("Starting now.", "Done.").
- Keep `eleven_turbo_v2_5` as the default model for low latency. Switch to `eleven_multilingual_v2` if voice quality matters more than speed.
- Find your HomePod's PipeWire sink with: `pw-cli list-objects | grep -A5 "node.name"`
- Use `scripts/audio-sink.sh list` to see available sinks.

---

## Future Extensions

- **STT input**: Add a `listen()` tool using Whisper or ElevenLabs STT so it's a full voice loop
- **Interrupt**: `stop_speaking()` tool that kills the current pw-play subprocess
- **Voice profiles**: Named presets (e.g., `"narrator"`, `"assistant"`) mapped to voice IDs
- **Streaming TTS**: Stream audio chunks directly instead of writing to tmp file for lower latency
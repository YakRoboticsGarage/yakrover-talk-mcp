# talk-mcp — CLAUDE.md

Voice-output MCP server. Converts LLM responses into natural spoken keypoints via ElevenLabs TTS, played through PipeWire (or any configured audio sink).

---

## Project Layout

```
talk-mcp/
├── server.py                        # FastMCP server, tool definitions
├── prompts.py                       # SPOKEN_KEYPOINTS_SYSTEM_PROMPT constant
├── tts.py                           # ElevenLabs synthesis helper
├── audio.py                         # Audio playback via pw-play / afplay / mpg123
├── config.py                        # Env vars and defaults
├── pyproject.toml                   # Dependencies and entry point
├── mcp-example.json                 # Example MCP config (local + remote)
├── sample-audio/
│   ├── template-example.json       # Example template format (tracked in git)
│   ├── templates.json              # Your actual templates (gitignored)
│   └── *.mp3                       # Audio files (gitignored)
├── scripts/
│   ├── setup-homepod.sh            # One-time PipeWire + firewall setup for HomePod
│   └── audio-sink.sh               # Connect/disconnect audio sinks
└── docs/plan.md                     # Full design spec
```

---

## Build Order

Always implement in this sequence — later files import from earlier ones:

1. `config.py`
2. `prompts.py`
3. `tts.py`
4. `audio.py`
5. `server.py`
6. `pyproject.toml`

---

## Config (`config.py`)

```python
import os

ELEVENLABS_API_KEY   = os.environ.get("ELEVENLABS_API_KEY")
DEFAULT_VOICE_ID     = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
DEFAULT_MODEL_ID     = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
AUDIO_TMP_PATH       = "/tmp/talk_mcp_speech.mp3"
PIPEWIRE_SINK        = os.environ.get("PIPEWIRE_SINK", None)
AUDIO_PLAYER         = os.environ.get("AUDIO_PLAYER", "pw-play")
AUDIO_FILES_DIR      = os.environ.get("AUDIO_FILES_DIR", os.path.join(os.path.dirname(__file__), "sample-audio"))
MCP_TRANSPORT        = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST             = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT             = int(os.environ.get("MCP_PORT", "8000"))
```

- Default voice: **George** (`JBFqnCBsd6RMkjVDRZzb`) — conversational, natural
- Default model: `eleven_turbo_v2_5` (low latency). Switch to `eleven_multilingual_v2` for quality.

---

## Spoken Keypoints Prompt (`prompts.py`)

The `SPOKEN_KEYPOINTS_SYSTEM_PROMPT` constant drives distillation. Rules:

1. Extract only key points — not the full text
2. Short, natural spoken sentences — max 2 sentences per point
3. No markdown, no lists, no bullet symbols, no code blocks
4. 3–5 sentences total; 1–2 if the answer is simple
5. Never say "In summary" or "To summarize"
6. Use natural connectors: "Also,", "One thing to note:", "The main idea is", "Keep in mind that"

Expose this as an MCP prompt resource via `@mcp.prompt()` so Claude Code can reference it.

---

## TTS Helper (`tts.py`)

```python
from elevenlabs.client import ElevenLabs
from config import DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, DEFAULT_OUTPUT_FORMAT, AUDIO_TMP_PATH

client = ElevenLabs()

def synthesize(text: str, voice_id: str = DEFAULT_VOICE_ID) -> str:
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

Deletes the temp file after playback by default. Pass `delete=False` for sample/template files.

---

## Transport Modes

The server supports two transports, selected via the `MCP_TRANSPORT` env var:

| Mode | Transport | When to use |
|---|---|---|
| Local | `stdio` (default) | Claude Code on the same machine |
| Remote | `http` | Claude Code on a different machine (e.g. laptop → desktop) |

> **Note:** The old `sse` transport (HTTP+SSE, MCP spec 2024-11-05) is deprecated. Use `http` (Streamable HTTP, MCP spec 2025-06-18) for all remote deployments. FastMCP exposes this at `/mcp`.

### `server.py` entry point

```python
import os
from fastmcp import FastMCP

mcp = FastMCP("talk-mcp")

# ... tool definitions ...

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(
            transport="http",
            host=os.environ.get("MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("MCP_PORT", "8000")),
        )
    else:
        mcp.run()  # stdio
```

### Local config (`.mcp.json`)

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

### Remote config (`.mcp.json` on the client machine)

```json
{
  "mcpServers": {
    "talk-mcp": {
      "url": "http://<server-ip>:8000/mcp"
    }
  }
}
```

Start the remote server on the machine with the HomePod. Set these in `.env`:

```env
ELEVENLABS_API_KEY=your_key
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000
```

Then run:

```bash
uv run python server.py
```

The server loads `.env` automatically via `python-dotenv`.

> **Note:** The HTTP server has no auth by default — run it on a trusted local network only, or put it behind a reverse proxy with auth.

---

## MCP Tools (`server.py`)

### `speak(text: str) -> str`

Primary TTS tool. The docstring **is** the instruction surface — Claude reads it.

**Language rules** (enforced in docstring):
- Only use for **English** text — ElevenLabs does not handle Hinglish well
- If the reply is Hinglish/Hindi, do NOT call `speak()` — reply as text instead
- If the context fits a Gabbar/Sholay template, use `play_template()` instead

### `speak_raw(text: str) -> str`

Bypass distillation. Use only for short confirmations ("Got it.", "Done.", "Starting now.").

### `set_voice(voice_id: str) -> str`

Change the ElevenLabs voice at runtime.

### `list_voices() -> str`

Returns available voices from the ElevenLabs API.

### `list_samples() -> str`

Lists audio files in `AUDIO_FILES_DIR`.

### `play_sample(filename: str) -> str`

Plays an audio file by filename from `AUDIO_FILES_DIR`. Does not delete the file.

### `list_templates() -> str`

Lists reply templates from `templates.json`. Each template has a name, audio file, and description of when to use it. Check templates before using `speak()`.

### `play_template(name: str) -> str`

Plays a pre-recorded reply template by name. **Always prefer over `speak()`** when:
- User mentions "gabbar" or references Sholay
- Context matches a template description
- Reply would be in Hinglish — templates handle this natively

---

## MCP Prompt Resource

```python
@mcp.prompt()
def spoken_keypoints_prompt() -> str:
    """Returns the system instructions for converting LLM responses to spoken keypoints."""
    return SPOKEN_KEYPOINTS_SYSTEM_PROMPT
```

---

## Audio Reply Templates

Pre-recorded audio clips that the LLM can play in response to specific situations (Hinglish replies, Gabbar references, etc.) instead of using ElevenLabs TTS.

### Setup

1. Copy the example to create your own templates:
   ```bash
   cp sample-audio/template-example.json sample-audio/templates.json
   ```
2. Add your `.mp3` files to `sample-audio/`
3. Edit `templates.json` — map each template name to a file and description

### Template format (`templates.json`)

```json
{
  "template-name": {
    "file": "audio-file.mp3",
    "description": "When to play this. The LLM reads this to decide."
  }
}
```

The **description** is the instruction surface — the LLM reads it to decide when to play the template. Write it as a clear directive.

### Git tracking

- `sample-audio/template-example.json` — tracked in git (shows format with generic examples)
- `sample-audio/templates.json` — **gitignored** (your actual templates with real audio mappings)
- `sample-audio/*.mp3` — **gitignored** (audio files stay local)

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

Install: `uv venv && uv pip install -e .`

---

## HomePod Setup

Run the setup script once to configure PipeWire RAOP discovery and firewall rules:

```bash
bash scripts/setup-homepod.sh
```

It will:
1. Add UFW rules for the HomePod IP and AirPlay mDNS (5353/udp)
2. Write `~/.config/pipewire/pipewire.conf.d/raop-discover.conf`
3. Restart `wireplumber` and `pipewire`
4. Wait 10 s and print available sinks — copy the `raop` sink name from the output

Then set `PIPEWIRE_SINK` in your MCP config (see below) or export it:

```bash
export PIPEWIRE_SINK="<raop-sink-name-from-output>"
```

Manual sink discovery if needed:

```bash
pw-cli list-objects | grep -E "node.name|media.class" | grep -B1 "Audio/Sink"
```

---

## Key Design Rules

- **`speak()` docstring is the primary instruction surface.** Keep it clear and imperative.
- **`speak_raw()` is the escape hatch** — short strings only.
- **Low latency first**: keep `eleven_turbo_v2_5` unless quality complaints arise.
- **No runtime distillation in server code** — the LLM does the distillation before calling `speak()`. The server just synthesizes and plays.
- Use `fastmcp` (not raw `mcp`) for the server.

### Language Routing

| Language/Context | Action |
|---|---|
| English | Use `speak()` (ElevenLabs TTS) |
| Hinglish / Hindi | Reply as text only — do NOT call `speak()` |
| Gabbar / Sholay references | Use `play_template()` — never synthesize via ElevenLabs |
| Template matches any context | Prefer `play_template()` over `speak()` |

These rules are enforced via tool docstrings in `server.py`.

---

## ElevenLabs Python SDK Reference

- Full docs: https://elevenlabs.io/docs/llms-full.txt
- Python SDK: https://elevenlabs.io/docs/eleven-agents/libraries/python

Key methods used in `tts.py`:
- `client.text_to_speech.convert(text, voice_id, model_id, output_format)` — returns audio chunk generator
- `client.text_to_speech.stream(...)` — streaming variant (future use)
- `client.voices.get_all()` — list available voices

Models: `eleven_turbo_v2_5` (default, low latency), `eleven_multilingual_v2` (quality), `eleven_flash_v2_5` (ultra-low latency)

Formats: `mp3_44100_128` (default), `mp3_44100_192`, `pcm_16000`, `ulaw_8000`

---

## Audio Sink Management

Use `scripts/audio-sink.sh` to manage PipeWire audio sinks (connect/disconnect HomePod):

```bash
bash scripts/audio-sink.sh list        # List available sinks
bash scripts/audio-sink.sh status      # Show current default sink
bash scripts/audio-sink.sh connect     # Set a sink as default output
bash scripts/audio-sink.sh disconnect  # Switch away from HomePod to a local sink
```

---

## Future Extensions (not in scope now)

- `listen()` — STT via Whisper or ElevenLabs STT
- `stop_speaking()` — kill current pw-play subprocess
- Voice profiles (named presets mapped to voice IDs)
- Streaming TTS (chunk audio directly, skip temp file)

# talk-mcp

A voice-output MCP server powered by ElevenLabs. Converts LLM responses into natural spoken keypoints, played through PipeWire to any audio sink — including HomePod via AirPlay.

## Architecture

```
┌─────────────────────┐         ┌──────────────────────────────────────┐
│   Client Machine    │         │   Server Machine (with speakers)     │
│                     │         │                                      │
│  ┌───────────────┐  │  MCP    │  ┌───────────┐    ┌──────────────┐  │
│  │  Claude Code  │──┼────────►│  │ server.py │───►│   tts.py     │  │
│  └───────────────┘  │ stdio   │  │ (FastMCP) │    └──────┬───────┘  │
│         │           │  or     │  └─────┬─────┘           │          │
│  ┌──────▼────────┐  │ http    │        │           ┌─────▼────────┐ │
│  │  .mcp.json    │  │         │        │           │ ElevenLabs   │ │
│  └───────────────┘  │         │        ▼           │ API          │ │
│                     │         │  ┌───────────┐     └──────────────┘ │
│  Transport:         │         │  │ audio.py  │◄── templates.json   │
│   • stdio (local)   │         │  └─────┬─────┘                     │
│   • http  (remote)  │         │        │                            │
│                     │         │  ┌─────▼─────┐   ┌──────────────┐  │
│                     │         │  │  pw-play   │──►│  PipeWire    │  │
│                     │         │  └───────────┘   └──────┬───────┘  │
│                     │         │                         │          │
│                     │         │                  ┌──────▼───────┐  │
│                     │         │                  │   HomePod    │  │
│                     │         │                  │ (AirPlay)    │  │
│                     │         │                  └──────────────┘  │
└─────────────────────┘         └──────────────────────────────────────┘
```

[View interactive diagram on Excalidraw](https://excalidraw.com/#json=ZhW_onaVdHn61Bh4M9AY7,VgSBFNjDm5DERGFAlyKMFg)

## How It Works

1. Claude Code calls MCP tools (`speak`, `play_template`, etc.) via stdio or HTTP
2. `server.py` routes the request — either to ElevenLabs TTS or to a pre-recorded template
3. `audio.py` plays the audio through PipeWire using `pw-play`
4. PipeWire routes audio to the configured sink (HomePod via AirPlay/RAOP, or local speakers)

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [PipeWire](https://pipewire.org/) (audio system — default on most modern Linux)
- [ElevenLabs](https://elevenlabs.io/) API key
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI)

## Setup

### 1. Clone and install

```bash
git clone git@github.com:YakRoboticsGarage/yakrover-talk-mcp.git
cd yakrover-talk-mcp
uv venv && uv pip install -e .
```

### 2. Get an ElevenLabs API key

1. Sign up at [elevenlabs.io](https://elevenlabs.io/)
2. Go to **Profile + API key** (bottom-left) → copy your API key

### 3. Create your `.env` file

The server loads `.env` automatically via `python-dotenv` — no need to `source` it.

```env
# Required
ELEVENLABS_API_KEY=your_key_here

# Transport (uncomment for remote server mode)
# MCP_TRANSPORT=http
# MCP_HOST=0.0.0.0
# MCP_PORT=8000

# Audio (optional)
# AUDIO_PLAYER=pw-play
# PIPEWIRE_SINK=your_sink_name
# AUDIO_FILES_DIR=/path/to/sample-audio
```

### 4. Set up audio templates (optional)

```bash
cp sample-audio/template-example.json sample-audio/templates.json
```

Edit `templates.json` and add your `.mp3` files to `sample-audio/`. See [Template Format](#audio-reply-templates) below.

### 5. Set up HomePod as audio sink (optional)

If you want audio to play through a HomePod:

```bash
bash scripts/setup-homepod.sh
```

This configures PipeWire RAOP discovery, firewall rules, and prints available sinks. Then manage your audio sink:

```bash
bash scripts/audio-sink.sh list        # List available sinks
bash scripts/audio-sink.sh connect     # Set a sink as default
bash scripts/audio-sink.sh status      # Show current default
bash scripts/audio-sink.sh disconnect  # Switch to local speakers
```

## Running the Server

### Option A: Local (stdio) — same machine as Claude Code

Create `.mcp.json` in the project root (or copy from `mcp-example.json`):

```json
{
  "mcpServers": {
    "talk-mcp": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/path/to/talk-mcp",
      "env": {
        "ELEVENLABS_API_KEY": "your_key_here",
        "AUDIO_PLAYER": "pw-play"
      }
    }
  }
}
```

Claude Code will start the server automatically when you open a session in this directory.

### Option B: Remote (HTTP) — server on a different machine

Use this when Claude Code runs on your laptop but audio should play on a desktop/server with speakers or HomePod.

#### Step 1: Find the server's local IP

On the server machine (the one with speakers):

```bash
# Linux
hostname -I | awk '{print $1}'

# macOS
ipconfig getifaddr en0
```

Example output: `192.168.1.42`

#### Step 2: Configure `.env` for remote mode

On the server machine, edit `.env` to enable HTTP transport:

```env
ELEVENLABS_API_KEY=your_key_here
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000
```

#### Step 3: Start the server

```bash
cd /path/to/talk-mcp
uv run python server.py
```

You should see the server start and listen on `http://0.0.0.0:8000/mcp` (Streamable HTTP, MCP spec 2025-06-18).

#### Step 4: Verify the server is reachable

From your client machine (laptop), confirm you can reach it:

```bash
curl http://192.168.1.42:8000/mcp
```

You should get a response (not a connection refused error).

#### Step 5: Configure Claude Code on the client

On the client machine, create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "talk-mcp": {
      "url": "http://192.168.1.42:8000/mcp"
    }
  }
}
```

Replace `192.168.1.42` with your server's actual IP.

#### Step 6: Open Claude Code

Start a new Claude Code session in the directory with `.mcp.json`. It will connect to the remote talk-mcp server automatically. Any `speak()` or `play_template()` calls will play audio on the server machine.

> **Note:** The HTTP server has no auth by default — run it on a trusted local network only, or put it behind a reverse proxy with auth.
>
> **Tip:** If the connection is refused, check that no firewall is blocking port 8000 on the server: `sudo ufw allow 8000/tcp`

## MCP Tools

| Tool | Description |
|---|---|
| `speak(text)` | Distill text into spoken keypoints and play via ElevenLabs TTS. English only. |
| `speak_raw(text)` | Speak text exactly as provided. For short confirmations only. |
| `set_voice(voice_id)` | Change the ElevenLabs voice at runtime. |
| `list_voices()` | List available ElevenLabs voices. |
| `list_samples()` | List audio files in the audio directory. |
| `play_sample(filename)` | Play an audio file by filename. |
| `list_templates()` | List reply templates and when to use them. |
| `play_template(name)` | Play a pre-recorded template by name. |

### Language Routing

The tools enforce language-aware routing via their docstrings:

| Context | Action |
|---|---|
| English replies | `speak()` — ElevenLabs TTS |
| Hinglish / Hindi | Text reply only — no TTS |
| Template matches | `play_template()` — pre-recorded audio |

## Audio Reply Templates

Templates are pre-recorded audio clips played instead of TTS for specific contexts.

### Template format (`sample-audio/templates.json`)

```json
{
  "greeting": {
    "file": "greeting.mp3",
    "description": "A friendly greeting. Use when the user says hello."
  },
  "victory": {
    "file": "victory.mp3",
    "description": "A celebration sound. Use when a task completes successfully."
  }
}
```

The `description` is what the LLM reads to decide when to play each template — write it as a clear directive.

### Git tracking

| File | Tracked | Notes |
|---|---|---|
| `template-example.json` | Yes | Example format — copy this to get started |
| `templates.json` | No (gitignored) | Your actual templates |
| `*.mp3` | No (gitignored) | Audio files stay local |

## Project Structure

```
talk-mcp/
├── server.py                  # FastMCP server, tool definitions
├── config.py                  # Environment variables and defaults
├── prompts.py                 # Spoken keypoints system prompt
├── tts.py                     # ElevenLabs synthesis helper
├── audio.py                   # Audio playback via pw-play
├── pyproject.toml             # Dependencies and entry point
├── mcp-example.json           # Example MCP config (local + remote)
├── sample-audio/
│   ├── template-example.json  # Example template format
│   ├── templates.json         # Your templates (gitignored)
│   └── *.mp3                  # Audio files (gitignored)
├── scripts/
│   ├── setup-homepod.sh       # One-time HomePod/PipeWire setup
│   └── audio-sink.sh          # Audio sink management
└── docs/
    └── plan.md                # Design spec
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ELEVENLABS_API_KEY` | — | ElevenLabs API key (required) |
| `ELEVENLABS_VOICE_ID` | `JBFqnCBsd6RMkjVDRZzb` | Voice ID (default: George) |
| `ELEVENLABS_MODEL_ID` | `eleven_turbo_v2_5` | TTS model (low latency) |
| `AUDIO_PLAYER` | `pw-play` | Audio player command |
| `PIPEWIRE_SINK` | system default | PipeWire sink target |
| `AUDIO_FILES_DIR` | `./sample-audio` | Directory for audio files and templates |
| `MCP_TRANSPORT` | `stdio` | Transport mode: `stdio` or `http` |
| `MCP_HOST` | `0.0.0.0` | HTTP server host (remote mode only) |
| `MCP_PORT` | `8000` | HTTP server port (remote mode only) |

## License

Apache 2.0 — see [LICENSE](LICENSE).

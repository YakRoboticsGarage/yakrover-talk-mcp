import json
import os

from fastmcp import FastMCP

import audio
import tts
from config import AUDIO_FILES_DIR, DEFAULT_VOICE_ID, MCP_HOST, MCP_PORT, MCP_TRANSPORT
from prompts import SPOKEN_KEYPOINTS_SYSTEM_PROMPT

mcp = FastMCP("talk-mcp")

_current_voice_id = DEFAULT_VOICE_ID


@mcp.tool()
def speak(text: str) -> str:
    """
    Converts text to natural spoken keypoints and plays them aloud via ElevenLabs.

    IMPORTANT: Before calling this tool, distill the response into 2–5 spoken
    keypoints using natural human language. Do NOT pass the full LLM response.
    Speak like a person giving a quick verbal update, not reading a document.
    No markdown, no bullet points, no code.

    LANGUAGE RULES:
    - Only use this tool for English text. ElevenLabs does not handle Hinglish well.
    - If the reply is in Hinglish or Hindi, do NOT call speak(). Just reply as text.
    - If the user mentions "gabbar" or the context fits a Gabbar template, use
      play_template() instead — never synthesize Gabbar lines via ElevenLabs.
    """
    path = tts.synthesize(text, voice_id=_current_voice_id)
    audio.play(path)
    return "Spoken."


@mcp.tool()
def speak_raw(text: str) -> str:
    """
    Speaks the given text exactly as provided, without distillation.
    Use only for short confirmations or single-sentence responses.
    """
    path = tts.synthesize(text, voice_id=_current_voice_id)
    audio.play(path)
    return "Spoken."


@mcp.tool()
def set_voice(voice_id: str) -> str:
    """Change the ElevenLabs voice at runtime."""
    global _current_voice_id
    _current_voice_id = voice_id
    return f"Voice set to {voice_id}."


@mcp.tool()
def list_voices() -> str:
    """Returns available voices from the ElevenLabs API."""
    voices = tts.list_voices()
    return json.dumps(voices, indent=2)


@mcp.tool()
def list_samples() -> str:
    """Lists available audio files in the configured audio files directory."""
    if not os.path.isdir(AUDIO_FILES_DIR):
        return f"Audio files directory not found: {AUDIO_FILES_DIR}"
    files = sorted(f for f in os.listdir(AUDIO_FILES_DIR) if not f.startswith("."))
    if not files:
        return "No audio files found."
    return "\n".join(files)


@mcp.tool()
def play_sample(filename: str) -> str:
    """
    Plays an audio file from the configured audio files directory.
    Use list_samples() first to see available files.
    """
    path = os.path.join(AUDIO_FILES_DIR, filename)
    if not os.path.isfile(path):
        return f"File not found: {filename}"
    audio.play(path, delete=False)
    return f"Played {filename}."


def _load_templates() -> dict:
    path = os.path.join(AUDIO_FILES_DIR, "templates.json")
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        return json.load(f)


@mcp.tool()
def list_templates() -> str:
    """
    Lists available reply templates. Each template maps a name to a pre-recorded
    audio clip with a description of when to use it. Check these before using
    speak() — if a template fits the situation, prefer play_template() instead.
    """
    templates = _load_templates()
    if not templates:
        return "No templates configured."
    lines = []
    for name, info in templates.items():
        lines.append(f"{name}: {info['description']}")
    return "\n".join(lines)


@mcp.tool()
def play_template(name: str) -> str:
    """
    Plays a pre-recorded reply template by name.
    Use list_templates() first to see available templates and when to use them.

    ALWAYS prefer this over speak() when:
    - The user mentions "gabbar" or references Sholay
    - The context matches a template description (e.g. dramatic moment, chaos, needing help)
    - The reply would be in Hinglish — templates handle this natively
    """
    templates = _load_templates()
    if name not in templates:
        return f"Template not found: {name}. Use list_templates() to see available options."
    filename = templates[name]["file"]
    path = os.path.join(AUDIO_FILES_DIR, filename)
    if not os.path.isfile(path):
        return f"Audio file missing: {filename}"
    audio.play(path, delete=False)
    return f"Played template: {name}."


@mcp.prompt()
def spoken_keypoints_prompt() -> str:
    """Returns the system instructions for converting LLM responses to spoken keypoints."""
    return SPOKEN_KEYPOINTS_SYSTEM_PROMPT


def main():
    if MCP_TRANSPORT == "http":
        mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
    else:
        mcp.run()


if __name__ == "__main__":
    main()

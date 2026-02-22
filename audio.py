import os
import subprocess

from config import AUDIO_PLAYER, AUDIO_TMP_PATH, PIPEWIRE_SINK


def play(audio_path: str = AUDIO_TMP_PATH, delete: bool = True):
    """Play an audio file. Deletes it afterwards unless delete=False."""
    cmd = [AUDIO_PLAYER]
    if AUDIO_PLAYER == "pw-play" and PIPEWIRE_SINK:
        cmd.extend(["--target", PIPEWIRE_SINK])
    cmd.append(audio_path)
    subprocess.run(cmd, check=True)
    if delete and os.path.exists(audio_path):
        os.remove(audio_path)

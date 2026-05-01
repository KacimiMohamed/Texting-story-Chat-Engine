from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from django.conf import settings
from moviepy import AudioFileClip

from creator.models import Message, Story


@dataclass
class MessageAudio:
    message_id: int
    file_path: Path
    duration: float


def _audio_duration_seconds(audio_path: Path) -> float:
    with AudioFileClip(str(audio_path)) as clip:
        return max(0.01, float(clip.duration))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_local_rvc(message: Message, out_path: Path) -> Path:
    cmd_template = getattr(settings, "RVC_COMMAND_TEMPLATE", "").strip()
    if not cmd_template:
        raise ValueError("RVC_COMMAND_TEMPLATE is not configured.")

    # Allowed placeholders: {text}, {output}, {character}
    cmd = cmd_template.format(
        text=message.text.replace('"', '\\"'),
        output=str(out_path),
        character=message.character.name,
    )
    subprocess.run(shlex.split(cmd), check=True)
    if not out_path.exists():
        raise FileNotFoundError(f"RVC command did not create audio: {out_path}")
    return out_path


def _synthesize_elevenlabs(message: Message, out_path: Path) -> Path:
    api_key = getattr(settings, "ELEVENLABS_API_KEY", "")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is not configured.")

    voice_map = getattr(settings, "ELEVENLABS_VOICE_MAP", {})
    default_voice = getattr(settings, "ELEVENLABS_DEFAULT_VOICE_ID", "")
    voice_id = voice_map.get(message.character.name, default_voice)
    if not voice_id:
        raise ValueError(
            "No ElevenLabs voice_id found. Set ELEVENLABS_DEFAULT_VOICE_ID or VOICE_MAP."
        )

    model_id = getattr(settings, "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    stability = float(getattr(settings, "ELEVENLABS_STABILITY", 0.45))
    similarity = float(getattr(settings, "ELEVENLABS_SIMILARITY_BOOST", 0.75))

    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": message.text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
            },
        },
        timeout=90,
    )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    return out_path


def synthesize_message_audio(message: Message, output_dir: Path) -> MessageAudio | None:
    provider = getattr(settings, "MESSAGE_AUDIO_PROVIDER", "none").lower().strip()
    if provider == "none":
        return None

    _ensure_dir(output_dir)
    ext = "mp3" if provider == "elevenlabs" else "wav"
    out_path = output_dir / f"message_{message.id}.{ext}"
    if out_path.exists():
        return MessageAudio(
            message_id=message.id,
            file_path=out_path,
            duration=_audio_duration_seconds(out_path),
        )

    if provider == "elevenlabs":
        _synthesize_elevenlabs(message, out_path)
    elif provider == "rvc":
        _run_local_rvc(message, out_path)
    else:
        raise ValueError(f"Unsupported MESSAGE_AUDIO_PROVIDER: {provider}")

    return MessageAudio(
        message_id=message.id,
        file_path=out_path,
        duration=_audio_duration_seconds(out_path),
    )


def build_story_audio(story: Story, messages: Iterable[Message]) -> dict[int, MessageAudio]:
    output_dir = Path(settings.MEDIA_ROOT) / "voice_cache" / f"story_{story.id}"
    result: dict[int, MessageAudio] = {}
    for message in messages:
        audio = synthesize_message_audio(message, output_dir=output_dir)
        if audio:
            result[message.id] = audio
    return result

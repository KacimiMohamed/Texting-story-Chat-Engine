from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from django.conf import settings
from moviepy import AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip
from moviepy.config import change_settings

from creator.models import Message, Story
from creator.services.voice_service import build_story_audio

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
BUBBLE_MAX_WIDTH = 860
BUBBLE_MARGIN_X = 60
BUBBLE_BOTTOM_MARGIN = 120
BUBBLE_PADDING_X = 32
BUBBLE_PADDING_Y = 22
BUBBLE_RADIUS = 34
MESSAGE_GAP_Y = 20
TEXT_SIZE = 40
NAME_SIZE = 28
SLIDE_DURATION = 0.45
MEME_DURATION = 1.8


@dataclass
class BubbleVisual:
    message: Message
    start_time: float
    clip: ImageClip
    height: int


def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    try:
        rgb = ImageColor.getrgb(value)
        if len(rgb) == 4:
            return rgb[:3]
        return rgb
    except ValueError:
        return fallback


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf"])
    else:
        candidates.extend(["DejaVuSans.ttf", "Arial.ttf"])

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_gradient_background(bg_color: str) -> Image.Image:
    top = _hex_to_rgb(bg_color, (30, 30, 30))
    bottom = tuple(max(0, int(c * 0.55)) for c in top)
    arr = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)

    for y in range(VIDEO_HEIGHT):
        t = y / max(1, VIDEO_HEIGHT - 1)
        arr[y, :, 0] = int(top[0] * (1 - t) + bottom[0] * t)
        arr[y, :, 1] = int(top[1] * (1 - t) + bottom[1] * t)
        arr[y, :, 2] = int(top[2] * (1 - t) + bottom[2] * t)
    return Image.fromarray(arr)


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width = font.getbbox(candidate)[2] - font.getbbox(candidate)[0]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _render_bubble_image(message: Message) -> tuple[np.ndarray, int]:
    bubble_color = _hex_to_rgb(message.character.color, (74, 144, 226))
    name_font = _load_font(NAME_SIZE, bold=True)
    text_font = _load_font(TEXT_SIZE)

    content_width = BUBBLE_MAX_WIDTH - (BUBBLE_PADDING_X * 2)
    name_text = message.character.name
    body_lines = _wrap_text(message.text, text_font, content_width)

    name_box = name_font.getbbox(name_text)
    name_height = (name_box[3] - name_box[1]) + 10

    line_height = text_font.getbbox("Ag")[3] - text_font.getbbox("Ag")[1]
    text_height = len(body_lines) * (line_height + 8)
    bubble_height = BUBBLE_PADDING_Y * 2 + name_height + text_height + 8

    bubble_image = Image.new("RGBA", (BUBBLE_MAX_WIDTH, bubble_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bubble_image)
    draw.rounded_rectangle(
        (0, 0, BUBBLE_MAX_WIDTH, bubble_height),
        radius=BUBBLE_RADIUS,
        fill=(bubble_color[0], bubble_color[1], bubble_color[2], 232),
    )

    name_x = BUBBLE_PADDING_X
    name_y = BUBBLE_PADDING_Y
    draw.text((name_x, name_y), name_text, fill=(255, 255, 255, 245), font=name_font)

    text_x = BUBBLE_PADDING_X
    text_y = name_y + name_height
    for line in body_lines:
        draw.text((text_x, text_y), line, fill=(255, 255, 255, 255), font=text_font)
        text_y += line_height + 8

    return np.array(bubble_image), bubble_height


def _render_meme_clip(image_path: str, start_time: float) -> ImageClip:
    with Image.open(image_path) as src:
        src = src.convert("RGBA")
        src.thumbnail((720, 720), Image.Resampling.LANCZOS)
        framed = ImageOps.expand(src, border=10, fill=(255, 255, 255, 255))

    img_np = np.array(framed)
    x = (VIDEO_WIDTH - img_np.shape[1]) / 2
    y = (VIDEO_HEIGHT - img_np.shape[0]) / 2

    return (
        ImageClip(img_np)
        .with_start(start_time)
        .with_duration(MEME_DURATION)
        .with_position((x, y))
        .with_opacity(0.97)
    )


def _build_bubble_positioner(
    index: int,
    all_bubbles: list[BubbleVisual],
) -> callable:
    this_bubble = all_bubbles[index]

    def position_at(t: float) -> tuple[float, float]:
        # Stack math: each newer bubble pushes older bubbles upward by
        # (new bubble height + 20px spacing).
        total_push = 0.0
        for later in all_bubbles[index + 1 :]:
            if t >= later.start_time:
                total_push += later.height + MESSAGE_GAP_Y

        base_y = VIDEO_HEIGHT - BUBBLE_BOTTOM_MARGIN - this_bubble.height
        target_y = base_y - total_push

        # Smooth upward slide while each push event happens.
        animated_y = target_y
        for later in all_bubbles[index + 1 :]:
            if later.start_time <= t < later.start_time + SLIDE_DURATION:
                slide_progress = (t - later.start_time) / SLIDE_DURATION
                eased = 1 - math.pow(1 - slide_progress, 3)
                animated_y += (later.height + MESSAGE_GAP_Y) * (1 - eased)

        return BUBBLE_MARGIN_X, animated_y

    return position_at


def _collect_story_messages(story: Story) -> Iterable[Message]:
    return (
        story.messages.select_related("character")
        .all()
        .order_by("order", "created_at", "id")
    )


def render_story_video(story: Story, output_path: str | Path, fps: int = 30) -> Path:
    """
    Render a 1080x1920 vertical texting-style video for a Story.
    """
    messages = list(_collect_story_messages(story))
    if not messages:
        raise ValueError("Story has no messages to render.")

    message_audio = build_story_audio(story, messages)

    bg_image = _draw_gradient_background(story.bg_color)
    background_clip = ImageClip(np.array(bg_image))

    timeline_seconds = 0.0
    bubble_visuals: list[BubbleVisual] = []
    meme_clips: list[ImageClip] = []
    audio_clips: list[AudioFileClip] = []

    for msg in messages:
        timeline_seconds += (msg.delay or 0) / 1000.0

        audio_duration = 0.0
        audio_meta = message_audio.get(msg.id)
        if audio_meta:
            clip = AudioFileClip(str(audio_meta.file_path)).with_start(timeline_seconds)
            audio_clips.append(clip)
            audio_duration = audio_meta.duration

        bubble_np, bubble_h = _render_bubble_image(msg)
        bubble_clip = (
            ImageClip(bubble_np)
            .with_start(timeline_seconds)
            .with_duration(3600)
            .with_opacity(1.0)
        )
        bubble_visuals.append(
            BubbleVisual(
                message=msg,
                start_time=timeline_seconds,
                clip=bubble_clip,
                height=bubble_h,
            )
        )

        if msg.image_file:
            image_path = Path(settings.MEDIA_ROOT) / msg.image_file.name
            if image_path.exists():
                meme_clips.append(_render_meme_clip(str(image_path), timeline_seconds))

        # Keep the story timeline locked to the spoken line duration.
        timeline_seconds += audio_duration

    for idx, bubble in enumerate(bubble_visuals):
        bubble.clip = bubble.clip.with_position(_build_bubble_positioner(idx, bubble_visuals))

    final_duration = timeline_seconds + max(2.0, MEME_DURATION)
    layers = [background_clip.with_duration(final_duration)]
    layers.extend([bubble.clip.with_duration(final_duration) for bubble in bubble_visuals])
    layers.extend(meme_clips)

    composite = CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT)).with_duration(
        final_duration
    )
    if audio_clips:
        mixed_audio = CompositeAudioClip(audio_clips).with_duration(final_duration)
        composite = composite.with_audio(mixed_audio)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure MoviePy to use project-level FFmpeg binaries.
    change_settings(
        {
            "FFMPEG_BINARY": settings.FFMPEG_BINARY,
            "FFPLAY_BINARY": settings.FFPLAY_BINARY,
        }
    )

    gpu_codec = getattr(settings, "VIDEO_EXPORT_CODEC", "h264_nvenc")
    fallback_codec = getattr(settings, "VIDEO_EXPORT_FALLBACK_CODEC", "libx264")
    preset = getattr(settings, "VIDEO_EXPORT_PRESET", "p7")
    bitrate = getattr(settings, "VIDEO_EXPORT_BITRATE", "8M")
    threads = getattr(settings, "VIDEO_EXPORT_THREADS", 0)

    nvenc_params = [
        "-preset",
        preset,
        "-tune",
        "hq",
        "-rc",
        "vbr",
        "-b:v",
        bitrate,
        "-maxrate",
        bitrate,
        "-bufsize",
        "16M",
        "-spatial-aq",
        "1",
        "-aq-strength",
        "8",
        "-pix_fmt",
        "yuv420p",
    ]

    try:
        composite.write_videofile(
            str(out_path),
            fps=fps,
            codec=gpu_codec,
            audio=bool(audio_clips),
            ffmpeg_params=nvenc_params,
            threads=threads,
            preset=preset,
        )
    except Exception:
        # Automatic fallback when NVENC is unavailable or ffmpeg lacks GPU support.
        composite.write_videofile(
            str(out_path),
            fps=fps,
            codec=fallback_codec,
            audio=bool(audio_clips),
            preset="veryfast",
            bitrate=bitrate,
            threads=threads if threads else 4,
        )
    for clip in audio_clips:
        clip.close()
    composite.close()
    return out_path

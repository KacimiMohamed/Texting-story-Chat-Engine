from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont
from django.conf import settings
from moviepy.config import change_settings
from moviepy.editor import AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip

from creator.models import Message, Story

# Instagram Dark Mode Group Chat Constants
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
AVATAR_SIZE = 65
BUBBLE_OFFSET_X = 76
SIDE_MARGIN = 40
HEADER_HEIGHT = 220
BUBBLE_MAX_WIDTH = 700
BUBBLE_PADDING_X = 30
BUBBLE_PADDING_Y = 20
BUBBLE_RADIUS = 30
STACK_GAP = 20
ENTRY_Y = 1750
HEADER_CUTOFF_Y = 220
TEXT_SIZE = 34
NAME_SIZE = 24
SUBTITLE_SIZE = 22
IMAGE_RADIUS = 24

COLOR_BG = "#000000"
COLOR_INCOMING = "#262626"
COLOR_OUTGOING = "#3797F0"
COLOR_TEXT = "#FFFFFF"
COLOR_NAME_TEXT = "#A8A8A8"


@dataclass
class TimedMessage:
    message: Message
    start_time: float
    scroll_step: float
    bottom_y: float = 0.0


class VideoGenerator:
    def __init__(self, story: Story):
        self.story = story

    def _messages(self) -> Iterable[Message]:
        return (
            self.story.messages.select_related("character")
            .all()
            .order_by("order", "created_at", "id")
        )

    def _font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        candidates = (
            [
                "Helvetica-Bold.ttf",
                "Arial Bold.ttf",
                "DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
            if bold
            else [
                "Helvetica.ttf",
                "Arial.ttf",
                "DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _wrap(self, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            candidate_w = font.getbbox(candidate)[2] - font.getbbox(candidate)[0]
            if candidate_w <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _load_message_image(self, message: Message, max_side: int) -> Image.Image | None:
        if not message.image_file:
            return None
        src_path = Path(settings.MEDIA_ROOT) / message.image_file.name
        if not src_path.exists():
            return None
        with Image.open(src_path) as src:
            image = src.convert("RGBA")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        rounded_mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(rounded_mask).rounded_rectangle(
            (0, 0, image.size[0], image.size[1]), radius=IMAGE_RADIUS, fill=255
        )
        image.putalpha(rounded_mask)
        return image

    def _get_circular_avatar(self, image_field, size: int) -> Image.Image | None:
        if not image_field or not getattr(image_field, "name", None):
            return None

        path = Path(settings.MEDIA_ROOT) / image_field.name
        if not path.exists():
            return None

        try:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                # Crop to perfect center square so faces don't stretch
                min_side = min(img.size)
                left = (img.width - min_side) / 2
                top = (img.height - min_side) / 2
                img = img.crop((left, top, left + min_side, top + min_side))
                img = img.resize((size, size), Image.Resampling.LANCZOS)

                # Cut into a perfect circle
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                img.putalpha(mask)
                return img
        except Exception as e:
            print(f"Error loading avatar: {e}")
            return None

    def _header_visual(self) -> np.ndarray:
        # Taller header background
        header = Image.new("RGBA", (VIDEO_WIDTH, HEADER_HEIGHT), ImageColor.getrgb("#000000") + (255,))
        draw = ImageDraw.Draw(header)
        
        # 1. Back Chevron (Shifted down)
        arr_x, arr_y = 45, 110
        draw.line([(arr_x + 18, arr_y - 18), (arr_x, arr_y), (arr_x + 18, arr_y + 18)], fill="#FFFFFF", width=6, joint="curve")
        
        # 2. Group Avatar (Shifted down)
        group_img_field = getattr(self.story, 'group_image', None)
        group_avatar = self._get_circular_avatar(group_img_field, 60)
        
        if group_avatar:
            header.alpha_composite(group_avatar, (95, 80))
        else:
            draw.ellipse((95, 80, 155, 140), fill="#262626")
        
        # 3. Group Name and Subtitle (Shifted down)
        title_font = self._font(34, bold=True)
        title_text = (self.story.title or "").strip() or "Group name"
        draw.text((175, 85), title_text, fill="#FFFFFF", font=title_font)
        
        sub_font = self._font(22)
        draw.text((175, 130), "Tap here for group info", fill="#A8A8A8", font=sub_font)
        
        # 4. Right Side UI Icons (Much larger sizing)
        try:
            from django.conf import settings
            from pathlib import Path
            assets_dir = Path(settings.BASE_DIR) / 'assets'
            
            # Video Call Icon - Increased to 60x60
            video_icon_path = assets_dir / 'ig_video.png'
            if video_icon_path.exists():
                video_icon = Image.open(video_icon_path).convert("RGBA")
                video_icon = video_icon.resize((60, 60), Image.Resampling.LANCZOS)
                header.alpha_composite(video_icon, (VIDEO_WIDTH - 210, 80))
            
            # Audio Call Icon - Increased to 52x52
            phone_icon_path = assets_dir / 'ig_phone.png'
            if phone_icon_path.exists():
                phone_icon = Image.open(phone_icon_path).convert("RGBA")
                phone_icon = phone_icon.resize((52, 52), Image.Resampling.LANCZOS)
                header.alpha_composite(phone_icon, (VIDEO_WIDTH - 110, 84))
                
        except Exception as e:
            print(f"Warning: Could not load header UI icons: {e}")
            
        return np.array(header)

    def _bubble_visual(self, message: Message, outgoing: bool) -> tuple[np.ndarray, int]:
        text_font = self._font(TEXT_SIZE)
        name_font = self._font(NAME_SIZE, bold=True)

        bubble_rgb = ImageColor.getrgb(COLOR_OUTGOING if outgoing else COLOR_INCOMING)
        text_rgb = ImageColor.getrgb(COLOR_TEXT)
        name_rgb = ImageColor.getrgb(COLOR_NAME_TEXT)

        max_content_w = BUBBLE_MAX_WIDTH - (BUBBLE_PADDING_X * 2)
        lines = self._wrap(message.text or "", text_font, max_content_w)

        text_widths = [
            (text_font.getbbox(line)[2] - text_font.getbbox(line)[0]) for line in lines
        ]
        embedded_image = self._load_message_image(message, max_side=420)
        image_width = embedded_image.width if embedded_image else 0
        widest_content = max([image_width, *text_widths, 0])

        body_width = max(100, widest_content + (BUBBLE_PADDING_X * 2))
        body_width = min(body_width, BUBBLE_MAX_WIDTH)

        line_h = text_font.getbbox("Ag")[3] - text_font.getbbox("Ag")[1]
        text_h = len(lines) * (line_h + 8)
        image_h = (embedded_image.height + 16) if embedded_image else 0
        bubble_h = BUBBLE_PADDING_Y * 2 + text_h + image_h
        if outgoing:
            canvas_w = body_width
            total_h = bubble_h
            bubble_x = 0
            bubble_y = 0
        else:
            name_h = name_font.getbbox(message.character.name)[3] - name_font.getbbox(message.character.name)[1]
            bubble_y = name_h + 10
            total_h = bubble_y + bubble_h
            bubble_x = BUBBLE_OFFSET_X
            canvas_w = bubble_x + body_width

        canvas = Image.new("RGBA", (canvas_w, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (bubble_x, bubble_y, bubble_x + body_width, bubble_y + bubble_h),
            radius=BUBBLE_RADIUS,
            fill=(bubble_rgb[0], bubble_rgb[1], bubble_rgb[2], 255),
        )

        if not outgoing:
            draw.text((bubble_x, 0), message.character.name, font=name_font, fill=name_rgb + (255,))
            avatar_y = total_h - AVATAR_SIZE - 5
            char_img_field = getattr(message.character, "avatar", None)
            char_avatar = self._get_circular_avatar(char_img_field, AVATAR_SIZE)
            if char_avatar:
                canvas.alpha_composite(char_avatar, (0, int(avatar_y)))
            else:
                # Fallback if no image uploaded
                draw.ellipse((0, avatar_y, AVATAR_SIZE, avatar_y + AVATAR_SIZE), fill="#333333")
                initial = message.character.name[0].upper() if message.character.name else "U"
                draw.text((22, avatar_y + 15), initial, fill="#FFFFFF", font=self._font(28, bold=True))

        y = bubble_y + BUBBLE_PADDING_Y
        for line in lines:
            draw.text((bubble_x + BUBBLE_PADDING_X, y), line, font=text_font, fill=text_rgb + (255,))
            y += line_h + 8
        if embedded_image:
            canvas.alpha_composite(embedded_image, (bubble_x + BUBBLE_PADDING_X, y + 8))

        return np.array(canvas), total_h

    def _build_chat_world(
        self, timed_messages: list[TimedMessage], final_duration: float, anchor_id: int | None
    ) -> tuple[CompositeVideoClip, list[float], list[float], int]:
        world_layers: list[ImageClip] = []
        message_starts: list[float] = []
        message_bottoms: list[float] = []
        y_cursor = HEADER_HEIGHT + 50

        for timed in timed_messages:
            outgoing = anchor_id is not None and timed.message.character_id == anchor_id
            bubble_np, bubble_h = self._bubble_visual(timed.message, outgoing=outgoing)
            bubble_w = int(bubble_np.shape[1])
            bubble_x = VIDEO_WIDTH - bubble_w - 40 if outgoing else 40
            bubble_clip = (
                ImageClip(bubble_np)
                .set_start(timed.start_time)
                .set_duration(max(0.05, final_duration - timed.start_time))
                .set_position((bubble_x, y_cursor))
            )
            world_layers.append(bubble_clip)
            bottom_y = float(y_cursor + bubble_h)
            timed.bottom_y = bottom_y
            message_starts.append(float(timed.start_time))
            message_bottoms.append(bottom_y)
            y_cursor = int(bottom_y) + STACK_GAP

        world_height = max(y_cursor + 240, VIDEO_HEIGHT + 1)
        chat_world = CompositeVideoClip(world_layers, size=(VIDEO_WIDTH, world_height)).set_duration(
            final_duration
        )
        return chat_world, message_starts, message_bottoms, world_height

    def _scroll_at(
        self, t: float, keyframe_times: list[float], keyframe_offsets: list[float]
    ) -> float:
        if not keyframe_times:
            return 0.0
        if t <= keyframe_times[0]:
            return keyframe_offsets[0]

        idx = bisect_right(keyframe_times, t) - 1
        idx = min(max(idx, 0), len(keyframe_times) - 1)

        if idx >= len(keyframe_times) - 1:
            return keyframe_offsets[idx]

        t0, t1 = keyframe_times[idx], keyframe_times[idx + 1]
        y0, y1 = keyframe_offsets[idx], keyframe_offsets[idx + 1]
        if t1 <= t0:
            return y1
        p = (t - t0) / (t1 - t0)
        return y0 + ((y1 - y0) * p)

    def _resolve_sfx(self, filename: str) -> Path | None:
        candidates = [
            Path(getattr(settings, f"{filename.split('.')[0].upper()}_SFX_PATH", "")),
            Path(settings.MEDIA_ROOT) / "sfx" / filename,
            Path(settings.BASE_DIR) / "assets" / "sfx" / filename,
            Path(settings.BASE_DIR) / filename,
        ]
        for candidate in candidates:
            if str(candidate) and candidate.exists():
                return candidate
        return None

    def _sfx_map(self) -> dict:
        from django.conf import settings
        from pathlib import Path
        
        sfx_dir = Path(settings.BASE_DIR) / 'assets' / 'sfx'
        
        # Maps the database string to the actual file on your computer
        return {
            "ping": sfx_dir / "ping.mp3",
            "vine_boom": sfx_dir / "vine_boom.mp3",
            "bruh": sfx_dir / "bruh.mp3",
            "camera_shutter": sfx_dir / "camera.mp3",
            "notification": sfx_dir / "notification.mp3",
        }

    def _apply_volume(self, clip: AudioFileClip, volume: float) -> AudioFileClip:
        if hasattr(clip, "with_volume_scaled"):
            return clip.with_volume_scaled(volume)
        if hasattr(clip, "volumex"):
            return clip.volumex(volume)
        return clip

    def _audio_duration(self, audio_path: Path) -> float | None:
        try:
            with AudioFileClip(str(audio_path)) as clip:
                return float(clip.duration or 0.0)
        except Exception:
            return None

    def generate(self, output_path: str | Path | None = None, fps: int = 30) -> Path:
        self.story.refresh_from_db()
        messages = list(self._messages())
        if not messages:
            raise ValueError("Story has no messages.")

        change_settings(
            {
                "FFMPEG_BINARY": settings.FFMPEG_BINARY,
                "FFPLAY_BINARY": settings.FFPLAY_BINARY,
            }
        )

        bg = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
        bg[:, :, :] = ImageColor.getrgb(COLOR_BG)
        bg_clip = ImageClip(bg).set_start(0)
        header_clip = ImageClip(self._header_visual()).set_start(0)

        timed_messages: list[TimedMessage] = []
        audio_layers: list[AudioFileClip] = []
        current_time = 0.0
        sfx_map = self._sfx_map()
        sfx_volume = float(getattr(settings, "SFX_DEFAULT_VOLUME", 0.7))
        anchor_id = next(
            (m.character_id for m in messages if (m.text or "").strip() or m.image_file), None
        )

        for msg in messages:
            current_time += (msg.delay or 0) / 1000.0

            audio_path: Path | None = None
            if hasattr(msg, "audio_file") and msg.audio_file:
                audio_path = Path(msg.audio_file.path)
                if not os.path.isfile(str(audio_path)):
                    continue

            has_visual_message = bool((msg.text or "").strip() or msg.image_file)
            if has_visual_message:
                timed_messages.append(TimedMessage(message=msg, start_time=current_time, scroll_step=0))

            selected_sfx = sfx_map.get(msg.sfx_choice)
            if selected_sfx:
                sfx_clip = AudioFileClip(str(selected_sfx)).set_start(current_time)
                audio_layers.append(self._apply_volume(sfx_clip, sfx_volume))

            voice_duration = None
            if audio_path:
                print(f"DEBUG: Loading audio from -> {audio_path}")
                voice_duration = self._audio_duration(audio_path)
                if voice_duration:
                    audio_layers.append(AudioFileClip(str(audio_path)).set_start(current_time))

            current_time += voice_duration if voice_duration else 2.0

        if not timed_messages:
            raise ValueError("Story has no drawable messages.")

        final_duration = current_time + 1.2
        chat_world, message_starts, message_bottoms, world_height = self._build_chat_world(
            timed_messages, final_duration, anchor_id
        )
        max_scroll = max(0.0, float(world_height - VIDEO_HEIGHT))

        keyframe_times: list[float] = [0.0]
        keyframe_offsets: list[float] = [0.0]
        scroll_offset = 0.0

        for timed, start_t, bottom_y in zip(timed_messages, message_starts, message_bottoms):
            if start_t > keyframe_times[-1]:
                keyframe_times.append(start_t)
                keyframe_offsets.append(scroll_offset)

            # Vsub/TikTok style:
            # - stay fixed while current message bottom < 1700
            # - then move world up by (bottom - 1700)
            target_offset = max(0.0, float(bottom_y - 1700.0))
            target_offset = min(max_scroll, target_offset)
            timed.scroll_step = target_offset - scroll_offset

            keyframe_times.append(start_t + 0.4)
            keyframe_offsets.append(target_offset)
            scroll_offset = target_offset

        chat_clip = chat_world.set_duration(final_duration).set_position(
            lambda t: (0, -self._scroll_at(float(t), keyframe_times, keyframe_offsets))
        )
        layers = [
            bg_clip.set_duration(final_duration),
            chat_clip,
            header_clip.set_duration(final_duration),
        ]

        composite = CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT)).set_duration(
            final_duration
        )
        if audio_layers:
            composite = composite.set_audio(
                CompositeAudioClip(audio_layers).set_duration(final_duration)
            )

        target = (
            Path(output_path)
            if output_path
            else (Path(settings.MEDIA_ROOT) / "exports" / f"story_{self.story.id}.mp4")
        )
        target.parent.mkdir(parents=True, exist_ok=True)

        composite.write_videofile(
            str(target),
            fps=fps,
            codec="h264_nvenc",
            audio=bool(audio_layers),
            preset="p7",
            threads=getattr(settings, "VIDEO_EXPORT_THREADS", 0),
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )

        for layer in audio_layers:
            layer.close()
        composite.close()
        return target

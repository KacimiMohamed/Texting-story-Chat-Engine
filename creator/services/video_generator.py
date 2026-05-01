from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont
from pilmoji import Pilmoji
from django.conf import settings
from moviepy.config import change_settings
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    concatenate_videoclips,
)

from creator.models import Message, Story

# Instagram Dark Mode Group Chat Constants
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
AVATAR_SIZE = 65
BUBBLE_OFFSET_X = 76
SIDE_MARGIN = 40
HEADER_HEIGHT = 320
BUBBLE_MAX_WIDTH = 700
BUBBLE_PADDING_X = 30
BUBBLE_PADDING_Y = 20
BUBBLE_RADIUS = 40
STACK_GAP = 20
ENTRY_Y = 1750
HEADER_CUTOFF_Y = 220
TEXT_SIZE = 45
NAME_SIZE = 23
SUBTITLE_SIZE = 22
IMAGE_RADIUS = 24

COLOR_BG = "#000000"
COLOR_INCOMING = "#262626"
COLOR_OUTGOING = "#3797F0"
COLOR_TEXT = "#FFFFFF"
COLOR_NAME_TEXT = "#A8A8A8"
CONTAINER_RADIUS = 50


class VideoGenerator:
    def _apply_top_corner_radius(self, image: Image.Image, radius: int) -> Image.Image:
        """Round only the top-left/top-right corners; keep bottom corners square."""
        width, height = image.size
        mask = Image.new("L", (width, height), 255)
        corner = Image.new("L", (radius * 2, radius * 2), 0)
        corner_draw = ImageDraw.Draw(corner)
        corner_draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)

        top_left = corner.crop((0, 0, radius, radius))
        top_right = corner.crop((radius, 0, radius * 2, radius))
        mask.paste(top_left, (0, 0))
        mask.paste(top_right, (width - radius, 0))

        rounded = image.copy()
        rounded.putalpha(mask)
        return rounded

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

    def _name_font(self, size: int) -> ImageFont.ImageFont:
        # Use a distinct face/weight for names to contrast with message body text.
        candidates = [
            "DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "Times New Roman Bold.ttf",
            "Arial Bold.ttf",
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return self._font(size, bold=True)

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

    def _load_chat_photo(self, message: Message, max_width: int = 600) -> Image.Image | None:
        if not message.image:
            return None
        src_path = Path(settings.MEDIA_ROOT) / message.image.name
        if not src_path.exists():
            return None
        with Image.open(src_path) as src:
            image = src.convert("RGBA")
        if image.width > max_width:
            ratio = max_width / float(image.width)
            target_h = max(1, int(image.height * ratio))
            image = image.resize((max_width, target_h), Image.Resampling.LANCZOS)
        rounded_mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(rounded_mask).rounded_rectangle(
            (0, 0, image.size[0], image.size[1]), radius=40, fill=255
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
        header = Image.new(
            "RGBA", (VIDEO_WIDTH, HEADER_HEIGHT), ImageColor.getrgb(COLOR_BG) + (255,)
        )
        draw = ImageDraw.Draw(header)
        
        # 1. Back Chevron (Shifted down)
        arr_x, arr_y = 45, 150
        draw.line([(arr_x + 18, arr_y - 18), (arr_x, arr_y), (arr_x + 18, arr_y + 18)], fill="#FFFFFF", width=6, joint="curve")
        
        # 2. Group Avatar (Shifted down)
        group_img_field = getattr(self.story, 'group_image', None)
        group_avatar = self._get_circular_avatar(group_img_field, 90)
        
        if group_avatar:
            header.alpha_composite(group_avatar, (95, 105))
        else:
            draw.ellipse((95, 105, 185, 195), fill="#262626")
        
        # 3. Group Name and Subtitle (Shifted down)
        title_font = self._font(44, bold=True)
        title_text = (self.story.title or "").strip() or "Group name"
        with Pilmoji(header) as pilmoji:
            pilmoji.text((215, 106), title_text, fill="#FFFFFF", font=title_font)
        
        subtitle_font = self._font(22)
        with Pilmoji(header) as pilmoji:
            pilmoji.text(
                (215, 164), "Tap here for group info", fill="#A8A8A8", font=subtitle_font
            )
        
        # 4. Right Side UI Icons (Much larger sizing)
        try:
            from django.conf import settings
            from pathlib import Path
            assets_dir = Path(settings.BASE_DIR) / 'assets'
            
            # Video Call Icon - Increased to 60x60
            video_icon_path = assets_dir / 'ig_video.png'
            if video_icon_path.exists():
                video_icon = Image.open(video_icon_path).convert("RGBA")
                video_icon = video_icon.resize((78, 78), Image.Resampling.LANCZOS)
                header.alpha_composite(video_icon, (VIDEO_WIDTH - 238, 112))
            
            # Audio Call Icon - Increased to 52x52
            phone_icon_path = assets_dir / 'ig_phone.png'
            if phone_icon_path.exists():
                phone_icon = Image.open(phone_icon_path).convert("RGBA")
                phone_icon = phone_icon.resize((68, 68), Image.Resampling.LANCZOS)
                header.alpha_composite(phone_icon, (VIDEO_WIDTH - 130, 116))
                
        except Exception as e:
            print(f"Warning: Could not load header UI icons: {e}")

        header = self._apply_top_corner_radius(header, CONTAINER_RADIUS)
        return np.array(header)

    def _bubble_visual(self, message: Message, outgoing: bool) -> tuple[np.ndarray, int]:
        text_font = self._font(TEXT_SIZE)
        name_font = self._name_font(NAME_SIZE)

        bubble_rgb = ImageColor.getrgb(COLOR_OUTGOING if outgoing else COLOR_INCOMING)
        text_rgb = ImageColor.getrgb(COLOR_TEXT)
        name_rgb = ImageColor.getrgb(COLOR_NAME_TEXT)

        # Strict split:
        # if message.image => render borderless rounded photo + name only.
        # else => render normal text bubble.
        if message.image:
            chat_photo = self._load_chat_photo(message, max_width=600)
            if not chat_photo:
                # Missing file fallback to normal text message path.
                pass
            else:
                name_h = name_font.getbbox(message.character.name)[3] - name_font.getbbox(
                    message.character.name
                )[1]
                photo_y = name_h + 10
                total_h = photo_y + chat_photo.height + BUBBLE_PADDING_Y
                photo_x = 0 if outgoing else BUBBLE_OFFSET_X
                canvas_w = photo_x + chat_photo.width

                canvas = Image.new("RGBA", (canvas_w, total_h), (0, 0, 0, 0))
                with Pilmoji(canvas) as pilmoji:
                    pilmoji.text(
                        (photo_x, 0), message.character.name, font=name_font, fill=name_rgb + (255,)
                    )
                # No bubble/background behind the photo.
                canvas.alpha_composite(chat_photo, (photo_x, photo_y))
                return np.array(canvas), total_h

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
            name_h = name_font.getbbox(message.character.name)[3] - name_font.getbbox(
                message.character.name
            )[1]
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
            with Pilmoji(canvas) as pilmoji:
                pilmoji.text(
                    (bubble_x, 0), message.character.name, font=name_font, fill=name_rgb + (255,)
                )
            avatar_y = total_h - AVATAR_SIZE - 5
            char_img_field = getattr(message.character, "avatar", None)
            char_avatar = self._get_circular_avatar(char_img_field, AVATAR_SIZE)
            if char_avatar:
                canvas.alpha_composite(char_avatar, (0, int(avatar_y)))
            else:
                # Fallback if no image uploaded
                draw.ellipse((0, avatar_y, AVATAR_SIZE, avatar_y + AVATAR_SIZE), fill="#333333")
                initial = message.character.name[0].upper() if message.character.name else "U"
                with Pilmoji(canvas) as pilmoji:
                    pilmoji.text(
                        (22, avatar_y + 15), initial, fill="#FFFFFF", font=self._font(28, bold=True)
                    )

        y = bubble_y + BUBBLE_PADDING_Y
        for line in lines:
            with Pilmoji(canvas) as pilmoji:
                pilmoji.text(
                    (bubble_x + BUBBLE_PADDING_X, y), line, font=text_font, fill=text_rgb + (255,)
                )
            y += line_h + 8
        if embedded_image:
            canvas.alpha_composite(embedded_image, (bubble_x + BUBBLE_PADDING_X, y + 8))

        return np.array(canvas), total_h

    def _chunk_messages(self, messages: list[Message], chunk_size: int = 4) -> list[list[Message]]:
        return [messages[i : i + chunk_size] for i in range(0, len(messages), chunk_size)]

    def _voice_clip_for_message(self, msg: Message) -> AudioFileClip | None:
        if not (hasattr(msg, "audio_file") and msg.audio_file):
            return None
        audio_path = Path(msg.audio_file.path)
        if not os.path.isfile(str(audio_path)):
            return None
        return AudioFileClip(str(audio_path))

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

        header_rgba = Image.fromarray(self._header_visual()).convert("RGBA")

        visual_messages = [m for m in messages if (m.text or "").strip() or m.image_file or m.image]
        if not visual_messages:
            raise ValueError("Story has no drawable messages.")

        chunked_messages = self._chunk_messages(visual_messages, chunk_size=4)
        audio_layers: list[AudioFileClip] = []
        sfx_map = self._sfx_map()
        sfx_volume = float(getattr(settings, "SFX_DEFAULT_VOLUME", 0.7))
        anchor_id = self.story.sender_id
        all_clips: list[ImageClip] = []

        for chunk in chunked_messages:
            current_displayed_messages: list[Message] = []

            for msg in chunk:
                current_displayed_messages.append(msg)

                frame = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 255, 0))
                draw = ImageDraw.Draw(frame)

                rendered_bubbles: list[tuple[np.ndarray, int, int]] = []
                current_y = HEADER_HEIGHT + 1
                for displayed_msg in current_displayed_messages:
                    outgoing = anchor_id is not None and displayed_msg.character_id == anchor_id
                    bubble_np, bubble_h = self._bubble_visual(displayed_msg, outgoing=outgoing)
                    bubble_w = int(bubble_np.shape[1])
                    bubble_x = VIDEO_WIDTH - bubble_w - 40 if outgoing else 40
                    rendered_bubbles.append((bubble_np, bubble_x, current_y))
                    current_y += bubble_h + STACK_GAP

                final_y = current_y - STACK_GAP if rendered_bubbles else HEADER_HEIGHT
                black_bottom = min(VIDEO_HEIGHT - 1, int(final_y) + 70)
                draw.rounded_rectangle(
                    [0, 0, VIDEO_WIDTH, black_bottom], radius=CONTAINER_RADIUS, fill=ImageColor.getrgb(COLOR_BG)
                )

                frame.paste(header_rgba, (0, 0), header_rgba)

                for bubble_np, bubble_x, bubble_y in rendered_bubbles:
                    bubble_img = Image.fromarray(bubble_np).convert("RGBA")
                    frame.paste(bubble_img, (bubble_x, bubble_y), bubble_img)

                msg_delay = (msg.delay or 0) / 1000.0
                voice_clip = self._voice_clip_for_message(msg)
                voice_duration = float(voice_clip.duration or 0.0) if voice_clip else 0.0
                base_duration = voice_duration if voice_duration > 0 else 2.0
                clip_duration = max(0.05, msg_delay + base_duration)

                clip = ImageClip(np.array(frame)).set_duration(clip_duration)

                clip_audio_layers: list[AudioFileClip] = []
                selected_sfx = sfx_map.get(msg.sfx_choice)
                if selected_sfx and selected_sfx.exists():
                    sfx_clip = self._apply_volume(AudioFileClip(str(selected_sfx)), sfx_volume).set_start(
                        msg_delay
                    )
                    clip_audio_layers.append(sfx_clip)
                    audio_layers.append(sfx_clip)

                if voice_clip:
                    voice_clip = voice_clip.set_start(msg_delay)
                    clip_audio_layers.append(voice_clip)
                    audio_layers.append(voice_clip)

                if clip_audio_layers:
                    clip = clip.set_audio(CompositeAudioClip(clip_audio_layers).set_duration(clip_duration))

                all_clips.append(clip)

        if not all_clips:
            raise ValueError("No progressive clips were generated from messages.")

        composite = concatenate_videoclips(all_clips, method="compose")
        composite = composite.set_duration(sum(float(c.duration or 0.0) for c in all_clips))
        has_audio = any(c.audio is not None for c in all_clips)

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
            audio=has_audio,
            preset="p7",
            threads=getattr(settings, "VIDEO_EXPORT_THREADS", 0),
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )

        for clip in all_clips:
            if clip.audio:
                clip.audio.close()
            clip.close()
        composite.close()
        return target

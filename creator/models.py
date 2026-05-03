from django.db import models
from django.core.exceptions import ValidationError

import re


class Character(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, help_text="Hex color (e.g. #22c55e)")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    # Default is 'Adam', a popular deep voice on ElevenLabs
    elevenlabs_voice_id = models.CharField(
        max_length=50,
        default="pNInz6obpgDQGcFmaJgB",
        help_text="ElevenLabs Voice ID",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Story(models.Model):
    title = models.CharField(max_length=200)
    bg_color = models.CharField(max_length=20, default="#ffffff")
    characters = models.ManyToManyField(Character, related_name="stories", blank=True)
    raw_script = models.TextField(
        blank=True,
        null=True,
        help_text="Paste a raw script here to auto-generate messages.",
    )
    sender = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_stories",
    )
    group_image = models.ImageField(upload_to="group_headers/", blank=True, null=True)

    class Meta:
        verbose_name_plural = "stories"
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title

    _SCRIPT_SPEAKER_RE = re.compile(
        r"(^|(?<=[\s\.\!\?]))(?P<name>[^\[\]:]{1,60}?):\s*",
        flags=re.MULTILINE,
    )
    _SCRIPT_VISUAL_RE = re.compile(
        r"\[(?:photo|visual|image|pic)\s*:[^\]]*\]",
        flags=re.IGNORECASE,
    )

    def _parse_raw_script(self, script: str) -> list[tuple[str, str, bool]]:
        """
        Returns a list of (character_name, text, is_visual_placeholder).

        - A speaker block begins at `<name>:` where `<name>` is not bracketed.
        - Visual tags like `[Photo: ...]` split the block:
          - preceding words => normal text message
          - each visual tag => placeholder message with text="" (so user can upload an image later)
        """
        s = (script or "").strip()
        if not s:
            return []

        matches = list(self._SCRIPT_SPEAKER_RE.finditer(s))
        if not matches:
            return []

        out: list[tuple[str, str, bool]] = []
        for idx, m in enumerate(matches):
            name = (m.group("name") or "").strip()
            if not name:
                continue
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(s)
            block = s[start:end].strip()
            if not block:
                continue

            cursor = 0
            for vm in self._SCRIPT_VISUAL_RE.finditer(block):
                before = block[cursor:vm.start()].strip()
                if before:
                    out.append((name, before, False))
                out.append((name, "", True))
                cursor = vm.end()

            tail = block[cursor:].strip()
            if tail:
                out.append((name, tail, False))

        return out

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        script = (self.raw_script or "").strip()
        if not script:
            return

        parsed = self._parse_raw_script(script)
        if not parsed:
            # If it doesn't parse, don't destroy user input.
            return

        existing_max = (
            self.messages.aggregate(models.Max("order")).get("order__max") or -1
        )
        next_order = int(existing_max) + 1

        created_messages: list[Message] = []
        story_char_ids: set[int] = set()
        for character_name, text, _is_visual in parsed:
            character, _ = Character.objects.get_or_create(
                name=character_name,
                defaults={"color": "#22c55e"},
            )
            story_char_ids.add(character.id)
            created_messages.append(
                Message(
                    story=self,
                    character=character,
                    text=text,
                    order=next_order,
                )
            )
            next_order += 1

        Message.objects.bulk_create(created_messages)
        if story_char_ids:
            self.characters.add(*story_char_ids)

        # Clear the script after successful import.
        self.raw_script = None
        super().save(update_fields=["raw_script"])


class Message(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="messages")
    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="messages"
    )
    text = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="chat_images/", null=True, blank=True)
    audio_file = models.FileField(upload_to="messages_audio/", blank=True, null=True)
    delay = models.PositiveIntegerField(
        default=0, help_text="Delay in milliseconds before showing this message."
    )
    sfx_choice = models.CharField(
        max_length=64,
        default="ping",
        help_text="Sound played when this message appears (files in assets/sfx).",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["story", "order", "created_at", "id"]

    def clean(self):
        if not self.text and not self.image:
            raise ValidationError("A message must contain either text or an image.")

    def __str__(self) -> str:
        return f"{self.story.title}: {self.character.name}"

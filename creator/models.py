from django.db import models


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


class Message(models.Model):
    class SFXChoices(models.TextChoices):
        NONE = "none", "None"
        PING = "ping", "Ping"
        VINE_BOOM = "vine_boom", "Vine Boom"
        BRUH = "bruh", "Bruh"
        CAMERA_SHUTTER = "camera_shutter", "Camera Shutter"
        NOTIFICATION = "notification", "Notification"

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="messages")
    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="messages"
    )
    text = models.TextField()
    image = models.ImageField(upload_to="chat_images/", null=True, blank=True)
    image_file = models.ImageField(upload_to="messages/", blank=True, null=True)
    audio_file = models.FileField(upload_to="messages_audio/", blank=True, null=True)
    delay = models.PositiveIntegerField(
        default=0, help_text="Delay in milliseconds before showing this message."
    )
    sfx_choice = models.CharField(
        max_length=32,
        choices=SFXChoices.choices,
        default=SFXChoices.PING,
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["story", "order", "created_at", "id"]

    def __str__(self) -> str:
        return f"{self.story.title}: {self.character.name}"

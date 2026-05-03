from django import forms
from django.contrib import admin

from .models import Character, Message, Story
from .services.video_generator import VideoGenerator
from .sfx_registry import get_sfx_choices


class SFXChoiceAdminMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "sfx_choice":
            return forms.ChoiceField(
                label=db_field.verbose_name or "SFX",
                choices=get_sfx_choices(),
                required=not db_field.blank,
                help_text=db_field.help_text or "",
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "elevenlabs_voice_id")
    search_fields = ("name",)


class MessageInline(SFXChoiceAdminMixin, admin.TabularInline):
    model = Message
    extra = 0
    fields = ("order", "character", "text", "image", "audio_file", "delay", "sfx_choice")
    ordering = ("order", "id")
    autocomplete_fields = ("character",)


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("title", "sender", "bg_color", "raw_script")
    search_fields = ("title",)
    filter_horizontal = ("characters",)
    inlines = [MessageInline]
    actions = ("generate_video",)
    fields = ("title", "sender", "group_image", "raw_script")
    autocomplete_fields = ("sender",)

    @admin.action(description="Generate Video")
    def generate_video(self, request, queryset):
        success = 0
        for story in queryset:
            try:
                output = VideoGenerator(story).generate()
                success += 1
                self.message_user(
                    request,
                    f"Generated video for '{story.title}': {output}",
                    level="SUCCESS",
                )
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to generate '{story.title}': {exc}",
                    level="ERROR",
                )
        if success:
            self.message_user(request, f"Video generation finished for {success} story(s).")


@admin.register(Message)
class MessageAdmin(SFXChoiceAdminMixin, admin.ModelAdmin):
    list_display = ("story", "order", "character", "delay", "sfx_choice", "audio_file")
    list_filter = ("story", "character")
    search_fields = ("story__title", "character__name", "text")
    ordering = ("story", "order", "id")
    autocomplete_fields = ("story", "character")
    fields = ("story", "character", "text", "image", "audio_file", "delay", "sfx_choice", "order")

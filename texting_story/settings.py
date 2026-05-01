"""
Django settings for texting_story project.
"""

import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-change-this-in-production"

DEBUG = True

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "creator",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "texting_story.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "texting_story.wsgi.application"
ASGI_APPLICATION = "texting_story.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# FFmpeg / GPU export settings for MoviePy rendering.
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
FFPROBE_BINARY = os.getenv("FFPROBE_BINARY", "ffprobe")
FFPLAY_BINARY = os.getenv("FFPLAY_BINARY", "ffplay")
VIDEO_EXPORT_CODEC = os.getenv("VIDEO_EXPORT_CODEC", "h264_nvenc")
VIDEO_EXPORT_PRESET = os.getenv("VIDEO_EXPORT_PRESET", "p7")
VIDEO_EXPORT_THREADS = int(os.getenv("VIDEO_EXPORT_THREADS", "0"))
VIDEO_EXPORT_BITRATE = os.getenv("VIDEO_EXPORT_BITRATE", "8M")
VIDEO_EXPORT_FALLBACK_CODEC = os.getenv("VIDEO_EXPORT_FALLBACK_CODEC", "libx264")
PING_SFX_PATH = os.getenv("PING_SFX_PATH", "")
CAMERA_SFX_PATH = os.getenv("CAMERA_SFX_PATH", "")
SFX_DEFAULT_VOLUME = float(os.getenv("SFX_DEFAULT_VOLUME", "0.7"))

# Voice synthesis settings (for timeline-locked message audio).
MESSAGE_AUDIO_PROVIDER = os.getenv("MESSAGE_AUDIO_PROVIDER", "none")  # none|elevenlabs|rvc
ELEVENLABS_API_KEY = "sk_8b69153828b1998a30c51e8d3e384b56993b455062ab731d"
ELEVENLABS_DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_STABILITY = float(os.getenv("ELEVENLABS_STABILITY", "0.45"))
ELEVENLABS_SIMILARITY_BOOST = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75"))
ELEVENLABS_VOICE_MAP = json.loads(os.getenv("ELEVENLABS_VOICE_MAP", "{}"))

# Example template:
# RVC_COMMAND_TEMPLATE='python infer.py --text "{text}" --speaker "{character}" --output "{output}"'
RVC_COMMAND_TEMPLATE = os.getenv("RVC_COMMAND_TEMPLATE", "")
